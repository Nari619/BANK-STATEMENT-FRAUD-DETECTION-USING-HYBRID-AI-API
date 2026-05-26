"""
StatementIQ Component 1 — Data Models
Pydantic schemas for API request/response.
"""

from pydantic import BaseModel
from typing import Optional
from enum import Enum


class ExtractionMethod(str, Enum):
    """How the text was extracted from the PDF."""
    TEXT = "text_extraction"       # pdfplumber got clean text — no AI used
    VISION = "vision_ai"          # Claude Vision read the image — AI used
    REJECTED = "rejected"         # Image too poor — no AI cost wasted


class PageResult(BaseModel):
    """Extraction result for a single page."""
    page_number: int
    text: str
    method: ExtractionMethod
    text_quality_score: float          # 0.0 to 1.0
    char_count: int
    line_count: int


class ExtractionResponse(BaseModel):
    """Full response from Component 1."""
    statement_id: str                  # unique ID for this upload
    filename: str
    total_pages: int
    extraction_method: ExtractionMethod  # overall method used
    ai_used: bool                      # simple flag: did we spend money?
    ai_cost_estimate_usd: float        # estimated cost of AI calls
    pages: list[PageResult]
    full_text: str                     # all pages concatenated
    text_quality_score: float          # overall quality 0.0 to 1.0
    warnings: list[str]               # any issues encountered
    error: Optional[str] = None


class RejectionResponse(BaseModel):
    """Response when PDF is rejected."""
    statement_id: str
    filename: str
    rejected: bool = True
    reason: str
    suggestion: str
