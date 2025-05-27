from pathlib import Path
from typing import Tuple
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

def ocr_image(path: Path) -> Tuple[str, float]:
    """
    Perform OCR on an image file.
    Returns extracted text and mean confidence.
    """
    image = Image.open(path)
    text = pytesseract.image_to_string(image)
    # Get OCR data to compute confidence scores
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    confs = [int(c) for c in data.get('conf', []) if c != '-1']
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    return text, mean_conf

def ocr_pdf(path: Path) -> Tuple[str, float]:
    """
    Convert PDF to images and perform OCR on each page.
    Returns combined text and mean confidence across all pages.
    """
    text_all = ""
    all_confs = []
    images = convert_from_path(str(path))
    for image in images:
        text = pytesseract.image_to_string(image)
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        confs = [int(c) for c in data.get('conf', []) if c != '-1']
        if confs:
            all_confs.extend(confs)
        text_all += text + "\n"
    mean_conf = sum(all_confs) / len(all_confs) if all_confs else 0.0
    return text_all, mean_conf
