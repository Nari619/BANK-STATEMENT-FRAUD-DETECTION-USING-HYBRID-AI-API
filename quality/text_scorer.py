"""
StatementIQ Component 1 — Text Quality Scorer
Decides if the extracted text is good enough to use,
or if we need to fall back to Vision AI.

No AI. Just heuristics based on what bank statements look like.
"""

import re


# Minimum thresholds for "usable" text
MIN_CHARS_PER_PAGE = 100          # Less than this = probably image-based PDF
MIN_LINES_PER_PAGE = 5            # Bank statements have many lines
MIN_DIGIT_RATIO = 0.05            # Bank statements contain lots of numbers
MIN_DOLLAR_SIGNS = 1              # Should have at least some dollar amounts
GARBAGE_CHAR_THRESHOLD = 0.15     # If >15% characters are garbage, extraction failed


def score_text_quality(text: str) -> dict:
    """
    Score the quality of extracted text on a 0.0 to 1.0 scale.
    
    Returns:
    {
        "score": float (0.0 to 1.0),
        "is_usable": bool,
        "reasons": list[str],    # why it passed or failed
        "details": dict          # individual metric scores
    }
    """
    if not text or not text.strip():
        return {
            "score": 0.0,
            "is_usable": False,
            "reasons": ["No text extracted. PDF is likely image-based."],
            "details": {},
        }

    text = text.strip()
    char_count = len(text)
    line_count = len(text.split("\n"))
    
    reasons = []
    scores = {}

    # --- Check 1: Character count ---
    if char_count < MIN_CHARS_PER_PAGE:
        scores["char_count"] = 0.0
        reasons.append(f"Only {char_count} characters extracted (need {MIN_CHARS_PER_PAGE}+).")
    else:
        scores["char_count"] = min(1.0, char_count / 500)  # normalize: 500+ chars = full score

    # --- Check 2: Line count ---
    if line_count < MIN_LINES_PER_PAGE:
        scores["line_count"] = 0.0
        reasons.append(f"Only {line_count} lines extracted (need {MIN_LINES_PER_PAGE}+).")
    else:
        scores["line_count"] = min(1.0, line_count / 20)

    # --- Check 3: Digit ratio ---
    # Bank statements are full of numbers. If extracted text has very few digits,
    # something went wrong.
    digit_count = sum(1 for c in text if c.isdigit())
    digit_ratio = digit_count / char_count if char_count > 0 else 0

    if digit_ratio < MIN_DIGIT_RATIO:
        scores["digit_ratio"] = 0.0
        reasons.append(f"Digit ratio {digit_ratio:.2%} too low (need {MIN_DIGIT_RATIO:.0%}+). Text may be garbled.")
    else:
        scores["digit_ratio"] = min(1.0, digit_ratio / 0.15)

    # --- Check 4: Dollar signs or currency indicators ---
    dollar_count = text.count("$") + len(re.findall(r'\d+\.\d{2}', text))  # $X or X.XX patterns
    if dollar_count < MIN_DOLLAR_SIGNS:
        scores["currency"] = 0.0
        reasons.append("No dollar amounts detected. May not be a financial document.")
    else:
        scores["currency"] = min(1.0, dollar_count / 10)

    # --- Check 5: Garbage character ratio ---
    # Characters that shouldn't appear in a bank statement
    garbage_chars = sum(1 for c in text if ord(c) > 127 and c not in "€£¥°±©®™•–—''""…")
    garbage_ratio = garbage_chars / char_count if char_count > 0 else 0

    if garbage_ratio > GARBAGE_CHAR_THRESHOLD:
        scores["garbage"] = 0.0
        reasons.append(f"High garbage character ratio ({garbage_ratio:.2%}). Text extraction corrupted.")
    else:
        scores["garbage"] = 1.0 - (garbage_ratio / GARBAGE_CHAR_THRESHOLD)

    # --- Check 6: Date patterns ---
    # Bank statements should contain dates
    date_patterns = len(re.findall(
        r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\w{3,9}\s+\d{1,2},?\s+\d{4}',
        text
    ))
    if date_patterns == 0:
        scores["dates"] = 0.0
        reasons.append("No date patterns found. Extraction may be incomplete.")
    else:
        scores["dates"] = min(1.0, date_patterns / 5)

    # --- Calculate overall score ---
    if not scores:
        overall = 0.0
    else:
        # Weighted average: char_count and digit_ratio matter most
        weights = {
            "char_count": 0.25,
            "line_count": 0.10,
            "digit_ratio": 0.25,
            "currency": 0.15,
            "garbage": 0.15,
            "dates": 0.10,
        }
        overall = sum(scores.get(k, 0) * w for k, w in weights.items())

    # Is it usable?
    is_usable = overall >= 0.4 and scores.get("char_count", 0) > 0

    if is_usable and not reasons:
        reasons.append("Text extraction quality is good. No AI fallback needed.")

    return {
        "score": round(overall, 3),
        "is_usable": is_usable,
        "reasons": reasons,
        "details": {k: round(v, 3) for k, v in scores.items()},
    }
