import base64

import cv2
import numpy as np
from flask import Blueprint, jsonify, request

from calibration.config import (
    MIN_CHARUCO_CORNERS, MIN_CAPTURES,
    charuco_detector, charuco_board,
)
from calibration.state import lock, state, open_camera

intrinsic_bp = Blueprint("intrinsic", __name__)


@intrinsic_bp.route("/api/status")
def get_status():
    with lock:
        det = state["last_detection"].copy()
        det["num_captures"] = len(state["captures"])
        det["has_calibration"] = state["calibration"] is not None
        det["has_extrinsic"] = state["extrinsic"] is not None
        det["has_handeye"] = state["handeye"] is not None
        det["num_touchpoint_pairs"] = len(state["touchpoint_pairs"])
        det["mode"] = state["mode"]
    return jsonify(det)


@intrinsic_bp.route("/api/capture/intrinsic", methods=["POST"])
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


@intrinsic_bp.route("/api/capture/clear", methods=["POST"])
def clear_captures():
    with lock:
        state["captures"] = []
        state["calibration"] = None
    return jsonify(ok=True)


@intrinsic_bp.route("/api/calibrate/intrinsic", methods=["POST"])
def calibrate_intrinsic():
    """Run Zhang's method via OpenCV."""
    with lock:
        captures = state["captures"][:]

    if len(captures) < MIN_CAPTURES:
        return jsonify(ok=False,
                       error=f"Need at least {MIN_CAPTURES} captures (have {len(captures)})"), 400

    all_obj_pts = []
    all_img_pts = []
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


@intrinsic_bp.route("/api/adjust/intrinsic", methods=["POST"])
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
