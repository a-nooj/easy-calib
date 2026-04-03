import os
import threading
import time
import cv2

from calibration.config import APRILTAG_SIZE

CAMERA_INDEX = int(os.environ.get("CAMERA_INDEX", 0))
lock = threading.Lock()
camera = None

state = {
    "stream_active": False,
    "camera_index": CAMERA_INDEX,
    "mode": "idle",              # idle | charuco | apriltag | undistort | handeye | debug | evaluate
    "captures": [],              # list of {corners, ids, img_size, thumbnail}
    "calibration": None,         # dict with fx,fy,cx,cy,k1..k5,p1,p2,rpe
    "extrinsic": None,           # dict with R, t, rvec
    "touchpoint_pairs": [],      # list of {cam_pt, robot_pt, thumbnail}
    "handeye": None,             # result: {R, t, method, config}
    "handeye_tag_size": APRILTAG_SIZE,
    "last_detection": {          # updated every frame
        "charuco_count": 0,
        "charuco_enough": False,
        "apriltag_detected": False,
        "apriltag_corners": None,
    },
    "eval_acc": None,            # None or {"coverage": np.zeros, "errors": np.zeros, "img_size": (w,h)}
    # auto-capture
    "auto_capture": False,
    "auto_capture_last": 0.0,          # timestamp of last intrinsic auto-capture
    "auto_capture_flash_until": 0.0,   # show green flash overlay until this time
    "auto_capture_stable_frames": 0,   # consecutive frames with tag detected (for extrinsic auto)
    "auto_capture_tag_size": APRILTAG_SIZE,  # tag size for extrinsic auto-capture
}


def open_camera():
    global camera
    idx = state["camera_index"]
    if camera is None or not camera.isOpened():
        camera = cv2.VideoCapture(idx)
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
