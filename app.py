"""
Camera Calibration Tool
=======================
Guided intrinsic (ChArUco) + extrinsic (AprilTag) camera calibration
using OpenCV. Run this on the machine with the camera attached.

Usage:
    pip install -r requirements.txt
    python app.py
    Open http://localhost:5000 in your browser
"""

import cv2
import numpy as np
import threading
import json
import time
import base64
import io
from flask import Flask, render_template, Response, jsonify, request, send_file

app = Flask(__name__)

# ═══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════
CHARUCO_SQUARES_X = 7
CHARUCO_SQUARES_Y = 5
CHARUCO_SQUARE_LENGTH = 0.030   # 30 mm
CHARUCO_MARKER_LENGTH = 0.022   # 22 mm
APRILTAG_SIZE = 0.050           # 50 mm (physical printed size)
MIN_CHARUCO_CORNERS = 6         # minimum per frame
MIN_CAPTURES = 4                # minimum frames for calibration

# ═══════════════════════════════════════════════════════════════════
#  OPENCV SETUP
# ═══════════════════════════════════════════════════════════════════
charuco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
charuco_board = cv2.aruco.CharucoBoard(
    (CHARUCO_SQUARES_X, CHARUCO_SQUARES_Y),
    CHARUCO_SQUARE_LENGTH,
    CHARUCO_MARKER_LENGTH,
    charuco_dict,
)
charuco_detector = cv2.aruco.CharucoDetector(charuco_board)

april_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
april_params = cv2.aruco.DetectorParameters()
april_detector = cv2.aruco.ArucoDetector(april_dict, april_params)

# ═══════════════════════════════════════════════════════════════════
#  GLOBAL STATE  (protected by lock)
# ═══════════════════════════════════════════════════════════════════
lock = threading.Lock()
camera = None
stream_active = False

state = {
    "mode": "idle",              # idle | charuco | apriltag | undistort | handeye | debug
    "captures": [],              # list of (charuco_corners, charuco_ids, img_size)
    "calibration": None,         # dict with fx,fy,cx,cy,k1..k5,p1,p2,rpe
    "extrinsic": None,           # dict with R, t, rvec
    "handeye_pairs": [],         # list of {cam_rvec, cam_tvec, ee_R, ee_t}
    "touchpoint_pairs": [],      # list of {cam_pt, robot_pt, thumbnail}
    "handeye": None,             # result: {R, t, method, config}
    "handeye_config": "eye-in-hand",  # "eye-in-hand" | "eye-to-hand" | "touch-point"
    "handeye_tag_size": APRILTAG_SIZE,
    "last_detection": {          # updated every frame
        "charuco_count": 0,
        "charuco_enough": False,
        "apriltag_detected": False,
        "apriltag_corners": None,
    },
}


def open_camera():
    global camera
    if camera is None or not camera.isOpened():
        camera = cv2.VideoCapture(0)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        camera.set(cv2.CAP_PROP_FPS, 30)
        time.sleep(0.3)
    return camera


def release_camera():
    global camera
    if camera is not None:
        camera.release()
        camera = None


# ═══════════════════════════════════════════════════════════════════
#  MJPEG STREAM GENERATOR
# ═══════════════════════════════════════════════════════════════════
def generate_frames():
    global stream_active
    stream_active = True
    cam = open_camera()

    while stream_active:
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
                he_config = state["handeye_config"]
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

                        # Draw the robot/EE frame projected through hand-eye
                        if he_config == "eye-in-hand":
                            # X_cam = T_he @ X_ee  →  T_cam_ee = T_he
                            # Robot base frame via: T_cam_base = T_cam_tag @ inv(T_tag_base)
                            # But for overlay, show EE frame = cam origin transformed
                            # and show a second set of axes representing the HE offset
                            T_overlay = T_cam_tag @ T_he
                        else:
                            # eye-to-hand: camera is fixed, robot moves
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

                    n_pairs = len(state.get("handeye_pairs", []))
                    cv2.putText(display, f"Pairs: {n_pairs}",
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


# ═══════════════════════════════════════════════════════════════════
#  ROUTES — PAGES
# ═══════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template("index.html")


# ═══════════════════════════════════════════════════════════════════
#  ROUTES — STREAM
# ═══════════════════════════════════════════════════════════════════
@app.route("/api/stream")
def stream():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/stream/stop", methods=["POST"])
def stop_stream():
    global stream_active
    stream_active = False
    return jsonify(ok=True)


# ═══════════════════════════════════════════════════════════════════
#  ROUTES — MODE
# ═══════════════════════════════════════════════════════════════════
@app.route("/api/mode", methods=["POST"])
def set_mode():
    mode = request.json.get("mode", "idle")
    with lock:
        state["mode"] = mode
    return jsonify(ok=True, mode=mode)


# ═══════════════════════════════════════════════════════════════════
#  ROUTES — BOARD GENERATION
# ═══════════════════════════════════════════════════════════════════
@app.route("/api/board/charuco")
def get_charuco_board():
    """Generate a high-res ChArUco board image for printing."""
    img = charuco_board.generateImage((1400, 1000), marginSize=60, borderBits=1)
    _, buf = cv2.imencode('.png', img)
    return send_file(io.BytesIO(buf.tobytes()), mimetype='image/png',
                     download_name='charuco_board.png')


@app.route("/api/board/apriltag")
def get_apriltag_board():
    """Generate AprilTag 36h11 tag #0 for printing."""
    tag_img = cv2.aruco.generateImageMarker(april_dict, 0, 600, borderBits=1)
    # Add white border for printing
    bordered = cv2.copyMakeBorder(tag_img, 80, 80, 80, 80,
                                  cv2.BORDER_CONSTANT, value=255)
    _, buf = cv2.imencode('.png', bordered)
    return send_file(io.BytesIO(buf.tobytes()), mimetype='image/png',
                     download_name='apriltag_36h11_id0.png')


# ═══════════════════════════════════════════════════════════════════
#  ROUTES — INTRINSIC CALIBRATION
# ═══════════════════════════════════════════════════════════════════
@app.route("/api/status")
def get_status():
    with lock:
        det = state["last_detection"].copy()
        det["num_captures"] = len(state["captures"])
        det["has_calibration"] = state["calibration"] is not None
        det["has_extrinsic"] = state["extrinsic"] is not None
        det["has_handeye"] = state["handeye"] is not None
        det["num_handeye_pairs"] = len(state["handeye_pairs"])
        det["num_touchpoint_pairs"] = len(state["touchpoint_pairs"])
        det["mode"] = state["mode"]
    return jsonify(det)


@app.route("/api/capture/intrinsic", methods=["POST"])
def capture_intrinsic():
    """Capture current frame's charuco corners for calibration."""
    cam = open_camera()
    ret, frame = cam.read()
    if not ret:
        return jsonify(ok=False, error="Camera read failed"), 500

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    charuco_corners, charuco_ids, marker_corners, marker_ids = \
        charuco_detector.detectBoard(gray)

    if charuco_corners is None or len(charuco_corners) < MIN_CHARUCO_CORNERS:
        return jsonify(ok=False,
                       error=f"Not enough corners detected ({0 if charuco_corners is None else len(charuco_corners)}/{MIN_CHARUCO_CORNERS})"), 400

    # Generate thumbnail
    thumb = frame.copy()
    cv2.aruco.drawDetectedCornersCharuco(thumb, charuco_corners, charuco_ids)
    thumb = cv2.resize(thumb, (320, 180))
    _, tbuf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
    thumb_b64 = base64.b64encode(tbuf.tobytes()).decode()

    with lock:
        state["captures"].append({
            "corners": charuco_corners,
            "ids": charuco_ids,
            "img_size": (gray.shape[1], gray.shape[0]),
        })
        n = len(state["captures"])

    return jsonify(ok=True, num_captures=n, corners_found=len(charuco_corners),
                   thumbnail=thumb_b64)


@app.route("/api/capture/clear", methods=["POST"])
def clear_captures():
    with lock:
        state["captures"] = []
        state["calibration"] = None
    return jsonify(ok=True)


@app.route("/api/calibrate/intrinsic", methods=["POST"])
def calibrate_intrinsic():
    """Run Zhang's method via OpenCV."""
    with lock:
        captures = state["captures"][:]

    if len(captures) < MIN_CAPTURES:
        return jsonify(ok=False,
                       error=f"Need at least {MIN_CAPTURES} captures (have {len(captures)})"), 400

    all_obj_pts = []
    all_img_pts = []
    all_ids = []
    img_size = captures[0]["img_size"]

    for cap in captures:
        obj_pts, img_pts = charuco_board.matchImagePoints(cap["corners"], cap["ids"])
        if obj_pts is not None and len(obj_pts) >= MIN_CHARUCO_CORNERS:
            all_obj_pts.append(obj_pts)
            all_img_pts.append(img_pts)

    if len(all_obj_pts) < MIN_CAPTURES:
        return jsonify(ok=False, error="Not enough valid captures after filtering"), 400

    try:
        ret, K, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
            all_obj_pts, all_img_pts, img_size, None, None,
            flags=cv2.CALIB_FIX_K3 | cv2.CALIB_FIX_K4 | cv2.CALIB_FIX_K5
        )
    except cv2.error as e:
        return jsonify(ok=False, error=f"Calibration failed: {str(e)}"), 500

    # Compute per-view reprojection errors
    per_view_errors = []
    for i in range(len(all_obj_pts)):
        proj, _ = cv2.projectPoints(all_obj_pts[i], rvecs[i], tvecs[i], K, dist_coeffs)
        err = cv2.norm(all_img_pts[i], proj.reshape(-1, 1, 2), cv2.NORM_L2) / len(proj)
        per_view_errors.append(round(float(err), 4))

    d = dist_coeffs.flatten().tolist()
    result = {
        "fx": round(float(K[0, 0]), 2),
        "fy": round(float(K[1, 1]), 2),
        "cx": round(float(K[0, 2]), 2),
        "cy": round(float(K[1, 2]), 2),
        "k1": round(float(d[0]), 6),
        "k2": round(float(d[1]), 6),
        "p1": round(float(d[2]), 6),
        "p2": round(float(d[3]), 6),
        "k3": round(float(d[4]), 6) if len(d) > 4 else 0.0,
        "rpe": round(float(ret), 4),
        "per_view_errors": per_view_errors,
        "image_size": list(img_size),
        "K": K.tolist(),
        "dist": dist_coeffs.tolist(),
        "num_frames": len(all_obj_pts),
    }

    with lock:
        state["calibration"] = result

    return jsonify(ok=True, result=result)


# ═══════════════════════════════════════════════════════════════════
#  ROUTES — EXTRINSIC CALIBRATION
# ═══════════════════════════════════════════════════════════════════
@app.route("/api/capture/extrinsic", methods=["POST"])
def capture_extrinsic():
    """Capture AprilTag and solve PnP for camera pose."""
    with lock:
        cal = state["calibration"]
    if cal is None:
        return jsonify(ok=False, error="Run intrinsic calibration first"), 400

    # Allow user to override tag size
    tag_size = request.json.get("tag_size", APRILTAG_SIZE) if request.json else APRILTAG_SIZE

    cam = open_camera()
    ret, frame = cam.read()
    if not ret:
        return jsonify(ok=False, error="Camera read failed"), 500

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = april_detector.detectMarkers(gray)

    if ids is None or len(ids) == 0:
        return jsonify(ok=False, error="No AprilTag detected in frame"), 400

    # Use first detected tag
    img_pts = corners[0][0].astype(np.float64)
    tag_id = int(ids[0][0])

    # 3D object points for the tag (counter-clockwise from top-left)
    half = tag_size / 2.0
    obj_pts = np.array([
        [-half,  half, 0],
        [ half,  half, 0],
        [ half, -half, 0],
        [-half, -half, 0],
    ], dtype=np.float64)

    K = np.array(cal["K"], dtype=np.float64)
    dist = np.array(cal["dist"], dtype=np.float64)

    success, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, K, dist,
                                         flags=cv2.SOLVEPNP_IPPE_SQUARE)
    if not success:
        return jsonify(ok=False, error="solvePnP failed"), 500

    R, _ = cv2.Rodrigues(rvec)

    # Reprojection error
    proj, _ = cv2.projectPoints(obj_pts, rvec, tvec, K, dist)
    rpe = float(cv2.norm(img_pts.reshape(-1, 2), proj.reshape(-1, 2), cv2.NORM_L2) / 4)

    # Generate annotated thumbnail
    thumb = frame.copy()
    cv2.aruco.drawDetectedMarkers(thumb, corners, ids)
    cv2.drawFrameAxes(thumb, K, dist, rvec, tvec, tag_size * 0.5)
    thumb = cv2.resize(thumb, (320, 180))
    _, tbuf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
    thumb_b64 = base64.b64encode(tbuf.tobytes()).decode()

    result = {
        "tag_id": tag_id,
        "R": R.tolist(),
        "t": tvec.flatten().tolist(),
        "rvec": rvec.flatten().tolist(),
        "rpe": round(rpe, 4),
        "tag_size": tag_size,
        "thumbnail": thumb_b64,
    }

    with lock:
        state["extrinsic"] = result

    return jsonify(ok=True, result=result)


# ═══════════════════════════════════════════════════════════════════
#  ROUTES — MANUAL ADJUSTMENT
# ═══════════════════════════════════════════════════════════════════
@app.route("/api/adjust/intrinsic", methods=["POST"])
def adjust_intrinsic():
    """Manually override intrinsic parameters."""
    data = request.json
    with lock:
        if state["calibration"] is None:
            return jsonify(ok=False, error="No calibration to adjust"), 400
        cal = state["calibration"]
        for key in ["fx", "fy", "cx", "cy", "k1", "k2", "p1", "p2"]:
            if key in data:
                cal[key] = float(data[key])
        # Rebuild K and dist arrays
        cal["K"] = [
            [cal["fx"], 0, cal["cx"]],
            [0, cal["fy"], cal["cy"]],
            [0, 0, 1],
        ]
        cal["dist"] = [[cal["k1"], cal["k2"], cal["p1"], cal["p2"],
                         cal.get("k3", 0)]]
        state["calibration"] = cal
    return jsonify(ok=True, result=cal)


@app.route("/api/adjust/extrinsic", methods=["POST"])
def adjust_extrinsic():
    """Manually override extrinsic parameters via Euler-ish rvec + t."""
    data = request.json
    with lock:
        if state["extrinsic"] is None:
            return jsonify(ok=False, error="No extrinsic to adjust"), 400
        ext = state["extrinsic"]
        if "rvec" in data:
            ext["rvec"] = [float(v) for v in data["rvec"]]
            R, _ = cv2.Rodrigues(np.array(ext["rvec"], dtype=np.float64))
            ext["R"] = R.tolist()
        if "t" in data:
            ext["t"] = [float(v) for v in data["t"]]
        state["extrinsic"] = ext
    return jsonify(ok=True, result=ext)


# ═══════════════════════════════════════════════════════════════════
#  ROUTES — HAND-EYE CALIBRATION
# ═══════════════════════════════════════════════════════════════════
@app.route("/api/handeye/config", methods=["POST"])
def set_handeye_config():
    """Set hand-eye configuration (eye-in-hand or eye-to-hand)."""
    data = request.json or {}
    config = data.get("config", "eye-in-hand")
    tag_size = data.get("tag_size", APRILTAG_SIZE)
    with lock:
        state["handeye_config"] = config
        state["handeye_tag_size"] = tag_size
    return jsonify(ok=True, config=config, tag_size=tag_size)


@app.route("/api/handeye/pair", methods=["POST"])
def add_handeye_pair():
    """Capture current tag pose and record user-provided EE pose as a pair."""
    with lock:
        cal = state["calibration"]
        tag_sz = state["handeye_tag_size"]
    if cal is None:
        return jsonify(ok=False, error="Run intrinsic calibration first"), 400

    data = request.json or {}
    ee_pose = data.get("ee_pose")  # [x,y,z, rx,ry,rz] in meters+radians
    if ee_pose is None or len(ee_pose) != 6:
        return jsonify(ok=False,
                       error="Provide ee_pose as [x, y, z, rx, ry, rz] (meters, radians)"), 400

    cam = open_camera()
    ret, frame = cam.read()
    if not ret:
        return jsonify(ok=False, error="Camera read failed"), 500

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = april_detector.detectMarkers(gray)
    if ids is None or len(ids) == 0:
        return jsonify(ok=False, error="No AprilTag detected — keep tag visible"), 400

    img_pts = corners[0][0].astype(np.float64)
    half = tag_sz / 2.0
    obj_pts = np.array([
        [-half,  half, 0], [ half,  half, 0],
        [ half, -half, 0], [-half, -half, 0],
    ], dtype=np.float64)

    K = np.array(cal["K"], dtype=np.float64)
    dist = np.array(cal["dist"], dtype=np.float64)

    success, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, K, dist,
                                         flags=cv2.SOLVEPNP_IPPE_SQUARE)
    if not success:
        return jsonify(ok=False, error="solvePnP failed on tag"), 500

    # Parse EE pose → rotation matrix + translation
    x, y, z, rx, ry, rz = [float(v) for v in ee_pose]
    ee_rvec = np.array([rx, ry, rz], dtype=np.float64)
    ee_R, _ = cv2.Rodrigues(ee_rvec)
    ee_t = np.array([x, y, z], dtype=np.float64)

    # Generate thumbnail
    thumb = frame.copy()
    cv2.aruco.drawDetectedMarkers(thumb, corners, ids)
    cv2.drawFrameAxes(thumb, K, dist, rvec, tvec, tag_sz * 0.5)
    thumb = cv2.resize(thumb, (320, 180))
    _, tbuf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
    thumb_b64 = base64.b64encode(tbuf.tobytes()).decode()

    pair = {
        "cam_rvec": rvec.flatten().tolist(),
        "cam_tvec": tvec.flatten().tolist(),
        "ee_R": ee_R.tolist(),
        "ee_t": ee_t.tolist(),
        "ee_pose_input": ee_pose,
        "thumbnail": thumb_b64,
    }

    with lock:
        state["handeye_pairs"].append(pair)
        n = len(state["handeye_pairs"])

    return jsonify(ok=True, num_pairs=n, thumbnail=thumb_b64)


@app.route("/api/handeye/clear", methods=["POST"])
def clear_handeye():
    with lock:
        state["handeye_pairs"] = []
        state["touchpoint_pairs"] = []
        state["handeye"] = None
    return jsonify(ok=True)


@app.route("/api/touchpoint/pair", methods=["POST"])
def add_touchpoint_pair():
    """Capture tag center in camera frame + user-provided TCP position as a point pair."""
    with lock:
        cal = state["calibration"]
        tag_sz = state["handeye_tag_size"]
    if cal is None:
        return jsonify(ok=False, error="Run intrinsic calibration first"), 400

    data = request.json or {}
    tcp_pos = data.get("tcp_pos")  # [x, y, z] in meters
    if tcp_pos is None or len(tcp_pos) != 3:
        return jsonify(ok=False,
                       error="Provide tcp_pos as [x, y, z] in meters"), 400

    cam = open_camera()
    ret, frame = cam.read()
    if not ret:
        return jsonify(ok=False, error="Camera read failed"), 500

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = april_detector.detectMarkers(gray)
    if ids is None or len(ids) == 0:
        return jsonify(ok=False, error="No AprilTag detected — keep tag visible"), 400

    img_pts = corners[0][0].astype(np.float64)
    half = tag_sz / 2.0
    obj_pts = np.array([
        [-half,  half, 0], [ half,  half, 0],
        [ half, -half, 0], [-half, -half, 0],
    ], dtype=np.float64)

    K = np.array(cal["K"], dtype=np.float64)
    dist = np.array(cal["dist"], dtype=np.float64)

    success, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, K, dist,
                                         flags=cv2.SOLVEPNP_IPPE_SQUARE)
    if not success:
        return jsonify(ok=False, error="solvePnP failed — tag may be at bad angle"), 500

    # Tag center in camera frame = tvec (since tag origin is at center)
    cam_pt = tvec.flatten().tolist()
    robot_pt = [float(v) for v in tcp_pos]

    # Generate thumbnail with crosshair at tag center
    thumb = frame.copy()
    cv2.aruco.drawDetectedMarkers(thumb, corners, ids)
    # Project tag center onto image
    center_2d, _ = cv2.projectPoints(np.zeros((1, 3)), rvec, tvec, K, dist)
    cx, cy = int(center_2d[0][0][0]), int(center_2d[0][0][1])
    cv2.drawMarker(thumb, (cx, cy), (50, 210, 120), cv2.MARKER_CROSS, 20, 2)
    cv2.putText(thumb, "TCP", (cx + 12, cy - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (50, 210, 120), 1)
    thumb = cv2.resize(thumb, (320, 180))
    _, tbuf = cv2.imencode('.jpg', thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
    thumb_b64 = base64.b64encode(tbuf.tobytes()).decode()

    pair = {
        "cam_pt": cam_pt,
        "robot_pt": robot_pt,
        "thumbnail": thumb_b64,
    }

    with lock:
        state["touchpoint_pairs"].append(pair)
        n = len(state["touchpoint_pairs"])

    return jsonify(ok=True, num_pairs=n, cam_pt=cam_pt, robot_pt=robot_pt,
                   thumbnail=thumb_b64)


@app.route("/api/calibrate/touchpoint", methods=["POST"])
def calibrate_touchpoint():
    """Rigid body registration via SVD (Procrustes / Arun's method).

    Given point correspondences {p_cam_i, p_robot_i}, finds R, t such that
    p_cam = R @ p_robot + t  (i.e. T_cam←base).
    """
    with lock:
        pairs = state["touchpoint_pairs"][:]

    if len(pairs) < 3:
        return jsonify(ok=False,
                       error=f"Need at least 3 point pairs (have {len(pairs)})"), 400

    cam_pts = np.array([p["cam_pt"] for p in pairs], dtype=np.float64)   # Nx3
    robot_pts = np.array([p["robot_pt"] for p in pairs], dtype=np.float64)  # Nx3
    n = len(pairs)

    # Compute centroids
    centroid_cam = cam_pts.mean(axis=0)
    centroid_robot = robot_pts.mean(axis=0)

    # Center the points
    cam_centered = cam_pts - centroid_cam
    robot_centered = robot_pts - centroid_robot

    # SVD of cross-covariance matrix
    H = robot_centered.T @ cam_centered   # 3x3
    U, S, Vt = np.linalg.svd(H)

    # Ensure proper rotation (det = +1)
    d = np.linalg.det(Vt.T @ U.T)
    sign_matrix = np.diag([1, 1, d])
    R = Vt.T @ sign_matrix @ U.T
    t = centroid_cam - R @ centroid_robot

    # Compute residual (RMSE of point correspondences after transform)
    transformed = (R @ robot_pts.T).T + t
    errors = np.linalg.norm(transformed - cam_pts, axis=1)
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    max_err = float(np.max(errors))
    per_point_errors = errors.tolist()

    # Check collinearity — if points are nearly collinear, warn
    if n >= 3:
        v1 = robot_centered[1] - robot_centered[0]
        v2 = robot_centered[2] - robot_centered[0]
        cross = np.linalg.norm(np.cross(v1, v2))
        span = max(np.linalg.norm(v1), np.linalg.norm(v2), 1e-9)
        collinearity = float(cross / span)
    else:
        collinearity = 0.0

    rvec, _ = cv2.Rodrigues(R)

    result = {
        "R": R.tolist(),
        "t": t.tolist(),
        "rvec": rvec.flatten().tolist(),
        "method": "SVD_PROCRUSTES",
        "config": "touch-point",
        "num_pairs": n,
        "residual": round(rmse, 6),
        "rmse_m": round(rmse, 6),
        "rmse_mm": round(rmse * 1000, 3),
        "max_error_mm": round(max_err * 1000, 3),
        "per_point_errors_mm": [round(e * 1000, 3) for e in per_point_errors],
        "collinearity_score": round(collinearity, 4),
        "all_methods": {
            "SVD_PROCRUSTES": {
                "R": R.tolist(),
                "t": t.tolist(),
                "rvec": rvec.flatten().tolist(),
                "residual": round(rmse, 6),
            }
        },
    }

    if collinearity < 0.05:
        result["warning"] = ("Points are nearly collinear — the rotation around "
                             "the line axis is poorly constrained. Add points that "
                             "are spread in 3D, not just along a line.")

    with lock:
        state["handeye"] = result

    return jsonify(ok=True, result=result)


@app.route("/api/calibrate/handeye", methods=["POST"])
def calibrate_handeye():
    """Run cv2.calibrateHandEye on collected pairs."""
    with lock:
        pairs = state["handeye_pairs"][:]
        config = state["handeye_config"]

    if len(pairs) < 3:
        return jsonify(ok=False,
                       error=f"Need at least 3 pose pairs (have {len(pairs)})"), 400

    # Build input arrays
    R_gripper2base_list = []  # or R_base2gripper for eye-to-hand
    t_gripper2base_list = []
    R_target2cam_list = []
    t_target2cam_list = []

    for p in pairs:
        R_cam, _ = cv2.Rodrigues(np.array(p["cam_rvec"], dtype=np.float64))
        t_cam = np.array(p["cam_tvec"], dtype=np.float64).reshape(3, 1)

        R_ee = np.array(p["ee_R"], dtype=np.float64)
        t_ee = np.array(p["ee_t"], dtype=np.float64).reshape(3, 1)

        R_target2cam_list.append(R_cam)
        t_target2cam_list.append(t_cam)
        R_gripper2base_list.append(R_ee)
        t_gripper2base_list.append(t_ee)

    # Try multiple methods and pick the one with lowest residual
    methods = {
        "TSAI": cv2.CALIB_HAND_EYE_TSAI,
        "PARK": cv2.CALIB_HAND_EYE_PARK,
        "HORAUD": cv2.CALIB_HAND_EYE_HORAUD,
        "ANDREFF": cv2.CALIB_HAND_EYE_ANDREFF,
        "DANIILIDIS": cv2.CALIB_HAND_EYE_DANIILIDIS,
    }

    best_result = None
    best_residual = float("inf")
    all_results = {}

    for name, method in methods.items():
        try:
            if config == "eye-in-hand":
                R_he, t_he = cv2.calibrateHandEye(
                    R_gripper2base_list, t_gripper2base_list,
                    R_target2cam_list, t_target2cam_list,
                    method=method
                )
            else:
                # eye-to-hand: swap roles
                R_he, t_he = cv2.calibrateHandEye(
                    [R.T for R in R_gripper2base_list],
                    [-R.T @ t for R, t in zip(R_gripper2base_list, t_gripper2base_list)],
                    R_target2cam_list, t_target2cam_list,
                    method=method
                )

            # Compute a simple consistency residual
            residual = 0.0
            for i in range(len(pairs)):
                T_ee = np.eye(4)
                T_ee[:3, :3] = R_gripper2base_list[i]
                T_ee[:3, 3] = t_gripper2base_list[i].flatten()

                T_cam = np.eye(4)
                T_cam[:3, :3] = R_target2cam_list[i]
                T_cam[:3, 3] = t_target2cam_list[i].flatten()

                T_he = np.eye(4)
                T_he[:3, :3] = R_he
                T_he[:3, 3] = t_he.flatten()

                # AX = XB consistency: T_ee_i @ T_he should be consistent
                composed = T_ee @ T_he @ T_cam
                # Ideally all composed transforms are the same
                if i == 0:
                    T_ref = composed.copy()
                else:
                    diff = np.linalg.norm(composed - T_ref, 'fro')
                    residual += diff

            rvec_he, _ = cv2.Rodrigues(R_he)
            all_results[name] = {
                "R": R_he.tolist(),
                "t": t_he.flatten().tolist(),
                "rvec": rvec_he.flatten().tolist(),
                "residual": round(float(residual), 6),
            }
            if residual < best_residual:
                best_residual = residual
                best_result = {
                    "R": R_he.tolist(),
                    "t": t_he.flatten().tolist(),
                    "rvec": rvec_he.flatten().tolist(),
                    "method": name,
                    "residual": round(float(residual), 6),
                    "config": config,
                    "num_pairs": len(pairs),
                    "all_methods": all_results,
                }
        except Exception as e:
            all_results[name] = {"error": str(e)}

    if best_result is None:
        return jsonify(ok=False, error="All hand-eye methods failed"), 500

    with lock:
        state["handeye"] = best_result

    return jsonify(ok=True, result=best_result)


@app.route("/api/adjust/handeye", methods=["POST"])
def adjust_handeye():
    """Manually adjust hand-eye transform."""
    data = request.json
    with lock:
        if state["handeye"] is None:
            return jsonify(ok=False, error="No hand-eye calibration to adjust"), 400
        he = state["handeye"]
        if "rvec" in data:
            he["rvec"] = [float(v) for v in data["rvec"]]
            R, _ = cv2.Rodrigues(np.array(he["rvec"], dtype=np.float64))
            he["R"] = R.tolist()
        if "t" in data:
            he["t"] = [float(v) for v in data["t"]]
        state["handeye"] = he
    return jsonify(ok=True, result=he)


# ═══════════════════════════════════════════════════════════════════
#  ROUTES — LOAD (import previous calibration)
# ═══════════════════════════════════════════════════════════════════
@app.route("/api/load", methods=["POST"])
def load_calibration():
    """Import a previously exported calibration JSON into the current state."""
    data = request.json
    if not data:
        return jsonify(ok=False, error="No JSON data provided"), 400

    loaded = {"intrinsic": False, "extrinsic": False, "hand_eye": False}

    # Load intrinsic
    intr = data.get("intrinsic")
    if intr:
        K = intr.get("camera_matrix")
        dist = intr.get("distortion_coefficients")
        params = intr.get("parameters", {})
        img_size = intr.get("image_size", [1280, 720])
        if K and dist:
            cal = {
                "fx": params.get("fx", K[0][0]),
                "fy": params.get("fy", K[1][1]),
                "cx": params.get("cx", K[0][2]),
                "cy": params.get("cy", K[1][2]),
                "k1": params.get("k1", dist[0][0] if isinstance(dist[0], list) else dist[0]),
                "k2": params.get("k2", dist[0][1] if isinstance(dist[0], list) else dist[1]),
                "p1": params.get("p1", dist[0][2] if isinstance(dist[0], list) else dist[2]),
                "p2": params.get("p2", dist[0][3] if isinstance(dist[0], list) else dist[3]),
                "k3": params.get("k3", 0),
                "rpe": intr.get("reprojection_error", 0),
                "per_view_errors": [],
                "image_size": img_size,
                "K": K,
                "dist": dist,
                "num_frames": 0,
            }
            with lock:
                state["calibration"] = cal
            loaded["intrinsic"] = True

    # Load extrinsic (camera-to-tag)
    extr = data.get("extrinsic")
    if extr:
        ext = {
            "tag_id": extr.get("tag_id", 0),
            "R": extr.get("rotation_matrix"),
            "t": extr.get("translation_vector"),
            "rvec": extr.get("rodrigues_vector"),
            "rpe": extr.get("reprojection_error", 0),
            "tag_size": extr.get("tag_size_meters", APRILTAG_SIZE),
            "thumbnail": "",
        }
        if ext["R"] and ext["t"]:
            with lock:
                state["extrinsic"] = ext
            loaded["extrinsic"] = True

    # Load hand-eye / robot-to-camera
    he_data = data.get("hand_eye")
    if he_data:
        he = {
            "R": he_data.get("rotation_matrix"),
            "t": he_data.get("translation_vector"),
            "rvec": he_data.get("rodrigues_vector"),
            "method": he_data.get("method", "imported"),
            "config": he_data.get("configuration", "imported"),
            "residual": he_data.get("residual", 0),
            "num_pairs": he_data.get("num_pose_pairs", 0),
            "all_methods": he_data.get("all_methods", {}),
        }
        if he["R"] and he["t"]:
            # Compute rvec if not provided
            if not he["rvec"]:
                rv, _ = cv2.Rodrigues(np.array(he["R"], dtype=np.float64))
                he["rvec"] = rv.flatten().tolist()
            with lock:
                state["handeye"] = he
                state["handeye_tag_size"] = he_data.get("tag_size_meters",
                                                         APRILTAG_SIZE)
            loaded["hand_eye"] = True

    if not any(loaded.values()):
        return jsonify(ok=False, error="No valid calibration data found in JSON"), 400

    return jsonify(ok=True, loaded=loaded)


# ═══════════════════════════════════════════════════════════════════
#  ROUTES — EXPORT
# ═══════════════════════════════════════════════════════════════════
@app.route("/api/export")
def export_calibration():
    with lock:
        cal = state["calibration"]
        ext = state["extrinsic"]
        he = state["handeye"]

    result = {}
    if cal:
        result["intrinsic"] = {
            "camera_matrix": cal["K"],
            "distortion_coefficients": cal["dist"],
            "image_size": cal["image_size"],
            "reprojection_error": cal["rpe"],
            "parameters": {k: cal[k] for k in ["fx","fy","cx","cy","k1","k2","p1","p2"]},
        }
    if ext:
        result["extrinsic"] = {
            "rotation_matrix": ext["R"],
            "translation_vector": ext["t"],
            "rodrigues_vector": ext["rvec"],
            "tag_id": ext["tag_id"],
            "tag_size_meters": ext["tag_size"],
            "reprojection_error": ext["rpe"],
        }
    if he:
        result["hand_eye"] = {
            "rotation_matrix": he["R"],
            "translation_vector": he["t"],
            "rodrigues_vector": he["rvec"],
            "method": he.get("method"),
            "configuration": he.get("config"),
            "residual": he.get("residual"),
            "num_pose_pairs": he.get("num_pairs"),
            "all_methods": he.get("all_methods"),
        }

    buf = io.BytesIO(json.dumps(result, indent=2).encode())
    return send_file(buf, mimetype='application/json',
                     download_name='calibration.json', as_attachment=True)


# ═══════════════════════════════════════════════════════════════════
#  SNAPSHOT (single frame grab for manual preview)
# ═══════════════════════════════════════════════════════════════════
@app.route("/api/snapshot")
def snapshot():
    """Return a single undistorted JPEG frame."""
    cam = open_camera()
    ret, frame = cam.read()
    if not ret:
        return jsonify(ok=False), 500

    with lock:
        cal = state["calibration"]

    if cal:
        K = np.array(cal["K"])
        dist = np.array(cal["dist"])
        h, w = frame.shape[:2]
        new_K, _ = cv2.getOptimalNewCameraMatrix(K, dist, (w, h), 0.5, (w, h))
        frame = cv2.undistort(frame, K, dist, None, new_K)

    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return send_file(io.BytesIO(buf.tobytes()), mimetype='image/jpeg')


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 56)
    print("  Camera Calibration Tool")
    print("  Open  http://localhost:5000  in your browser")
    print("=" * 56 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
