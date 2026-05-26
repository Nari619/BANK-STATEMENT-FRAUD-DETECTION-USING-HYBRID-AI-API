"""
StatementIQ Component 1 — PDF to Image + Image Quality Gate
Converts image-based PDF pages to images for Vision AI.
Checks image quality BEFORE sending to Claude to avoid wasting money.

No AI. Just image processing.
"""

import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import os


def pdf_pages_to_images(pdf_path: str, dpi: int = 200) -> list[dict]:
    """
    Convert each page of a PDF to a PNG image.
    
    Returns list of dicts:
    {
        "page_number": int,
        "image_bytes": bytes,
        "image_base64": str,     # for sending to Vision API
        "width": int,
        "height": int,
        "size_kb": float,
    }
    """
    results = []
    
    try:
        doc = fitz.open(pdf_path)
        
        for i, page in enumerate(doc):
            # Render page to image at specified DPI
            # Higher DPI = better quality but larger file
            zoom = dpi / 72  # 72 is default PDF DPI
            matrix = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix)
            
            # Convert to PNG bytes
            img_bytes = pixmap.tobytes("png")
            
            # Get dimensions
            width = pixmap.width
            height = pixmap.height
            size_kb = len(img_bytes) / 1024
            
            # Base64 encode for API calls
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            
            results.append({
                "page_number": i + 1,
                "image_bytes": img_bytes,
                "image_base64": img_base64,
                "width": width,
                "height": height,
                "size_kb": round(size_kb, 1),
            })
        
        doc.close()
        
    except Exception as e:
        raise RuntimeError(f"Failed to convert PDF to images: {str(e)}")
    
    return results


def check_image_quality(image_bytes: bytes) -> dict:
    """
    Check if an image is good enough for Vision AI to read.
    Rejects blurry, tiny, or corrupt images BEFORE spending money on API calls.
    
    Returns:
    {
        "is_readable": bool,
        "quality_score": float (0.0 to 1.0),
        "reason": str,
        "details": dict
    }
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return {
            "is_readable": False,
            "quality_score": 0.0,
            "reason": "Cannot open image. File may be corrupt.",
            "details": {},
        }

    width, height = img.size
    details = {}
    scores = {}

    # --- Check 1: Resolution ---
    # Bank statements need enough resolution to read small text
    min_dimension = min(width, height)
    if min_dimension < 200:
        scores["resolution"] = 0.0
        details["resolution"] = f"{width}x{height} — too small to read text"
    elif min_dimension < 500:
        scores["resolution"] = 0.3
        details["resolution"] = f"{width}x{height} — low resolution, may miss details"
    elif min_dimension < 1000:
        scores["resolution"] = 0.7
        details["resolution"] = f"{width}x{height} — acceptable"
    else:
        scores["resolution"] = 1.0
        details["resolution"] = f"{width}x{height} — good resolution"

    # --- Check 2: File size ---
    # Very small files are likely blank or near-blank pages
    size_kb = len(image_bytes) / 1024
    if size_kb < 5:
        scores["file_size"] = 0.0
        details["file_size"] = f"{size_kb:.1f}KB — likely blank page"
    elif size_kb < 20:
        scores["file_size"] = 0.3
        details["file_size"] = f"{size_kb:.1f}KB — very little content"
    else:
        scores["file_size"] = 1.0
        details["file_size"] = f"{size_kb:.1f}KB — sufficient content"

    # --- Check 3: Contrast / variance ---
    # Convert to grayscale and check if there's enough contrast
    # A blank white or black page has zero variance
    gray = img.convert("L")
    pixels = list(gray.getdata())
    
    if len(pixels) == 0:
        scores["contrast"] = 0.0
        details["contrast"] = "No pixel data"
    else:
        mean_val = sum(pixels) / len(pixels)
        variance = sum((p - mean_val) ** 2 for p in pixels) / len(pixels)
        std_dev = variance ** 0.5
        
        if std_dev < 10:
            scores["contrast"] = 0.0
            details["contrast"] = f"StdDev {std_dev:.1f} — nearly blank page"
        elif std_dev < 30:
            scores["contrast"] = 0.4
            details["contrast"] = f"StdDev {std_dev:.1f} — low contrast, may be washed out"
        elif std_dev < 50:
            scores["contrast"] = 0.7
            details["contrast"] = f"StdDev {std_dev:.1f} — acceptable contrast"
        else:
            scores["contrast"] = 1.0
            details["contrast"] = f"StdDev {std_dev:.1f} — good contrast"

    # --- Check 4: Aspect ratio ---
    # Bank statements are portrait (taller than wide) or standard letter
    aspect = width / height if height > 0 else 0
    if aspect < 0.3 or aspect > 3.0:
        scores["aspect"] = 0.3
        details["aspect"] = f"Ratio {aspect:.2f} — unusual for a bank statement"
    else:
        scores["aspect"] = 1.0
        details["aspect"] = f"Ratio {aspect:.2f} — normal document ratio"

    # --- Overall score ---
    weights = {"resolution": 0.35, "file_size": 0.15, "contrast": 0.35, "aspect": 0.15}
    overall = sum(scores.get(k, 0) * w for k, w in weights.items())
    
    # Decision
    is_readable = overall >= 0.35 and scores.get("resolution", 0) > 0 and scores.get("contrast", 0) > 0

    if is_readable:
        reason = "Image quality is sufficient for Vision AI processing."
    else:
        # Build specific rejection reason
        problems = []
        if scores.get("resolution", 1) < 0.3:
            problems.append("resolution too low")
        if scores.get("contrast", 1) < 0.3:
            problems.append("page appears blank or washed out")
        if scores.get("file_size", 1) < 0.3:
            problems.append("file too small, likely blank")
        reason = f"Image rejected: {', '.join(problems)}. Upload a clearer scan."

    img.close()

    return {
        "is_readable": is_readable,
        "quality_score": round(overall, 3),
        "reason": reason,
        "details": details,
    }
