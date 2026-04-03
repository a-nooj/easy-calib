# Camera Calibration Tool

A guided, interactive webapp for **intrinsic** (ChArUco), **extrinsic** (AprilTag), and **hand-eye / robot-to-camera** calibration, powered by OpenCV. Includes a **Debug & Tune** mode for loading previous calibrations and fine-tuning parameters with a live camera feed.

![Python](https://img.shields.io/badge/python-3.8+-blue) ![OpenCV](https://img.shields.io/badge/opencv-4.8--4.x-green) ![Flask](https://img.shields.io/badge/flask-3.x-lightgrey)

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

**Touch-Point** (SVD Procrustes) — Camera fixed, robot physically touches the AprilTag center with its calibrated TCP. Enter **only position** (x, y, z) — no rotation needed. The tag can move between captures. Solves via rigid-body point registration (Arun's method / SVD). Reports per-point error in mm, RMSE, max error, and a collinearity score that warns if points are too close to a line or plane.

- **Live overlay**: projects the derived transform frame onto the tag in real-time
- Dashed line connecting tag origin to computed robot frame origin
- Point count with progress bar
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

### Evaluate Tab

A quality-assessment tab available after intrinsic calibration. Displays three PNG heatmaps rendered from the captured frames and calibration result:

- **Coverage heatmap** — shows where ChArUco corners landed across all captures (INFERNO colormap). Sparse regions indicate areas where distortion estimation may be weak.
- **Reprojection error heatmap** — per-corner reprojection error across the image plane (green = low, red = high). Helps identify spatial bias in the calibration.
- **Distortion magnitude heatmap** — pixel displacement magnitude of the undistortion map across the full image (MAGMA colormap). Shows how aggressively the lens model bends each region.

Heatmaps update live as new frames are captured (accumulated in `eval_acc` state). Use **Reset** to clear the accumulator and start fresh without discarding the calibration.

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

### Hand-Eye (Touch-Point) Tips

- Spread points across the workspace — don't cluster them in one area
- Use **different Z heights** (e.g. tag on a table, then on a box) to avoid coplanar degeneracy
- Your TCP calibration accuracy directly determines the result
- 4–6 well-spread points is usually sufficient; the collinearity score will warn if more diversity is needed

---

## Configuration

Edit the constants at the top of `calibration/config.py` to match your setup:

```python
CHARUCO_SQUARES_X = 7        # columns
CHARUCO_SQUARES_Y = 5        # rows
CHARUCO_SQUARE_LENGTH = 0.030  # meters (30 mm)
CHARUCO_MARKER_LENGTH = 0.022  # meters (22 mm)
APRILTAG_SIZE = 0.050          # meters (50 mm)
```

### Camera index

By default the app opens device `0`. If your target camera is on a different index, set the `CAMERA_INDEX` environment variable before starting:

```bash
CAMERA_INDEX=2 python app.py
```

Or with Docker:

```yaml
# docker-compose.yml
services:
  app:
    environment:
      - CAMERA_INDEX=2
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/stream` | GET | MJPEG video stream with detection overlay |
| `/api/stream/stop` | POST | Stop the active camera stream |
| `/api/mode` | POST | Set stream mode (idle, charuco, apriltag, undistort, handeye, debug) |
| `/api/board/charuco` | GET | Download ChArUco board PNG |
| `/api/board/apriltag` | GET | Download AprilTag PNG |
| `/api/capture/intrinsic` | POST | Capture frame for intrinsic calibration |
| `/api/capture/clear` | POST | Clear all intrinsic capture frames |
| `/api/capture/delete` | POST | Remove a single capture frame by index |
| `/api/calibrate/intrinsic` | POST | Run Zhang's method |
| `/api/capture/extrinsic` | POST | Capture AprilTag + solvePnP |
| `/api/handeye/config` | POST | Set touch-point tag size |
| `/api/handeye/clear` | POST | Clear touch-point pairs and hand-eye result |
| `/api/touchpoint/pair` | POST | Add TCP position + tag pose point pair |
| `/api/calibrate/touchpoint` | POST | Run SVD Procrustes point registration |
| `/api/adjust/intrinsic` | POST | Manual intrinsic parameter override |
| `/api/adjust/extrinsic` | POST | Manual extrinsic pose override |
| `/api/adjust/handeye` | POST | Manual hand-eye transform override |
| `/api/evaluate/coverage` | GET | Coverage heatmap PNG |
| `/api/evaluate/reprojection` | GET | Reprojection error heatmap PNG |
| `/api/evaluate/distortion` | GET | Distortion magnitude heatmap PNG |
| `/api/evaluate/reset` | POST | Clear the live evaluation accumulator |
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
    "method": "touch-point",
    "configuration": "touch-point",
    "residual": 0.002,
    "num_pose_pairs": 5
  }
}
```

This format is accepted by the `/api/load` endpoint and the Debug & Tune import panel. You can provide `rotation_matrix`, `rodrigues_vector`, or both — if `rodrigues_vector` is missing, it's computed from the rotation matrix automatically.

---

## Docker Deployment

> **Platform note:** USB/V4L2 camera passthrough (`/dev/video*`) only works on **Linux**. On macOS or Windows you can still build and run the container, but you'll need to stream frames from a network camera or mock source — the host USB device won't be forwarded.

### Option A — Docker Compose (recommended)

A `docker-compose.yml` is included. It starts two services:

- **`app`** — the Flask server, with `/dev/video0` passed through for camera access
- **`tunnel`** — a Cloudflare Tunnel that exposes the app publicly over HTTPS (no account required)

```bash
# Build and start both services
docker compose up --build

# Run in the background
docker compose up --build -d

# View the public tunnel URL (printed in the tunnel service logs)
docker compose logs tunnel

# Stop everything
docker compose down
```

Open `http://localhost:5000` locally, or use the `trycloudflare.com` URL from the tunnel logs to access from another device.

**Different camera index:**

```yaml
# docker-compose.yml
services:
  app:
    devices:
      - /dev/video2:/dev/video0   # map host device 2 → container device 0
    environment:
      - CAMERA_INDEX=0
```

**Skip the tunnel** (local access only):

```bash
docker compose up --build app
```

### Option B — Standalone Docker

```bash
# Build the image
docker build -t calibration-tool .

# Run with camera passthrough (Linux)
docker run --rm \
  --device /dev/video0:/dev/video0 \
  -p 5000:5000 \
  calibration-tool

# Different camera index
docker run --rm \
  --device /dev/video2:/dev/video0 \
  -e CAMERA_INDEX=0 \
  -p 5000:5000 \
  calibration-tool
```

Then open `http://localhost:5000`.

---

## Requirements

- Python 3.9+
- A USB or built-in camera accessible as device `0`
- A printer (for the calibration targets)
- A ruler or calipers (to measure printed dimensions)
- Optional: A robot arm with accessible EE/TCP pose readout (for hand-eye calibration)
