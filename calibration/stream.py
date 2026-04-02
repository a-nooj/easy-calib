import cv2
import numpy as np
import time

from calibration.config import (
    MIN_CHARUCO_CORNERS, MIN_CAPTURES,
    charuco_detector, charuco_board, april_detector,
)
from calibration.state import lock, state, open_camera


# ═══════════════════════════════════════════════════════════════════
#  MJPEG STREAM GENERATOR
# ═══════════════════════════════════════════════════════════════════
def generate_frames():
    with lock:
        state["stream_active"] = True
    cam = open_camera()

    while True:
        with lock:
            if not state["stream_active"]:
                break

        ret, frame = cam.read()
        if not ret:
            time.sleep(0.03)
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        display = frame.copy()

        with lock:
            mode = state["mode"]
            cal = state["calibration"]

        # — CHARUCO DETECTION MODE —
        if mode == "charuco":
            charuco_corners, charuco_ids, marker_corners, marker_ids = \
                charuco_detector.detectBoard(gray)

            n_corners = 0 if charuco_corners is None else len(charuco_corners)

            # Draw marker outlines
            if marker_corners is not None and len(marker_corners) > 0:
                cv2.aruco.drawDetectedMarkers(display, marker_corners, marker_ids,
                                              borderColor=(80, 80, 80))

            # Draw charuco corners
            if charuco_corners is not None and charuco_ids is not None and len(charuco_corners) > 0:
                cv2.aruco.drawDetectedCornersCharuco(display, charuco_corners, charuco_ids,
                                                     cornerColor=(255, 160, 50))
                # Corner count badge
                color = (50, 210, 120) if n_corners >= MIN_CHARUCO_CORNERS else (60, 130, 255)
                cv2.putText(display, f"{n_corners} corners",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            with lock:
                state["last_detection"]["charuco_count"] = n_corners
                state["last_detection"]["charuco_enough"] = n_corners >= MIN_CHARUCO_CORNERS

        # — APRILTAG DETECTION MODE —
        elif mode == "apriltag":
            corners, ids, _ = april_detector.detectMarkers(gray)
            detected = ids is not None and len(ids) > 0

            if detected:
                cv2.aruco.drawDetectedMarkers(display, corners, ids,
                                              borderColor=(50, 210, 120))
                # Label corners
                for i, c in enumerate(corners):
                    pts = c[0].astype(int)
                    labels = ["TL", "TR", "BR", "BL"]
                    for j, pt in enumerate(pts):
                        cv2.circle(display, tuple(pt), 5, (255, 160, 50), -1)
                        cv2.putText(display, labels[j], (pt[0]+8, pt[1]-8),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 160, 50), 1)

                cv2.putText(display, f"Tag #{ids[0][0]} detected",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (50, 210, 120), 2)
            else:
                cv2.putText(display, "No tag detected",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 255), 2)

            with lock:
                state["last_detection"]["apriltag_detected"] = detected
                state["last_detection"]["apriltag_corners"] = \
                    corners[0][0].tolist() if detected else None

        # — UNDISTORT MODE —
        elif mode == "undistort" and cal is not None:
            K = np.array(cal["K"])
            dist = np.array(cal["dist"])
            h, w = frame.shape[:2]
            new_K, roi = cv2.getOptimalNewCameraMatrix(K, dist, (w, h), 0.5, (w, h))
            display = cv2.undistort(frame, K, dist, None, new_K)
            cv2.putText(display, "Undistorted",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (50, 210, 120), 2)

        # — HAND-EYE LIVE OVERLAY MODE —
        elif mode == "handeye" and cal is not None:
            K = np.array(cal["K"])
            dist = np.array(cal["dist"])

            # Detect AprilTag
            corners, ids, _ = april_detector.detectMarkers(gray)
            detected = ids is not None and len(ids) > 0

            with lock:
                he = state["handeye"]
                tag_sz = state["handeye_tag_size"]
                state["last_detection"]["apriltag_detected"] = detected

            if detected:
                cv2.aruco.drawDetectedMarkers(display, corners, ids,
                                              borderColor=(50, 210, 120))

                # Solve tag pose
                half = tag_sz / 2.0
                obj_pts = np.array([
                    [-half,  half, 0], [ half,  half, 0],
                    [ half, -half, 0], [-half, -half, 0],
                ], dtype=np.float64)
                img_pts = corners[0][0].astype(np.float64)
                ok_pnp, rvec_tag, tvec_tag = cv2.solvePnP(
                    obj_pts, img_pts, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE)

                if ok_pnp:
                    # Draw tag frame (RGB = XYZ)
                    cv2.drawFrameAxes(display, K, dist, rvec_tag, tvec_tag,
                                      tag_sz * 0.6)
                    cv2.putText(display, "Tag", (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 210, 120), 1)

                    if he is not None:
                        # Compose: camera → tag → (HE transform) → robot base
                        T_cam_tag = np.eye(4)
                        R_tag, _ = cv2.Rodrigues(rvec_tag)
                        T_cam_tag[:3, :3] = R_tag
                        T_cam_tag[:3, 3] = tvec_tag.flatten()

                        T_he = np.eye(4)
                        T_he[:3, :3] = np.array(he["R"])
                        T_he[:3, 3] = np.array(he["t"])

                        T_overlay = T_cam_tag @ T_he

                        rvec_ov, _ = cv2.Rodrigues(T_overlay[:3, :3])
                        tvec_ov = T_overlay[:3, 3].reshape(3, 1)
                        cv2.drawFrameAxes(display, K, dist, rvec_ov, tvec_ov,
                                          tag_sz * 0.4)

                        # Draw dashed line connecting tag origin to HE frame
                        tag_2d, _ = cv2.projectPoints(
                            np.zeros((1, 3)), rvec_tag, tvec_tag, K, dist)
                        he_2d, _ = cv2.projectPoints(
                            np.zeros((1, 3)), rvec_ov, tvec_ov, K, dist)
                        pt1 = tuple(tag_2d[0][0].astype(int))
                        pt2 = tuple(he_2d[0][0].astype(int))
                        cv2.line(display, pt1, pt2, (255, 200, 60), 1, cv2.LINE_AA)

                        cv2.putText(display, "HE Frame",
                                    (pt2[0] + 8, pt2[1] - 8),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 200, 60), 1)

                    n_pairs = len(state.get("touchpoint_pairs", []))
                    cv2.putText(display, f"Points: {n_pairs}",
                                (20, display.shape[0] - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 180), 1)
            else:
                cv2.putText(display, "No tag — point at AprilTag",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)

        # — DEBUG / TUNE MODE —
        elif mode == "debug" and cal is not None:
            K = np.array(cal["K"])
            dist = np.array(cal["dist"])
            h, w = frame.shape[:2]

            # Undistort
            new_K, roi = cv2.getOptimalNewCameraMatrix(K, dist, (w, h), 0.5, (w, h))
            display = cv2.undistort(frame, K, dist, None, new_K)

            # Detect AprilTag
            gray_ud = cv2.cvtColor(display, cv2.COLOR_BGR2GRAY)
            corners, ids, _ = april_detector.detectMarkers(gray_ud)
            detected = ids is not None and len(ids) > 0

            with lock:
                he = state["handeye"]
                tag_sz = state["handeye_tag_size"]
                state["last_detection"]["apriltag_detected"] = detected

            if detected:
                cv2.aruco.drawDetectedMarkers(display, corners, ids,
                                              borderColor=(50, 210, 120))

                half = tag_sz / 2.0
                obj_pts = np.array([
                    [-half,  half, 0], [ half,  half, 0],
                    [ half, -half, 0], [-half, -half, 0],
                ], dtype=np.float64)
                img_pts = corners[0][0].astype(np.float64)
                ok_pnp, rvec_tag, tvec_tag = cv2.solvePnP(
                    obj_pts, img_pts, new_K, None,
                    flags=cv2.SOLVEPNP_IPPE_SQUARE)

                if ok_pnp:
                    # Draw tag coordinate frame
                    cv2.drawFrameAxes(display, new_K, None, rvec_tag, tvec_tag,
                                      tag_sz * 0.6)

                    # Compute reprojection error
                    proj, _ = cv2.projectPoints(obj_pts, rvec_tag, tvec_tag,
                                                new_K, None)
                    rpe = cv2.norm(img_pts.reshape(-1, 2),
                                   proj.reshape(-1, 2), cv2.NORM_L2) / 4
                    dist_to_tag = float(np.linalg.norm(tvec_tag))

                    cv2.putText(display,
                                f"Tag RPE:{rpe:.2f}px  dist:{dist_to_tag*100:.1f}cm",
                                (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                                (50, 210, 120), 1)

                    # Project HE frame if available
                    if he is not None:
                        T_cam_tag = np.eye(4)
                        R_tag, _ = cv2.Rodrigues(rvec_tag)
                        T_cam_tag[:3, :3] = R_tag
                        T_cam_tag[:3, 3] = tvec_tag.flatten()

                        T_he = np.eye(4)
                        T_he[:3, :3] = np.array(he["R"])
                        T_he[:3, 3] = np.array(he["t"])

                        T_overlay = T_cam_tag @ T_he
                        rvec_ov, _ = cv2.Rodrigues(T_overlay[:3, :3])
                        tvec_ov = T_overlay[:3, 3].reshape(3, 1)

                        cv2.drawFrameAxes(display, new_K, None, rvec_ov, tvec_ov,
                                          tag_sz * 0.4)

                        # Line from tag to HE frame
                        tag_2d, _ = cv2.projectPoints(
                            np.zeros((1, 3)), rvec_tag, tvec_tag, new_K, None)
                        he_2d, _ = cv2.projectPoints(
                            np.zeros((1, 3)), rvec_ov, tvec_ov, new_K, None)
                        pt1 = tuple(tag_2d[0][0].astype(int))
                        pt2 = tuple(he_2d[0][0].astype(int))
                        cv2.line(display, pt1, pt2, (255, 200, 60), 1, cv2.LINE_AA)
                        cv2.putText(display, "Robot Frame",
                                    (pt2[0]+8, pt2[1]-8),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 200, 60), 1)

                        # Project a small grid on the tag plane for visual feedback
                        grid_pts = []
                        for gx in range(-2, 3):
                            for gy in range(-2, 3):
                                grid_pts.append([gx * tag_sz * 0.3,
                                                 gy * tag_sz * 0.3, 0])
                        grid_pts = np.array(grid_pts, dtype=np.float64)
                        proj_grid, _ = cv2.projectPoints(
                            grid_pts, rvec_tag, tvec_tag, new_K, None)
                        for p in proj_grid:
                            px, py = int(p[0][0]), int(p[0][1])
                            cv2.circle(display, (px, py), 2,
                                       (80, 80, 120), -1)
            else:
                cv2.putText(display, "No AprilTag detected",
                            (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            (100, 100, 255), 1)

            # Info bar at bottom
            cv2.putText(display,
                        f"DEBUG  fx:{cal['fx']:.0f}  fy:{cal['fy']:.0f}  "
                        f"cx:{cal['cx']:.0f}  cy:{cal['cy']:.0f}  "
                        f"k1:{cal['k1']:.4f}  k2:{cal['k2']:.4f}",
                        (10, display.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (80, 90, 110), 1)

        # — EVALUATE / LIVE ACCUMULATION MODE —
        elif mode == "evaluate":
            charuco_corners, charuco_ids, marker_corners, marker_ids = \
                charuco_detector.detectBoard(gray)
            n_corners = 0 if charuco_corners is None else len(charuco_corners)

            if n_corners >= MIN_CHARUCO_CORNERS:
                h_f, w_f = gray.shape[:2]
                with lock:
                    acc = state["eval_acc"]
                    if acc is None or acc["img_size"] != (w_f, h_f):
                        acc = {
                            "coverage": np.zeros((h_f, w_f), np.float32),
                            "errors":   np.zeros((h_f, w_f), np.float32),
                            "img_size": (w_f, h_f),
                        }
                        state["eval_acc"] = acc

                    # Accumulate corner coverage
                    for corner in charuco_corners:
                        cx_c, cy_c = int(corner[0][0]), int(corner[0][1])
                        cv2.circle(acc["coverage"], (cx_c, cy_c), radius=20,
                                   color=1.0, thickness=-1)

                    # Accumulate reprojection errors if calibration available
                    if cal is not None:
                        K_e = np.array(cal["K"], dtype=np.float64)
                        dist_e = np.array(cal["dist"], dtype=np.float64)
                        obj_pts, img_pts = charuco_board.matchImagePoints(
                            charuco_corners, charuco_ids)
                        if obj_pts is not None and len(obj_pts) >= 4:
                            retval_e, rvec_e, tvec_e = cv2.solvePnP(
                                obj_pts, img_pts, K_e, dist_e)
                            if retval_e:
                                proj_e, _ = cv2.projectPoints(
                                    obj_pts, rvec_e, tvec_e, K_e, dist_e)
                                errs_e = np.linalg.norm(
                                    img_pts.reshape(-1, 2) - proj_e.reshape(-1, 2),
                                    axis=1)
                                for pt_e, err_e in zip(
                                        img_pts.reshape(-1, 2), errs_e):
                                    cv2.circle(acc["errors"],
                                               (int(pt_e[0]), int(pt_e[1])),
                                               radius=25, color=float(err_e),
                                               thickness=-1)

            # Draw detected corners on the display frame
            if charuco_corners is not None and charuco_ids is not None \
                    and len(charuco_corners) > 0:
                cv2.aruco.drawDetectedCornersCharuco(
                    display, charuco_corners, charuco_ids,
                    cornerColor=(80, 220, 160))
            color_ev = (50, 210, 120) if n_corners >= MIN_CHARUCO_CORNERS \
                else (100, 100, 255)
            cv2.putText(display, "● Evaluating — move the board",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_ev, 2)
            cv2.putText(display, f"{n_corners} corners",
                        (20, display.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 180), 1)

        # Capture count overlay (in charuco mode)
        if mode == "charuco":
            with lock:
                nc = len(state["captures"])
            cv2.putText(display, f"Captures: {nc}/{MIN_CAPTURES}+",
                        (20, display.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 180), 1)

        _, buf = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 82])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')

        time.sleep(0.01)
