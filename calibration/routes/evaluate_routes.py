import io

import cv2
import numpy as np
from flask import Blueprint, jsonify, send_file

from calibration.config import charuco_board
from calibration.state import lock, state

evaluate_bp = Blueprint("evaluate", __name__)


def _png(img):
    _, buf = cv2.imencode('.png', img)
    return send_file(io.BytesIO(buf.tobytes()), mimetype='image/png')


@evaluate_bp.route("/api/evaluate/coverage")
def coverage_heatmap():
    with lock:
        acc = state["eval_acc"]
        if acc is not None and acc["coverage"].sum() > 0:
            raw = acc["coverage"].copy()
            use_acc = True
        else:
            use_acc = False
            captures = state["captures"][:]

    if use_acc:
        acc_blur = cv2.GaussianBlur(raw, (61, 61), 0)
        norm = cv2.normalize(acc_blur, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        colored = cv2.applyColorMap(norm, cv2.COLORMAP_INFERNO)
        return _png(colored)

    if not captures:
        return jsonify(ok=False, error="No captures yet"), 400

    w, h = captures[0]["img_size"]
    acc_map = np.zeros((h, w), dtype=np.float32)

    for cap in captures:
        for corner in cap["corners"]:
            cx, cy = int(corner[0][0]), int(corner[0][1])
            cv2.circle(acc_map, (cx, cy), radius=20, color=1.0, thickness=-1)

    acc_map = cv2.GaussianBlur(acc_map, (61, 61), 0)
    norm = cv2.normalize(acc_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    colored = cv2.applyColorMap(norm, cv2.COLORMAP_INFERNO)
    return _png(colored)


@evaluate_bp.route("/api/evaluate/reprojection")
def reprojection_heatmap():
    with lock:
        acc = state["eval_acc"]
        if acc is not None and acc["errors"].sum() > 0:
            raw_err = acc["errors"].copy()
            use_acc = True
        else:
            use_acc = False
            captures = state["captures"][:]
            calibration = state["calibration"]

    if use_acc:
        err_map = cv2.GaussianBlur(raw_err, (41, 41), 0)
        nonzero = err_map[err_map > 0]
        if nonzero.size > 0:
            err_map = np.clip(err_map, 0, 2.0 * float(np.median(nonzero)))
        norm = cv2.normalize(err_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        b = np.zeros_like(norm)
        g = (255 - norm).astype(np.uint8)
        r = norm.astype(np.uint8)
        colored = cv2.merge([b, g, r])
        return _png(colored)

    if not captures:
        return jsonify(ok=False, error="No captures yet"), 400
    if calibration is None:
        return jsonify(ok=False, error="No calibration yet"), 400

    K = np.array(calibration["K"], dtype=np.float64)
    dist = np.array(calibration["dist"], dtype=np.float64)
    w, h = captures[0]["img_size"]
    err_map = np.zeros((h, w), dtype=np.float32)

    for cap in captures:
        obj_pts, img_pts = charuco_board.matchImagePoints(cap["corners"], cap["ids"])
        if obj_pts is None or len(obj_pts) < 4:
            continue
        retval, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, K, dist)
        if not retval:
            continue
        proj, _ = cv2.projectPoints(obj_pts, rvec, tvec, K, dist)
        errors = np.linalg.norm(
            img_pts.reshape(-1, 2) - proj.reshape(-1, 2), axis=1
        )
        for pt, err in zip(img_pts.reshape(-1, 2), errors):
            cv2.circle(err_map, (int(pt[0]), int(pt[1])), radius=25,
                       color=float(err), thickness=-1)

    err_map = cv2.GaussianBlur(err_map, (41, 41), 0)

    # Cap at 2× median of non-zero region to reduce outlier influence
    nonzero = err_map[err_map > 0]
    if nonzero.size > 0:
        err_map = np.clip(err_map, 0, 2.0 * float(np.median(nonzero)))

    norm = cv2.normalize(err_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    # Green (low error) → Red (high error)
    b = np.zeros_like(norm)
    g = (255 - norm).astype(np.uint8)
    r = norm.astype(np.uint8)
    colored = cv2.merge([b, g, r])
    return _png(colored)


@evaluate_bp.route("/api/evaluate/distortion")
def distortion_heatmap():
    with lock:
        calibration = state["calibration"]

    if calibration is None:
        return jsonify(ok=False, error="No calibration yet"), 400

    K = np.array(calibration["K"], dtype=np.float64)
    dist = np.array(calibration["dist"], dtype=np.float64)
    w, h = calibration["image_size"]

    map_xy, _ = cv2.initUndistortRectifyMap(K, dist, None, K, (w, h), cv2.CV_32FC2)
    xx = np.arange(w, dtype=np.float32)[np.newaxis, :]
    yy = np.arange(h, dtype=np.float32)[:, np.newaxis]
    magnitude = np.sqrt((map_xy[:, :, 0] - xx) ** 2 + (map_xy[:, :, 1] - yy) ** 2)

    norm = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    colored = cv2.applyColorMap(norm, cv2.COLORMAP_MAGMA)
    return _png(colored)


@evaluate_bp.route("/api/evaluate/reset", methods=["POST"])
def reset_eval_acc():
    with lock:
        state["eval_acc"] = None
    return jsonify(ok=True)
