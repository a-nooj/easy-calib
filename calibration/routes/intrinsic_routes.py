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


def _make_frame_viz(thumb_b64, img_pts, proj_pts, img_size):
    """Overlay detected corners (green) and reprojected corners (red) on a thumbnail.

    The thumbnail is upscaled 2× before drawing so markers remain sharp when the
    image is enlarged in the lightbox; the grid displays it scaled down via CSS.
    """
    thumb_arr = np.frombuffer(base64.b64decode(thumb_b64), dtype=np.uint8)
    small = cv2.imdecode(thumb_arr, cv2.IMREAD_COLOR)
    # Upscale 2× for crisp rendering at lightbox size
    viz = cv2.resize(small, (small.shape[1] * 2, small.shape[0] * 2),
                     interpolation=cv2.INTER_LINEAR)
    h, w = viz.shape[:2]
    sx, sy = w / img_size[0], h / img_size[1]
    for det, proj in zip(img_pts, proj_pts):
        dx, dy = int(det[0][0] * sx), int(det[0][1] * sy)
        px, py = int(proj[0][0] * sx), int(proj[0][1] * sy)
        cv2.line(viz, (dx, dy), (px, py), (0, 210, 255), 1)
        cv2.circle(viz, (dx, dy), 6, (50, 220, 50), -1)
        cv2.drawMarker(viz, (px, py), (0, 60, 230), cv2.MARKER_CROSS, 14, 1)
    _, buf = cv2.imencode('.jpg', viz, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return base64.b64encode(buf.tobytes()).decode()


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
        det["auto_capture"] = state["auto_capture"]
        det["auto_capture_stable_pct"] = min(
            1.0, state["auto_capture_stable_frames"] / 15.0)
        det["camera_index"] = state["camera_index"]
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
            "thumbnail": thumb_b64,
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


@intrinsic_bp.route("/api/capture/auto", methods=["POST"])
def set_auto_capture():
    """Enable or disable auto-capture mode for intrinsic or extrinsic."""
    data = request.json or {}
    enabled = bool(data.get("enabled", False))
    tag_size = float(data.get("tag_size", state["auto_capture_tag_size"]))
    mode = data.get("mode", "intrinsic")  # "intrinsic" | "extrinsic"
    with lock:
        state["auto_capture"] = enabled
        state["auto_capture_tag_size"] = tag_size
        state["auto_capture_stable_frames"] = 0
        # When enabling extrinsic auto-capture, clear any previous extrinsic result
        # so has_extrinsic transitions from false→true when auto fires
        if enabled and mode == "extrinsic":
            state["extrinsic"] = None
    return jsonify(ok=True, auto_capture=enabled)


@intrinsic_bp.route("/api/capture/latest_thumbnail")
def latest_thumbnail():
    """Return the thumbnail of the most recent intrinsic capture."""
    with lock:
        caps = state["captures"]
        n = len(caps)
    if n == 0:
        return jsonify(ok=False, error="No captures"), 404
    return jsonify(ok=True, thumbnail=caps[-1]["thumbnail"], num_captures=n)


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
    valid_capture_indices = []
    img_size = captures[0]["img_size"]

    for cap_idx, cap in enumerate(captures):
        obj_pts, img_pts = charuco_board.matchImagePoints(cap["corners"], cap["ids"])
        if obj_pts is not None and len(obj_pts) >= MIN_CHARUCO_CORNERS:
            all_obj_pts.append(obj_pts)
            all_img_pts.append(img_pts)
            valid_capture_indices.append(cap_idx)

    if len(all_obj_pts) < MIN_CAPTURES:
        return jsonify(ok=False, error="Not enough valid captures after filtering"), 400

    try:
        ret, K, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
            all_obj_pts, all_img_pts, img_size, None, None,
            flags=cv2.CALIB_FIX_K3 | cv2.CALIB_FIX_K4 | cv2.CALIB_FIX_K5
        )
    except cv2.error as e:
        return jsonify(ok=False, error=f"Calibration failed: {str(e)}"), 500

    # Compute per-view reprojection errors and generate overlay thumbnails
    per_view_errors = []
    frame_viz = []
    for i in range(len(all_obj_pts)):
        proj, _ = cv2.projectPoints(all_obj_pts[i], rvecs[i], tvecs[i], K, dist_coeffs)
        proj = proj.reshape(-1, 1, 2)
        err = cv2.norm(all_img_pts[i], proj, cv2.NORM_L2) / len(proj)
        per_view_errors.append(round(float(err), 4))
        cap = captures[valid_capture_indices[i]]
        frame_viz.append(_make_frame_viz(cap["thumbnail"], all_img_pts[i], proj, img_size))

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
        "capture_indices": valid_capture_indices,
        "frame_viz": frame_viz,
    }

    with lock:
        state["calibration"] = result

    return jsonify(ok=True, result=result)


@intrinsic_bp.route("/api/capture/delete", methods=["POST"])
def delete_capture():
    """Remove a single capture by index and invalidate calibration."""
    data = request.json or {}
    idx = int(data.get("idx", -1))
    with lock:
        if idx < 0 or idx >= len(state["captures"]):
            return jsonify(ok=False, error="Invalid index"), 400
        state["captures"].pop(idx)
        state["calibration"] = None
        n = len(state["captures"])
    return jsonify(ok=True, num_captures=n)


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
