"""
StatementIQ Component 2 — Metadata Fraud Check
Reads PDF internal metadata and flags suspicious signals.

No AI. Just rule-based checks:
- What software created this PDF?
- Does the creation date make sense?
- Does the Author field look like a bank system or a person?

If Producer = "Canva" → fake. 100% accuracy. Zero cost.
"""

import pikepdf
import re
from datetime import datetime, timedelta
from typing import Optional


# Known legitimate bank PDF producers
# Banks use enterprise document management systems, not consumer tools
KNOWN_BANK_PRODUCERS = [
    "opentext", "ibm filenet", "documentum", "hyland",
    "kofax", "adobe livecycle", "sap", "oracle",
    "bottomline", "fiserv", "jack henry", "fis global",
    "pitney bowes", "xerox", "ricoh", "lexmark",
    "quadient", "messagepoint", "smart communications",
    "doxim", "naehas", "cincom", "thunderhead",
]

# Consumer tools that should NEVER produce a real bank statement
SUSPICIOUS_PRODUCERS = {
    "canva": "critical",
    "google docs": "critical",
    "google slides": "critical",
    "libreoffice": "critical",
    "openoffice": "critical",
    "microsoft word": "high",
    "microsoft publisher": "high",
    "pages": "high",
    "keynote": "critical",
    "figma": "critical",
    "sketch": "critical",
    "photoshop": "critical",
    "illustrator": "critical",
    "indesign": "high",
    "affinity": "critical",
    "gimp": "critical",
    "inkscape": "critical",
    "wkhtmltopdf": "medium",        # could be legitimate web-to-PDF
    "chrome": "medium",              # could be "Save as PDF" from online banking
    "firefox": "medium",
    "safari": "medium",
    "prince": "low",                 # legitimate PDF engine
    "weasyprint": "low",
}

# Known fake bank statement generator tools
FAKE_GENERATOR_SIGNATURES = [
    "bank statement generator",
    "novelty document",
    "fake statement",
    "prop document",
    "gag document",
]


def check_metadata(pdf_path: str) -> dict:
    """
    Read PDF metadata and return fraud signals.
    
    Returns:
    {
        "metadata": dict,           # raw metadata fields
        "signals": list[dict],      # fraud signals found
        "risk_level": str,          # "clean" | "low" | "medium" | "high" | "critical"
        "risk_score": int,          # 0-100 (0 = likely fake, 100 = likely real)
        "summary": str,             # one-line summary
    }
    """
    signals = []
    metadata = {}
    
    try:
        with pikepdf.open(pdf_path) as pdf:
            docinfo = pdf.docinfo
            
            # Extract all metadata fields
            metadata = {
                "creator": _safe_str(docinfo.get("/Creator")),
                "producer": _safe_str(docinfo.get("/Producer")),
                "creation_date": _safe_str(docinfo.get("/CreationDate")),
                "mod_date": _safe_str(docinfo.get("/ModDate")),
                "author": _safe_str(docinfo.get("/Author")),
                "title": _safe_str(docinfo.get("/Title")),
                "subject": _safe_str(docinfo.get("/Subject")),
                "total_pages": len(pdf.pages),
            }
    except Exception as e:
        return {
            "metadata": {},
            "signals": [{
                "type": "ERROR",
                "severity": "unknown",
                "detail": f"Could not read PDF metadata: {str(e)}",
            }],
            "risk_level": "unknown",
            "risk_score": 50,
            "summary": "Could not read metadata. File may be encrypted or corrupt.",
        }

    # ── Check 1: Producer field ──────────────────────────────
    producer = (metadata.get("producer") or "").lower().strip()
    
    if not producer:
        signals.append({
            "type": "MISSING_PRODUCER",
            "severity": "medium",
            "detail": "No Producer field. Legitimate bank PDFs always have a Producer.",
        })
    else:
        # Check against suspicious producers
        for tool, severity in SUSPICIOUS_PRODUCERS.items():
            if tool in producer:
                signals.append({
                    "type": "SUSPICIOUS_PRODUCER",
                    "severity": severity,
                    "detail": f"PDF created by '{metadata['producer']}'. Real bank statements are not created with {tool.title()}.",
                })
                break
        
        # Check for known fake generators
        for sig in FAKE_GENERATOR_SIGNATURES:
            if sig in producer:
                signals.append({
                    "type": "FAKE_GENERATOR",
                    "severity": "critical",
                    "detail": f"PDF Producer matches known fake document generator: '{metadata['producer']}'.",
                })
                break
        
        # Check if it matches known bank systems
        is_known_bank = any(bp in producer for bp in KNOWN_BANK_PRODUCERS)
        if is_known_bank:
            signals.append({
                "type": "KNOWN_BANK_PRODUCER",
                "severity": "positive",
                "detail": f"Producer '{metadata['producer']}' matches known bank document systems.",
            })

    # ── Check 2: Creator field ───────────────────────────────
    creator = (metadata.get("creator") or "").lower().strip()
    
    if creator:
        for tool, severity in SUSPICIOUS_PRODUCERS.items():
            if tool in creator:
                signals.append({
                    "type": "SUSPICIOUS_CREATOR",
                    "severity": severity,
                    "detail": f"PDF Creator is '{metadata['creator']}'. This is a consumer design tool, not a banking system.",
                })
                break

    # ── Check 3: Author field ────────────────────────────────
    author = (metadata.get("author") or "").strip()
    
    if author:
        # Bank statements don't have individual author names
        # If the Author looks like a person's name, that's suspicious
        looks_like_name = bool(re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', author))
        
        if looks_like_name:
            signals.append({
                "type": "PERSONAL_AUTHOR",
                "severity": "high",
                "detail": f"Author field contains what appears to be a personal name: '{author}'. Bank statements are generated by systems, not individuals.",
            })
        
        # Check if author matches suspicious tools
        author_lower = author.lower()
        for tool in SUSPICIOUS_PRODUCERS:
            if tool in author_lower:
                signals.append({
                    "type": "SUSPICIOUS_AUTHOR",
                    "severity": "medium",
                    "detail": f"Author field references a consumer tool: '{author}'.",
                })
                break

    # ── Check 4: Creation date ───────────────────────────────
    creation_date = _parse_pdf_date(metadata.get("creation_date"))
    mod_date = _parse_pdf_date(metadata.get("mod_date"))
    
    if creation_date:
        # Check if creation date is in the future
        now = datetime.now()
        if creation_date > now + timedelta(days=1):
            signals.append({
                "type": "FUTURE_DATE",
                "severity": "high",
                "detail": f"Creation date {creation_date.strftime('%Y-%m-%d')} is in the future.",
            })
    
    # ── Check 5: Modification date vs creation date ──────────
    if creation_date and mod_date:
        # Real bank statements are generated once and never modified
        time_diff = abs((mod_date - creation_date).total_seconds())
        
        if time_diff > 86400:  # more than 24 hours difference
            days_diff = time_diff / 86400
            signals.append({
                "type": "MODIFIED_AFTER_CREATION",
                "severity": "high",
                "detail": f"Document was modified {days_diff:.0f} days after creation. Authentic bank statements are generated once and never edited.",
            })
        elif time_diff > 3600:  # more than 1 hour
            signals.append({
                "type": "MODIFIED_AFTER_CREATION",
                "severity": "medium",
                "detail": f"Document was modified {time_diff/3600:.1f} hours after creation. Minor discrepancy — could be system processing.",
            })
    
    # ── Check 6: Page count ──────────────────────────────────
    pages = metadata.get("total_pages", 0)
    if pages > 50:
        signals.append({
            "type": "UNUSUAL_LENGTH",
            "severity": "low",
            "detail": f"Document has {pages} pages. Most bank statements are 1-10 pages.",
        })

    # ── Calculate risk score ─────────────────────────────────
    severity_weights = {
        "critical": 40,
        "high": 25,
        "medium": 10,
        "low": 5,
        "positive": -15,   # positive signals REDUCE risk
    }
    
    risk_points = 0
    for signal in signals:
        weight = severity_weights.get(signal["severity"], 0)
        risk_points += weight
    
    # Clamp to 0-100 where 0 = definitely fake, 100 = looks clean
    risk_score = max(0, min(100, 100 - risk_points))
    
    # Determine risk level
    if risk_score >= 80:
        risk_level = "clean"
    elif risk_score >= 60:
        risk_level = "low"
    elif risk_score >= 40:
        risk_level = "medium"
    elif risk_score >= 20:
        risk_level = "high"
    else:
        risk_level = "critical"
    
    # Summary
    critical_signals = [s for s in signals if s["severity"] in ("critical", "high")]
    positive_signals = [s for s in signals if s["severity"] == "positive"]
    
    if not signals or (len(positive_signals) == len(signals)):
        summary = "No suspicious metadata detected. Document appears to be system-generated."
    elif critical_signals:
        summary = f"{len(critical_signals)} critical/high-risk signal(s) found in metadata. Document is likely fabricated or edited."
    else:
        summary = f"{len(signals)} minor signal(s) found. Review recommended."
    
    return {
        "metadata": metadata,
        "signals": signals,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "summary": summary,
    }


def _safe_str(val) -> Optional[str]:
    """Safely convert pikepdf metadata value to string."""
    if val is None:
        return None
    try:
        return str(val)
    except Exception:
        return None


def _parse_pdf_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse PDF date format: D:YYYYMMDDHHmmSS+HH'mm'
    Returns datetime or None if unparseable.
    """
    if not date_str:
        return None
    
    # Remove "D:" prefix
    date_str = date_str.strip()
    if date_str.startswith("D:"):
        date_str = date_str[2:]
    
    # Try common formats
    formats = [
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M",
        "%Y%m%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]
    
    # Clean timezone info
    date_str = re.sub(r"[+\-]\d{2}'\d{2}'?$", "", date_str)
    date_str = re.sub(r"Z$", "", date_str)
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str[:len(fmt.replace("%", ""))], fmt)
        except (ValueError, IndexError):
            continue
    
    return None
