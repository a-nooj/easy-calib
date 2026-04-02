import io
import json

import cv2
import numpy as np
from flask import Blueprint, jsonify, request, send_file

from calibration.config import APRILTAG_SIZE
from calibration.state import lock, state, open_camera

io_bp = Blueprint("io", __name__)


@io_bp.route("/api/load", methods=["POST"])
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


@io_bp.route("/api/export")
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


@io_bp.route("/api/snapshot")
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
