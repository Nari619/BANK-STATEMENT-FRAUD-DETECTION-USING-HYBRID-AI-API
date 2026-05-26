"""
StatementIQ Component 1 — Claude Vision Fallback
Called ONLY when:
  1. pdfplumber text extraction failed (image-based PDF)
  2. Image quality gate passed (image is readable)

Uses Anthropic Claude Vision — same API key as all other AI components.
One provider. One key. No OpenAI dependency.
"""

import os

# Estimated cost per page (Claude Sonnet vision input + output)
ESTIMATED_COST_PER_PAGE_USD = 0.01


def extract_text_with_vision(
    image_base64: str,
    page_number: int,
    api_key: str | None = None,
) -> dict:
    """
    Send a page image to Claude Vision and extract the text content.
    
    Args:
        image_base64: Base64-encoded PNG image of the PDF page
        page_number: Which page this is
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
    
    Returns:
    {
        "text": str,
        "page_number": int,
        "model_used": str,
        "cost_estimate_usd": float,
        "success": bool,
        "error": str | None
    }
    """
    try:
        import anthropic
    except ImportError:
        return {
            "text": "",
            "page_number": page_number,
            "model_used": "none",
            "cost_estimate_usd": 0.0,
            "success": False,
            "error": "anthropic package not installed. Run: pip install anthropic",
        }

    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    
    if not key or key.startswith("sk-your") or key.startswith("sk-ant-your"):
        return {
            "text": "",
            "page_number": page_number,
            "model_used": "none",
            "cost_estimate_usd": 0.0,
            "success": False,
            "error": "No Anthropic API key configured. Set ANTHROPIC_API_KEY in .env file.",
        }

    try:
        client = anthropic.Anthropic(api_key=key)

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                f"Extract ALL text from page {page_number} of this bank statement. "
                                "Preserve the layout using spaces and newlines. "
                                "For transaction tables, put each row on its own line "
                                "with values separated by two spaces. "
                                "Include headers, account info, dates, amounts, balances. "
                                "Do NOT summarize. Do NOT interpret. Do NOT add commentary. "
                                "Output ONLY the extracted text."
                            ),
                        },
                    ],
                },
            ],
        )

        extracted_text = response.content[0].text or ""

        return {
            "text": extracted_text.strip(),
            "page_number": page_number,
            "model_used": "claude-sonnet-4-6",
            "cost_estimate_usd": ESTIMATED_COST_PER_PAGE_USD,
            "success": True,
            "error": None,
        }

    except Exception as e:
        return {
            "text": "",
            "page_number": page_number,
            "model_used": "claude-sonnet-4-6",
            "cost_estimate_usd": 0.0,
            "success": False,
            "error": f"Claude Vision API call failed: {str(e)}",
        }


def estimate_vision_cost(num_pages: int) -> float:
    """Estimate the cost of processing N pages through Claude Vision."""
    return round(num_pages * ESTIMATED_COST_PER_PAGE_USD, 4)
