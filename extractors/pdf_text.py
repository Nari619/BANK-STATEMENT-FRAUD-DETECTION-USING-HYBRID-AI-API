"""
StatementIQ Component 1 — PDF Text Extractor
Uses pdfplumber to extract selectable text from machine-readable PDFs.
No AI. No cost. This is the happy path.
"""

import pdfplumber
from typing import Optional


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Extract text from each page of a PDF using pdfplumber.
    
    Returns a list of dicts, one per page:
    {
        "page_number": int,
        "text": str,
        "char_count": int,
        "line_count": int,
        "has_tables": bool
    }
    
    If text extraction produces nothing (image-based PDF),
    text will be empty and char_count will be 0.
    """
    results = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                # Extract text
                text = page.extract_text() or ""
                
                # Try table extraction if regular text is sparse
                # Bank statements are often formatted as tables
                tables = page.extract_tables()
                table_text = ""
                if tables:
                    for table in tables:
                        for row in table:
                            if row:
                                # Filter None values and join
                                cleaned = [str(cell).strip() if cell else "" for cell in row]
                                table_text += "  ".join(cleaned) + "\n"

                # Use whichever extraction got more content
                final_text = text if len(text) >= len(table_text) else table_text
                
                # If both extractions got something, merge them
                # (text extraction gets headers/footers, table extraction gets transaction rows)
                if text and table_text and len(table_text) > len(text) * 0.5:
                    # Table had significant content — use table for structured data
                    # but keep text for headers/account info that might not be in tables
                    lines_in_text = set(text.strip().split("\n"))
                    lines_in_table = set(table_text.strip().split("\n"))
                    
                    # Find lines that are in text but NOT in table (headers, account info)
                    unique_header_lines = []
                    for line in text.strip().split("\n"):
                        if line.strip() and line.strip() not in [t.strip() for t in table_text.split("\n")]:
                            unique_header_lines.append(line)
                    
                    if unique_header_lines:
                        header_section = "\n".join(unique_header_lines[:10])  # cap at 10 header lines
                        final_text = header_section + "\n\n" + table_text
                    else:
                        final_text = table_text

                results.append({
                    "page_number": i + 1,
                    "text": final_text.strip(),
                    "char_count": len(final_text.strip()),
                    "line_count": len(final_text.strip().split("\n")) if final_text.strip() else 0,
                    "has_tables": len(tables) > 0 if tables else False,
                })

    except Exception as e:
        # If pdfplumber can't even open the file, return empty
        results.append({
            "page_number": 1,
            "text": "",
            "char_count": 0,
            "line_count": 0,
            "has_tables": False,
            "error": str(e),
        })

    return results
