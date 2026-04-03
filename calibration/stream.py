import base64
import cv2
import numpy as np
import time

from calibration.config import (
    MIN_CHARUCO_CORNERS, MIN_CAPTURES,
    charuco_detector, charuco_board, april_detector,
    APRILTAG_SIZE,
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
                color = (50, 210, 120) if n_corners >= MIN_CHARUCO_CORNERS else (60, 130, 255)
                cv2.putText(display, f"{n_corners} corners",
                            (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            with lock:
                state["last_detection"]["charuco_count"] = n_corners
                state["last_detection"]["charuco_enough"] = n_corners >= MIN_CHARUCO_CORNERS

            # — INTRINSIC AUTO-CAPTURE —
            with lock:
                auto = state["auto_capture"]
                last_auto = state["auto_capture_last"]
                flash_until = state["auto_capture_flash_until"]

            if auto and n_corners >= MIN_CHARUCO_CORNERS:
                now = time.time()
                if now - last_auto >= 2.0:
                    h_a, w_a = frame.shape[:2]
                    small = cv2.resize(display, (320, 180))
                    _, tbuf = cv2.imencode('.jpg', small, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    thumb_b64 = base64.b64encode(tbuf.tobytes()).decode()
                    with lock:
                        state["captures"].append({
                            "corners": charuco_corners,
                            "ids": charuco_ids,
                            "img_size": (w_a, h_a),
                            "thumbnail": thumb_b64,
                        })
                        state["auto_capture_last"] = now
                        state["auto_capture_flash_until"] = now + 0.5
                    flash_until = now + 0.5

            # Flash green border after capture
            if time.time() < flash_until:
                cv2.rectangle(display, (0, 0),
                              (display.shape[1] - 1, display.shape[0] - 1),
                              (50, 210, 120), 8)

        # — APRILTAG DETECTION MODE —
        elif mode == "apriltag":
            corners, ids, _ = april_detector.detectMarkers(gray)
            detected = ids is not None and len(ids) > 0

            if detected:
                cv2.aruco.drawDetectedMarkers(display, corners, ids,
                                              borderColor=(50, 210, 120))
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

            # — EXTRINSIC AUTO-CAPTURE —
            with lock:
                auto_ext = state["auto_capture"]
                cal_ext = state["calibration"]
                tag_sz_ext = state["auto_capture_tag_size"]
                flash_until_ext = state["auto_capture_flash_until"]

            if auto_ext:
                if detected and cal_ext is not None:
                    with lock:
                        state["auto_capture_stable_frames"] += 1
                        stable = state["auto_capture_stable_frames"]
                else:
                    with lock:
                        state["auto_capture_stable_frames"] = 0
                    stable = 0

                # Draw stability progress bar at bottom of frame
                if detected:
                    bar_w = int(display.shape[1] * min(1.0, stable / 15.0))
                    cv2.rectangle(display,
                                  (0, display.shape[0] - 5),
                                  (bar_w, display.shape[0]),
                                  (50, 210, 120), -1)

                if stable >= 15 and cal_ext is not None and detected:
                    img_pts_ext = corners[0][0].astype(np.float64)
                    half_ext = tag_sz_ext / 2.0
                    obj_pts_ext = np.array([
                        [-half_ext,  half_ext, 0],
                        [ half_ext,  half_ext, 0],
                        [ half_ext, -half_ext, 0],
                        [-half_ext, -half_ext, 0],
                    ], dtype=np.float64)
                    K_ext = np.array(cal_ext["K"], dtype=np.float64)
                    dist_ext = np.array(cal_ext["dist"], dtype=np.float64)
                    ok_pnp, rvec_ext, tvec_ext = cv2.solvePnP(
                        obj_pts_ext, img_pts_ext, K_ext, dist_ext,
                        flags=cv2.SOLVEPNP_IPPE_SQUARE)
                    if ok_pnp:
                        R_ext, _ = cv2.Rodrigues(rvec_ext)
                        proj_ext, _ = cv2.projectPoints(
                            obj_pts_ext, rvec_ext, tvec_ext, K_ext, dist_ext)
                        rpe_ext = float(cv2.norm(
                            img_pts_ext.reshape(-1, 2),
                            proj_ext.reshape(-1, 2), cv2.NORM_L2) / 4)
                        thumb_f = display.copy()
                        cv2.drawFrameAxes(thumb_f, K_ext, dist_ext,
                                          rvec_ext, tvec_ext, tag_sz_ext * 0.5)
                        thumb_f = cv2.resize(thumb_f, (320, 180))
                        _, tbuf_ext = cv2.imencode(
                            '.jpg', thumb_f, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        thumb_b64_ext = base64.b64encode(tbuf_ext.tobytes()).decode()
                        with lock:
                            state["extrinsic"] = {
                                "tag_id": int(ids[0][0]),
                                "R": R_ext.tolist(),
                                "t": tvec_ext.flatten().tolist(),
                                "rvec": rvec_ext.flatten().tolist(),
                                "rpe": round(rpe_ext, 4),
                                "tag_size": tag_sz_ext,
                                "thumbnail": thumb_b64_ext,
                            }
                            state["auto_capture"] = False
                            state["auto_capture_stable_frames"] = 0
                            state["auto_capture_flash_until"] = time.time() + 1.0
                        flash_until_ext = time.time() + 1.0

            if time.time() < flash_until_ext:
                cv2.rectangle(display, (0, 0),
                              (display.shape[1] - 1, display.shape[0] - 1),
                              (50, 210, 120), 8)

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

            corners, ids, _ = april_detector.detectMarkers(gray)
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
                    obj_pts, img_pts, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE)

                if ok_pnp:
                    cv2.drawFrameAxes(display, K, dist, rvec_tag, tvec_tag, tag_sz * 0.6)
                    cv2.putText(display, "Tag", (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (50, 210, 120), 1)

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
                        cv2.drawFrameAxes(display, K, dist, rvec_ov, tvec_ov, tag_sz * 0.4)

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

            new_K, roi = cv2.getOptimalNewCameraMatrix(K, dist, (w, h), 0.5, (w, h))
            display = cv2.undistort(frame, K, dist, None, new_K)

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
                    cv2.drawFrameAxes(display, new_K, None, rvec_tag, tvec_tag, tag_sz * 0.6)

                    proj, _ = cv2.projectPoints(obj_pts, rvec_tag, tvec_tag, new_K, None)
                    rpe = cv2.norm(img_pts.reshape(-1, 2),
                                   proj.reshape(-1, 2), cv2.NORM_L2) / 4
                    dist_to_tag = float(np.linalg.norm(tvec_tag))
                    cv2.putText(display,
                                f"Tag RPE:{rpe:.2f}px  dist:{dist_to_tag*100:.1f}cm",
                                (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                                (50, 210, 120), 1)

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
                        cv2.drawFrameAxes(display, new_K, None, rvec_ov, tvec_ov, tag_sz * 0.4)

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

                        grid_pts = []
                        for gx in range(-2, 3):
                            for gy in range(-2, 3):
                                grid_pts.append([gx * tag_sz * 0.3, gy * tag_sz * 0.3, 0])
                        grid_pts = np.array(grid_pts, dtype=np.float64)
                        proj_grid, _ = cv2.projectPoints(
                            grid_pts, rvec_tag, tvec_tag, new_K, None)
                        for p in proj_grid:
                            px, py = int(p[0][0]), int(p[0][1])
                            cv2.circle(display, (px, py), 2, (80, 80, 120), -1)
            else:
                cv2.putText(display, "No AprilTag detected",
                            (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            (100, 100, 255), 1)

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

                    for corner in charuco_corners:
                        cx_c, cy_c = int(corner[0][0]), int(corner[0][1])
                        cv2.circle(acc["coverage"], (cx_c, cy_c), radius=20,
                                   color=1.0, thickness=-1)

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
                auto_on = state["auto_capture"]
            label = f"Auto: {nc}/{MIN_CAPTURES}+" if auto_on else f"Captures: {nc}/{MIN_CAPTURES}+"
            cv2.putText(display, label,
                        (20, display.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 180), 1)

        _, buf = cv2.imencode('.jpg', display, [cv2.IMWRITE_JPEG_QUALITY, 82])
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')

        time.sleep(0.01)
