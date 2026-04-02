import io

import cv2
from flask import Blueprint, send_file

from calibration.config import charuco_board, april_dict

board_bp = Blueprint("board", __name__)


@board_bp.route("/api/board/charuco")
def get_charuco_board():
    """Generate a high-res ChArUco board image for printing."""
    img = charuco_board.generateImage((1400, 1000), marginSize=60, borderBits=1)
    _, buf = cv2.imencode('.png', img)
    return send_file(io.BytesIO(buf.tobytes()), mimetype='image/png',
                     download_name='charuco_board.png')


@board_bp.route("/api/board/apriltag")
def get_apriltag_board():
    """Generate AprilTag 36h11 tag #0 for printing."""
    tag_img = cv2.aruco.generateImageMarker(april_dict, 0, 600, borderBits=1)
    # Add white border for printing
    bordered = cv2.copyMakeBorder(tag_img, 80, 80, 80, 80,
                                  cv2.BORDER_CONSTANT, value=255)
    _, buf = cv2.imencode('.png', bordered)
    return send_file(io.BytesIO(buf.tobytes()), mimetype='image/png',
                     download_name='apriltag_36h11_id0.png')
