import cv2

# ═══════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════
CHARUCO_SQUARES_X = 7
CHARUCO_SQUARES_Y = 5
CHARUCO_SQUARE_LENGTH = 0.030   # 30 mm
CHARUCO_MARKER_LENGTH = 0.022   # 22 mm
APRILTAG_SIZE = 0.050           # 50 mm (physical printed size)
MIN_CHARUCO_CORNERS = 6         # minimum per frame
MIN_CAPTURES = 4                # minimum frames for calibration

# ═══════════════════════════════════════════════════════════════════
#  OPENCV SETUP
# ═══════════════════════════════════════════════════════════════════
charuco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
charuco_board = cv2.aruco.CharucoBoard(
    (CHARUCO_SQUARES_X, CHARUCO_SQUARES_Y),
    CHARUCO_SQUARE_LENGTH,
    CHARUCO_MARKER_LENGTH,
    charuco_dict,
)
charuco_detector = cv2.aruco.CharucoDetector(charuco_board)

april_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
april_params = cv2.aruco.DetectorParameters()
april_detector = cv2.aruco.ArucoDetector(april_dict, april_params)
