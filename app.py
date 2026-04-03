from flask import Flask

from calibration.routes.pages import pages_bp
from calibration.routes.stream_routes import stream_bp
from calibration.routes.board_routes import board_bp
from calibration.routes.camera_routes import camera_bp
from calibration.routes.intrinsic_routes import intrinsic_bp
from calibration.routes.extrinsic_routes import extrinsic_bp
from calibration.routes.handeye_routes import handeye_bp
from calibration.routes.io_routes import io_bp
from calibration.routes.evaluate_routes import evaluate_bp

app = Flask(__name__)
for bp in [pages_bp, stream_bp, board_bp, camera_bp, intrinsic_bp,
           extrinsic_bp, handeye_bp, io_bp, evaluate_bp]:
    app.register_blueprint(bp)

if __name__ == "__main__":
    print("\n" + "=" * 56)
    print("  Camera Calibration Tool")
    print("  Open  http://localhost:5000  in your browser")
    print("=" * 56 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
