from pathlib import Path
from typing import Tuple
from PIL import Image
import pytesseract
import fitz  # PyMuPDF
import io

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
    
    doc = fitz.open(path)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap() 
        img_bytes = pix.tobytes("png")
        
        page_image = Image.open(io.BytesIO(img_bytes))

        #show preview
        page_image.show()

        # wait for user input
        input("Press Enter to continue...")

        text = pytesseract.image_to_string(page_image)
        data = pytesseract.image_to_data(page_image, output_type=pytesseract.Output.DICT)
        confs = [int(c) for c in data.get('conf', []) if c != '-1']
        if confs:
            all_confs.extend(confs)
        text_all += text + "\n"
    
    doc.close()
    mean_conf = sum(all_confs) / len(all_confs) if all_confs else 0.0
    return text_all, mean_conf
