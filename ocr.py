from pathlib import Path
from typing import Tuple  # Added List
from PIL import Image
import pytesseract

import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageOps
from matplotlib import pyplot as plt


def display_image(title, image):
    # Get image dimensions (height, width)
    if len(image.shape) == 2:  # Grayscale
        img_height, img_width = image.shape
    else:  # Color
        img_height, img_width, _ = image.shape

    # Get DPI for the figure
    dpi = plt.rcParams['figure.dpi']

    # Calculate figure size in inches
    figsize_width = img_width / dpi
    figsize_height = img_height / dpi

    plt.figure(figsize=(figsize_width, figsize_height))
    if len(image.shape) == 2:  # Grayscale
        plt.imshow(image, cmap='gray')
    else:  # Color
        plt.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    plt.title(title)
    plt.axis('off')
    plt.show()

def preprocess_image_for_ocr(pil_image):
    """
    Preprocess a PIL image to enhance OCR accuracy.
    Steps:
    1. Convert to grayscale.
    2. Apply median filter to reduce noise.
    3. Normalize the image intensity.
    4. Convert to OpenCV format for further processing.
    5. Apply adaptive thresholding.
    6. Deskew the image to correct any rotation.
    7. Convert back to PIL image.
    """

    # Load the image using PIL and convert to OpenCV format

    cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    display_image('Original Image', cv_image)

    # Step 1: Convert to Grayscale
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    display_image('Grayscale Image', gray)

    # # Step 2: Apply Median Filter to Reduce Noise
    # median = cv2.medianBlur(gray, 3)
    # display_image('Median Filtered Image', median)

    # Step 3: Normalize the Image Intensity
    normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    display_image('Normalized Image', normalized)

    # Step 4: Adaptive Thresholding
    thresh = cv2.adaptiveThreshold(
        normalized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 45, 30
    )

    display_image('Adaptive Thresholding', thresh)

    # Step 6: Convert Back to PIL Image (if needed)
    final_image = Image.fromarray(thresh)

    return final_image


def ocr_image(image: Image.Image) -> Tuple[str, float]:
    """
    Perform OCR on an image file.
    Returns extracted text and mean confidence.
    """

    image = preprocess_image_for_ocr(image)
    # preview
    image.show()
    # wait
    input("Press Enter to continue...")

    text = pytesseract.image_to_string(image)
    # Get OCR data to compute confidence scores
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    confs = [int(c) for c in data.get('conf', []) if c != '-1']
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    return text, mean_conf
