# Camera Calibration Tool

A guided, interactive webapp for **intrinsic** (ChArUco), **extrinsic** (AprilTag), and **hand-eye / robot-to-camera** calibration, powered by OpenCV. Includes a **Debug & Tune** mode for loading previous calibrations and fine-tuning parameters with a live camera feed.

![Python](https://img.shields.io/badge/python-3.9+-blue) ![OpenCV](https://img.shields.io/badge/opencv-4.8+-green) ![Flask](https://img.shields.io/badge/flask-3.0+-lightgrey)

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Plug in your camera

# 3. Run the server
python app.py

# 4. Open in your browser
#    → http://localhost:5000
```

The guided wizard will walk you through every step. Use the **Calibrate** tab for a fresh calibration, or the **Debug & Tune** tab to import and refine a previous one.

---

## Features

### Calibrate Tab — Step-by-Step Wizard

#### Step 1 — Intrinsic Calibration (ChArUco Board)
- Generates a **7×5 ChArUco board** for you to print
- Live webcam feed with **real-time corner detection** overlay
- Capture **4+ frames** from diverse angles and distances
- Runs **Zhang's method** (`cv2.calibrateCamera`) to estimate:
  - Focal lengths (fx, fy)
  - Principal point (cx, cy)
  - Radial distortion (k1, k2)
  - Tangential distortion (p1, p2)
- Reports per-view reprojection error

#### Step 2 — Extrinsic Calibration (AprilTag)
- Generates an **AprilTag 36h11** (ID #0) for you to print
- Live detection with annotated corner labels
- Runs `cv2.solvePnP` to estimate 6-DOF camera pose:
  - Rotation matrix R (3×3)
  - Translation vector t (3×1)
  - Rodrigues vector
- Draws 3D coordinate axes on the tag

#### Step 3 — Hand-Eye / Robot-to-Camera Calibration (Optional)

Three configuration modes, selected from a dropdown that dynamically updates the UI instructions, input fields, and tips:

**Eye-in-Hand** (AX=XB) — Camera mounted on the robot end-effector, AprilTag fixed in the workspace. Enter full 6-DOF EE poses (x, y, z, rx, ry, rz). Runs all 5 OpenCV methods (Tsai, Park, Horaud, Andreff, Daniilidis), picks the best by AX=XB consistency residual. Solves for T_cam←ee.

**Eye-to-Hand** (AX=XB) — Camera fixed, AprilTag attached to the robot end-effector. Same 6-DOF input and multi-method solving, with the gripper poses automatically inverted before passing to `cv2.calibrateHandEye`. Solves for T_cam←base.

**Touch-Point** (SVD Procrustes) — Camera fixed, robot physically touches the AprilTag center with its calibrated TCP. Enter **only position** (x, y, z) — no rotation needed. The tag can move between captures. Solves via rigid-body point registration (Arun's method / SVD). Reports per-point error in mm, RMSE, max error, and a collinearity score that warns if points are too close to a line or plane.

All modes include:
- **Live overlay**: projects the derived transform frame onto the tag in real-time
- Dashed line connecting tag origin to computed robot frame origin
- Pair/point count with progress bar
- Thumbnail grid of captured correspondences

#### Step 4 — Manual Adjustment
- Interactive sliders with **editable numeric inputs** for every parameter
- Type a value directly or drag the slider — both stay in sync
- Live undistorted video preview updates as you adjust
- Covers intrinsics (fx, fy, cx, cy, k1, k2, p1, p2), extrinsics (rvec, t), and hand-eye transform (rvec, t)

#### Step 5 — Export
- Download `calibration.json` with all parameters
- Ready to load directly into OpenCV or any vision pipeline

---

### Debug & Tune Tab

A standalone mode for loading and refining a previous calibration without re-running the wizard. Access it from the top-level tab bar.

**Import** — Paste a `calibration.json` into the text area or upload a file. Accepts the same format that Export produces, so round-tripping is seamless. Loads any combination of intrinsics, extrinsic (camera-to-tag), and hand-eye (robot-to-camera).

**Live Feed** — Starts a debug camera stream showing:
- Undistorted image with current intrinsic parameters
- AprilTag detection with coordinate frame axes
- Tag reprojection error and distance overlaid on the video
- Composed robot-frame overlay (if hand-eye transform is loaded)
- Dot grid projected on the tag plane for visual reference
- Info bar with current fx, fy, cx, cy, k1, k2

**Sliders** — Full set of intrinsic sliders (fx, fy, cx, cy, k1, k2, p1, p2) and robot-to-camera transform sliders (rvec[0–2], tx, ty, tz). All have **editable numeric inputs** — click the value, type a number, press Enter. Sections grey out until the relevant data is loaded.

**Live Metrics** — Polling display showing tag detection status and hand-eye transform state.

**Export** — Download button for the current (possibly tuned) parameters.

---

## Tips for Good Calibration

- **Print at actual size** — disable "fit to page" in your printer settings
- **Measure the real printed dimensions** — enter them in the tool
- **Mount the ChArUco board flat** — tape it to cardboard or a clipboard
- **Capture 8–12 diverse views** — vary angle, distance, and position
- **Cover the whole frame** — corners of the image matter most for distortion estimation
- **Good lighting** — avoid motion blur and harsh reflections
- **Keep it steady** — pause briefly before each capture

### Hand-Eye Specific Tips

- **Eye-in-hand / Eye-to-hand**: Move the robot to significantly different orientations between captures. Include tilts of 15–45° around different axes. 5–8 diverse poses recommended.
- **Touch-point**: Spread points across the workspace. Use **different Z heights** (e.g. tag on table, tag on a box) to avoid coplanar degeneracy. Your TCP calibration accuracy directly determines the result. 4–6 well-spread points is usually sufficient.

---

## Configuration

Edit the constants at the top of `app.py` to match your setup:

```python
CHARUCO_SQUARES_X = 7        # columns
CHARUCO_SQUARES_Y = 5        # rows
CHARUCO_SQUARE_LENGTH = 0.030  # meters (30 mm)
CHARUCO_MARKER_LENGTH = 0.022  # meters (22 mm)
APRILTAG_SIZE = 0.050          # meters (50 mm)
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/stream` | GET | MJPEG video stream with detection overlay |
| `/api/mode` | POST | Set stream mode (idle, charuco, apriltag, undistort, handeye, debug) |
| `/api/board/charuco` | GET | Download ChArUco board PNG |
| `/api/board/apriltag` | GET | Download AprilTag PNG |
| `/api/capture/intrinsic` | POST | Capture frame for intrinsic calibration |
| `/api/calibrate/intrinsic` | POST | Run Zhang's method |
| `/api/capture/extrinsic` | POST | Capture AprilTag + solvePnP |
| `/api/handeye/config` | POST | Set hand-eye config (eye-in-hand / eye-to-hand / touch-point) |
| `/api/handeye/pair` | POST | Add EE pose + tag pose pair (eye-in-hand / eye-to-hand) |
| `/api/handeye/clear` | POST | Clear all hand-eye and touch-point pairs |
| `/api/calibrate/handeye` | POST | Run cv2.calibrateHandEye (all 5 methods) |
| `/api/touchpoint/pair` | POST | Add TCP position + tag pose point pair (touch-point mode) |
| `/api/calibrate/touchpoint` | POST | Run SVD Procrustes point registration |
| `/api/adjust/intrinsic` | POST | Manual intrinsic parameter override |
| `/api/adjust/extrinsic` | POST | Manual extrinsic pose override |
| `/api/adjust/handeye` | POST | Manual hand-eye transform override |
| `/api/load` | POST | Import a previously exported calibration.json |
| `/api/export` | GET | Download calibration.json |
| `/api/status` | GET | Current detection status and pair counts |
| `/api/snapshot` | GET | Single frame grab |

---

## Export Format

The exported `calibration.json` includes whichever sections were calibrated:

```json
{
  "intrinsic": {
    "camera_matrix": [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
    "distortion_coefficients": [[k1, k2, p1, p2, k3]],
    "image_size": [1280, 720],
    "reprojection_error": 0.35,
    "parameters": { "fx": 615, "fy": 615, "cx": 640, "cy": 360, "k1": -0.05, "..." : "..." }
  },
  "extrinsic": {
    "rotation_matrix": [["..."], ["..."], ["..."]],
    "translation_vector": [0.0, 0.0, 0.5],
    "rodrigues_vector": [0.0, 0.0, 0.0]
  },
  "hand_eye": {
    "rotation_matrix": [["..."], ["..."], ["..."]],
    "translation_vector": [0.0, 0.0, 0.5],
    "rodrigues_vector": [0.0, 0.0, 0.0],
    "method": "TSAI",
    "configuration": "eye-in-hand",
    "residual": 0.002,
    "num_pose_pairs": 6,
    "all_methods": { "TSAI": {}, "PARK": {}, "..." : "..." }
  }
}
```

This format is accepted by the `/api/load` endpoint and the Debug & Tune import panel. You can provide `rotation_matrix`, `rodrigues_vector`, or both — if `rodrigues_vector` is missing, it's computed from the rotation matrix automatically.

---

## Requirements

- Python 3.9+
- A USB or built-in camera accessible as device `0`
- A printer (for the calibration targets)
- A ruler or calipers (to measure printed dimensions)
- Optional: A robot arm with accessible EE/TCP pose readout (for hand-eye calibration)
