from pathlib import Path
from typing import List
import cv2
from qreader import QReader

def scan_qr(path: Path) -> List[str]:
    """
    Decode all QR codes in the image file and return list of decoded strings.
    """
    image = cv2.imread(str(path))
    if image is None:
        return []

    qreader_instance = QReader()
    decoded_results = qreader_instance.decode(image=image)

    if decoded_results is None:
        return []
    
    if isinstance(decoded_results, str):
        # If it's a non-empty string, put it in a list. If empty, treat as no result.
        return [decoded_results] if decoded_results else []
    elif isinstance(decoded_results, list):
        # Filter out any None or empty strings from the list, similar to `if obj.data`
        return [item for item in decoded_results if isinstance(item, str) and item]
    
    return [] # Fallback for unexpected types or if decoded_results is not str/list
