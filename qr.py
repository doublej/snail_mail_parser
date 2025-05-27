from pathlib import Path
from typing import List
from pyzbar.pyzbar import decode
from PIL import Image

def scan_qr(path: Path) -> List[str]:
    """
    Decode all QR codes in the image file and return list of decoded strings.
    """
    image = Image.open(path)
    decoded_objects = decode(image)
    return [obj.data.decode('utf-8') for obj in decoded_objects if obj.data]
