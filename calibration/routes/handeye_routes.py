import base64

import cv2
import numpy as np
from flask import Blueprint, jsonify, request

from calibration.config import APRILTAG_SIZE, april_detector
from calibration.state import lock, state, open_camera

handeye_bp = Blueprint("handeye", __name__)


@handeye_bp.route("/api/handeye/config", methods=["POST"])
def set_handeye_config():
    """Set hand-eye tag size."""
    data = request.json or {}
    tag_size = data.get("tag_size", APRILTAG_SIZE)
    with lock:
        state["handeye_tag_size"] = tag_size
    return jsonify(ok=True, tag_size=tag_size)


@handeye_bp.route("/api/handeye/clear", methods=["POST"])
def clear_handeye():
    with lock:
        state["touchpoint_pairs"] = []
        state["handeye"] = None
    return jsonify(ok=True)


@handeye_bp.route("/api/touchpoint/pair", methods=["POST"])
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


@handeye_bp.route("/api/calibrate/touchpoint", methods=["POST"])
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


@handeye_bp.route("/api/adjust/handeye", methods=["POST"])
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
