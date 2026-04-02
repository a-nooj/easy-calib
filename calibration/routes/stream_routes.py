from flask import Blueprint, Response, jsonify, request

from calibration.state import lock, state
from calibration.stream import generate_frames

stream_bp = Blueprint("stream", __name__)


@stream_bp.route("/api/stream")
def stream():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@stream_bp.route("/api/stream/stop", methods=["POST"])
def stop_stream():
    with lock:
        state["stream_active"] = False
    return jsonify(ok=True)


@stream_bp.route("/api/mode", methods=["POST"])
def set_mode():
    mode = request.json.get("mode", "idle")
    with lock:
        state["mode"] = mode
    return jsonify(ok=True, mode=mode)
