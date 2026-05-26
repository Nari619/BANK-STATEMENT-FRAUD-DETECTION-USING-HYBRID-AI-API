"""
StatementIQ Component 1 — Extraction Orchestrator
The brain of Component 1. Decides which path to take:

    PDF comes in
        │
        ├── Text extraction works? → YES → use it. Done. No AI.
        │
        ├── Text extraction fails? → Is the image readable?
        │                                 │
        │                                 ├── YES → Claude Vision. Done.
        │                                 │
        │                                 └── NO → Reject. 
        │                                          No AI cost wasted.
"""

import os
import uuid
from datetime import datetime

from extractors.pdf_text import extract_text_from_pdf
from extractors.vision_fallback import extract_text_with_vision, estimate_vision_cost
from quality.text_scorer import score_text_quality
from quality.image_gate import pdf_pages_to_images, check_image_quality
from models import ExtractionMethod, PageResult, ExtractionResponse, RejectionResponse


def process_statement(pdf_path: str, api_key: str | None = None) -> ExtractionResponse | RejectionResponse:
    """
    Main entry point. Takes a PDF path, returns extracted text.
    Decides automatically whether to use AI or not.
    Uses Anthropic API key for Claude Vision fallback.
    """
    if api_key is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
    statement_id = f"stmt_{uuid.uuid4().hex[:8]}"
    filename = os.path.basename(pdf_path)
    warnings = []

    # =========================================================
    # STEP 1: Try normal text extraction (NO AI)
    # =========================================================
    text_results = extract_text_from_pdf(pdf_path)
    
    if not text_results:
        return RejectionResponse(
            statement_id=statement_id,
            filename=filename,
            reason="Could not open PDF file. File may be corrupt or password-protected.",
            suggestion="Upload an unprotected PDF file.",
        )

    # =========================================================
    # STEP 2: Score text quality for each page
    # =========================================================
    page_scores = []
    all_pages_usable = True
    usable_pages = []
    unusable_pages = []

    for page_data in text_results:
        quality = score_text_quality(page_data["text"])
        page_scores.append({
            **page_data,
            "quality": quality,
        })
        
        if quality["is_usable"]:
            usable_pages.append(page_data)
        else:
            unusable_pages.append(page_data)
            all_pages_usable = False

    # =========================================================
    # PATH A: All pages extracted cleanly → No AI needed
    # =========================================================
    if all_pages_usable:
        pages = []
        for ps in page_scores:
            pages.append(PageResult(
                page_number=ps["page_number"],
                text=ps["text"],
                method=ExtractionMethod.TEXT,
                text_quality_score=ps["quality"]["score"],
                char_count=ps["char_count"],
                line_count=ps["line_count"],
            ))
        
        full_text = "\n\n--- PAGE BREAK ---\n\n".join(p.text for p in pages)
        avg_score = sum(p.text_quality_score for p in pages) / len(pages) if pages else 0

        return ExtractionResponse(
            statement_id=statement_id,
            filename=filename,
            total_pages=len(pages),
            extraction_method=ExtractionMethod.TEXT,
            ai_used=False,
            ai_cost_estimate_usd=0.0,
            pages=pages,
            full_text=full_text,
            text_quality_score=round(avg_score, 3),
            warnings=warnings,
        )

    # =========================================================
    # Text extraction failed for some/all pages.
    # Now decide: can Vision AI read them?
    # =========================================================
    
    # =========================================================
    # STEP 3: Convert PDF to images
    # =========================================================
    try:
        page_images = pdf_pages_to_images(pdf_path, dpi=200)
    except RuntimeError as e:
        return RejectionResponse(
            statement_id=statement_id,
            filename=filename,
            reason=f"Could not convert PDF to images: {str(e)}",
            suggestion="Upload a standard PDF file (not encrypted or damaged).",
        )

    # =========================================================
    # STEP 4: Check image quality BEFORE calling AI
    # =========================================================
    readable_images = []
    unreadable_pages = []

    for img_data in page_images:
        page_num = img_data["page_number"]
        
        # Skip pages where text extraction already worked
        if any(p["page_number"] == page_num and p["quality"]["is_usable"] for p in page_scores):
            continue
        
        quality_check = check_image_quality(img_data["image_bytes"])
        
        if quality_check["is_readable"]:
            readable_images.append({
                **img_data,
                "image_quality": quality_check,
            })
        else:
            unreadable_pages.append({
                "page_number": page_num,
                "reason": quality_check["reason"],
            })

    # =========================================================
    # PATH C: No readable images → Reject entirely
    # =========================================================
    if not readable_images and not usable_pages:
        reasons = [f"Page {p['page_number']}: {p['reason']}" for p in unreadable_pages]
        return RejectionResponse(
            statement_id=statement_id,
            filename=filename,
            reason="All pages are too poor quality to extract text. " + "; ".join(reasons),
            suggestion="Upload a higher quality scan or a digitally-generated bank statement PDF.",
        )

    # =========================================================
    # PATH B: Some pages need Vision AI → Call Claude
    # =========================================================
    vision_pages = []
    total_ai_cost = 0.0
    
    for img_data in readable_images:
        result = extract_text_with_vision(
            image_base64=img_data["image_base64"],
            page_number=img_data["page_number"],
            api_key=api_key,
        )
        
        if result["success"]:
            vision_quality = score_text_quality(result["text"])
            vision_pages.append({
                "page_number": result["page_number"],
                "text": result["text"],
                "quality": vision_quality,
                "method": ExtractionMethod.VISION,
                "cost": result["cost_estimate_usd"],
            })
            total_ai_cost += result["cost_estimate_usd"]
        else:
            warnings.append(
                f"Page {result['page_number']}: Vision AI failed — {result['error']}"
            )
            # Add as unreadable
            unreadable_pages.append({
                "page_number": result["page_number"],
                "reason": result["error"] or "Vision API call failed",
            })

    # =========================================================
    # Combine all results: text-extracted pages + vision pages
    # =========================================================
    all_page_results = []
    
    # Add pages where text extraction worked
    for ps in page_scores:
        if ps["quality"]["is_usable"]:
            all_page_results.append(PageResult(
                page_number=ps["page_number"],
                text=ps["text"],
                method=ExtractionMethod.TEXT,
                text_quality_score=ps["quality"]["score"],
                char_count=ps["char_count"],
                line_count=ps["line_count"],
            ))
    
    # Add pages where Vision AI was used
    for vp in vision_pages:
        all_page_results.append(PageResult(
            page_number=vp["page_number"],
            text=vp["text"],
            method=ExtractionMethod.VISION,
            text_quality_score=vp["quality"]["score"],
            char_count=len(vp["text"]),
            line_count=len(vp["text"].split("\n")),
        ))

    # Add warnings for unreadable pages
    for up in unreadable_pages:
        warnings.append(f"Page {up['page_number']} could not be read: {up['reason']}")

    # Sort by page number
    all_page_results.sort(key=lambda p: p.page_number)
    
    # If we got nothing at all
    if not all_page_results:
        return RejectionResponse(
            statement_id=statement_id,
            filename=filename,
            reason="Could not extract text from any page using either method.",
            suggestion="Upload a clearer bank statement — either a digitally-generated PDF or a high-quality scan.",
        )

    # Build final response
    full_text = "\n\n--- PAGE BREAK ---\n\n".join(p.text for p in all_page_results)
    avg_score = sum(p.text_quality_score for p in all_page_results) / len(all_page_results)
    
    # Determine overall method
    methods_used = set(p.method for p in all_page_results)
    if ExtractionMethod.VISION in methods_used:
        overall_method = ExtractionMethod.VISION
    else:
        overall_method = ExtractionMethod.TEXT

    return ExtractionResponse(
        statement_id=statement_id,
        filename=filename,
        total_pages=len(all_page_results),
        extraction_method=overall_method,
        ai_used=total_ai_cost > 0,
        ai_cost_estimate_usd=round(total_ai_cost, 4),
        pages=all_page_results,
        full_text=full_text,
        text_quality_score=round(avg_score, 3),
        warnings=warnings,
    )
