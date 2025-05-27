from pathlib import Path
from typing import List
import cv2

# Initialize QRCodeDetector. It's good practice to create it once if used frequently.
# However, for simplicity in this function structure, creating it per call is also acceptable,
# but less performant if scan_qr is called very often.
# For now, let's initialize it globally within the module.
_qr_detector = None

def get_qr_detector():
    global _qr_detector
    if _qr_detector is None:
        _qr_detector = cv2.QRCodeDetector()
    return _qr_detector

def scan_qr(path: Path) -> List[str]:
    """
    Decode all QR codes in the image file using OpenCV's QRCodeDetector.
    Returns a list of decoded strings.
    """
    img_path_str = str(path)
    image = cv2.imread(img_path_str)

    if image is None:
        # Consider logging a warning or raising an error if image can't be read
        return []

    detector = get_qr_detector()
    
    # detectAndDecodeMulti is used for potentially multiple QR codes
    # It returns:
    #   retval: boolean, True if QR codes were found and decoded.
    #   decoded_info: A tuple of decoded strings.
    #   points: A tuple of NumPy arrays, each representing the vertices of a detected QR code.
    #   straight_qrcode: A tuple of rectified QR code images.
    retval, decoded_info, points, straight_qrcode = detector.detectAndDecodeMulti(image)

    if retval and decoded_info is not None:
        # decoded_info can be a tuple of strings. Filter out any empty strings.
        return [info for info in decoded_info if info]
    
    return []
