import concurrent.futures
import io

import cv2
from flask import Blueprint, jsonify, request, send_file

from calibration.state import lock, state, release_camera

camera_bp = Blueprint("camera", __name__)


def _probe(idx):
    """Open a camera index, read one frame, return info dict or None."""
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        cap.release()
        return None
    cap.read()  # warm-up frame
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return {"index": idx, "width": w, "height": h}


@camera_bp.route("/api/cameras")
def list_cameras():
    """Probe indices 0–3 in parallel and return available cameras."""
    with lock:
        if state["stream_active"]:
            return jsonify(ok=False, error="Stop the stream before scanning cameras"), 400
    release_camera()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_probe, i): i for i in range(4)}
        for f in concurrent.futures.as_completed(futures, timeout=5):
            try:
                r = f.result()
                if r:
                    results.append(r)
            except Exception:
                pass
    results.sort(key=lambda x: x["index"])
    return jsonify(ok=True, cameras=results)


@camera_bp.route("/api/camera/preview/<int:index>")
def camera_preview(index):
    """Return a single JPEG preview frame from the given camera index."""
    with lock:
        if state["stream_active"]:
            return jsonify(ok=False, error="Stop stream first"), 400
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        return jsonify(ok=False, error=f"Cannot open camera {index}"), 404
    for _ in range(3):
        cap.read()  # discard initial dark/green frames
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return jsonify(ok=False, error="Could not read frame"), 500
    frame = cv2.resize(frame, (320, 180))
    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return send_file(io.BytesIO(buf.tobytes()), mimetype='image/jpeg')


@camera_bp.route("/api/camera/select", methods=["POST"])
def select_camera():
    """Set the active camera index (releases current camera first)."""
    data = request.json or {}
    index = data.get("index")
    if index is None:
        return jsonify(ok=False, error="Provide index"), 400
    with lock:
        if state["stream_active"]:
            return jsonify(ok=False, error="Stop stream first"), 400
    release_camera()
    with lock:
        state["camera_index"] = int(index)
    return jsonify(ok=True, index=int(index))
