from pathlib import Path
from typing import Tuple, List # Added List
from PIL import Image
import pytesseract
import fitz  # PyMuPDF
import io

from qr import scan_qr # Import scan_qr

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

def ocr_pdf(path: Path) -> Tuple[str, float, List[str]]:
    """
    Convert PDF to a list of PIL Image objects, one for each page.
    Does NOT perform OCR or QR scanning itself.
    Returns a list of PIL.Image objects.
    """
    images_from_pdf: List[Image.Image] = []
    try:
        doc = fitz.open(path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(alpha=False) # Render without alpha for consistency
            img_bytes = pix.tobytes("png") # Convert to PNG bytes
            # It's good practice to ensure the image mode is suitable for pytesseract, e.g. 'L' or 'RGB'
            pil_image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
            images_from_pdf.append(pil_image)
        doc.close()
        # Debug page show and input were here, now removed as per plan.
    except Exception as e:
        print(f"Error converting PDF {path} page to image: {e}")
    return images_from_pdf
