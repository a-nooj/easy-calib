import base64

import cv2
import numpy as np
from flask import Blueprint, jsonify, request

from calibration.config import APRILTAG_SIZE, april_detector
from calibration.state import lock, state, open_camera

extrinsic_bp = Blueprint("extrinsic", __name__)


@extrinsic_bp.route("/api/capture/extrinsic", methods=["POST"])
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


@extrinsic_bp.route("/api/capture/extrinsic/result")
def get_extrinsic_result():
    """Return the current extrinsic calibration result (used by auto-capture polling)."""
    with lock:
        ext = state["extrinsic"]
    if ext is None:
        return jsonify(ok=False, error="No extrinsic calibration"), 404
    return jsonify(ok=True, result=ext)


@extrinsic_bp.route("/api/adjust/extrinsic", methods=["POST"])
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
