import os
import cv2
import numpy as np
from pdf2image import convert_from_path
from config import POPPLER_PATH, UPLOAD_DIR, IS_WINDOWS

def process_bulk_pdf(pdf_path: str, batch_id: str) -> list:
    """
    Converts a multi-page PDF into grayscale images optimized for vision model ingestion.
    Returns a list of processed image file paths.
    """
    batch_output_dir = os.path.join(UPLOAD_DIR, batch_id)
    os.makedirs(batch_output_dir, exist_ok=True)

    convert_kwargs = {"dpi": 200}
    if IS_WINDOWS:
        convert_kwargs["poppler_path"] = POPPLER_PATH

    pages = convert_from_path(pdf_path, **convert_kwargs)
    print(f"Extracted {len(pages)} pages from PDF.")

    processed_image_paths = []

    for index, page in enumerate(pages):
        img = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)

        # Force landscape scans into portrait orientation
        h, w = img.shape[:2]
        if w > h:
            # img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            h, w = img.shape[:2]

        # Downscale if larger than 1600px on longest side
        max_dim = 1600
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        out_path = os.path.join(batch_output_dir, f"page_{index}.jpg")
        cv2.imwrite(out_path, gray)
        processed_image_paths.append(out_path)

    return processed_image_paths
