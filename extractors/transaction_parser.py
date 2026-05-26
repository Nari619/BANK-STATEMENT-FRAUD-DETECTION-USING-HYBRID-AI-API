"""
StatementIQ Component 4 — Transaction Parser (Hybrid)

Takes raw text from Component 1 and converts it to structured transactions.

Path A: Regex patterns for known banks (Chase, BofA, Wells Fargo, Capital One, Citi)
        → Free, instant, ~40% of US banking customers covered
        
Path B: Claude API fallback for unknown bank formats
        → Costs ~$0.01-0.03 per page, handles any format

Output: list of structured transactions as JSON
"""

import re
import os
import json
from typing import Optional


# ═══════════════════════════════════════════════════════════
# REGEX PARSERS — NO AI (top 5 US banks)
# ═══════════════════════════════════════════════════════════

def _detect_bank(text: str) -> Optional[str]:
    """Detect which bank this statement is from based on text content."""
    text_upper = text.upper()
    
    patterns = {
        "chase": [r"JPMORGAN\s*CHASE", r"CHASE\s+BANK", r"CHASE\.COM", r"^CHASE$"],
        "bofa": [r"BANK\s*OF\s*AMERICA", r"BANKOFAMERICA", r"BOFA"],
        "wells_fargo": [r"WELLS\s*FARGO", r"WELLSFARGO"],
        "capital_one": [r"CAPITAL\s*ONE", r"CAPITALONE"],
        "citi": [r"CITIBANK", r"CITI\s+BANK", r"CITIGROUP"],
    }
    
    for bank, bank_patterns in patterns.items():
        for pattern in bank_patterns:
            if re.search(pattern, text_upper, re.MULTILINE):
                return bank
    
    return None


def _parse_chase(text: str) -> list[dict]:
    """Parse Chase bank statement transactions."""
    transactions = []
    
    # Chase format: MM/DD  DESCRIPTION  ±$X,XXX.XX  $X,XXX.XX
    pattern = re.compile(
        r'(\d{2}/\d{2})\s+'           # date
        r'(.+?)\s+'                     # description
        r'([+\-]?\$[\d,]+\.\d{2})\s+'  # amount
        r'(\$[\d,]+\.\d{2})',           # balance
        re.MULTILINE
    )
    
    for match in pattern.finditer(text):
        date, desc, amount, balance = match.groups()
        transactions.append(_build_transaction(date, desc.strip(), amount, balance))
    
    # If the pattern above didn't catch transactions, try a more flexible one
    if not transactions:
        # Try: MM/DD  DESCRIPTION  $X,XXX.XX  $X,XXX.XX (without +/-)
        pattern2 = re.compile(
            r'(\d{2}/\d{2})\s+'
            r'(.+?)\s+'
            r'(-?\$?[\d,]+\.\d{2})\s+'
            r'(\$?[\d,]+\.\d{2})',
            re.MULTILINE
        )
        for match in pattern2.finditer(text):
            date, desc, amount, balance = match.groups()
            if desc.strip() and not desc.strip().startswith("Date"):
                transactions.append(_build_transaction(date, desc.strip(), amount, balance))
    
    return transactions


def _parse_bofa(text: str) -> list[dict]:
    """Parse Bank of America statement transactions."""
    transactions = []
    
    # BofA format varies but commonly: MM/DD/YYYY  DESCRIPTION  AMOUNT
    pattern = re.compile(
        r'(\d{2}/\d{2}/?\d{0,4})\s+'
        r'(.+?)\s+'
        r'(-?[\d,]+\.\d{2})\s*'
        r'([\d,]+\.\d{2})?',
        re.MULTILINE
    )
    
    for match in pattern.finditer(text):
        date, desc, amount, balance = match.groups()
        if desc.strip() and not desc.strip().lower().startswith("date"):
            transactions.append(_build_transaction(
                date, desc.strip(), amount, balance or ""
            ))
    
    return transactions


def _parse_generic(text: str) -> list[dict]:
    """
    Generic regex parser — tries common transaction formats.
    Works for Wells Fargo, Capital One, Citi, and many others.
    """
    transactions = []
    
    # Pattern: date followed by description, then dollar amounts
    patterns = [
        # MM/DD  DESC  $AMT  $BAL
        re.compile(
            r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+'
            r'(.{10,60}?)\s+'
            r'(-?\$?[\d,]+\.\d{2})\s+'
            r'(\$?[\d,]+\.\d{2})',
            re.MULTILINE
        ),
        # MM/DD  DESC  AMT (no balance column)
        re.compile(
            r'(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+'
            r'(.{10,60}?)\s+'
            r'(-?\$?[\d,]+\.\d{2})\s*$',
            re.MULTILINE
        ),
    ]
    
    for pattern in patterns:
        matches = pattern.findall(text)
        if len(matches) >= 3:  # need at least 3 transactions to be confident
            for match in matches:
                date = match[0]
                desc = match[1].strip()
                amount = match[2]
                balance = match[3] if len(match) > 3 else ""
                
                if desc and not desc.lower().startswith("date"):
                    transactions.append(_build_transaction(date, desc, amount, balance))
            break
    
    return transactions


def _build_transaction(date: str, description: str, amount: str, balance: str) -> dict:
    """Build a standardized transaction dict."""
    # Clean amount
    amount_clean = amount.replace("$", "").replace(",", "").strip()
    
    # Determine type
    is_credit = amount.startswith("+") or (
        not amount.startswith("-") and any(kw in description.upper() for kw in 
        ["DEPOSIT", "DIRECT DEP", "PAYROLL", "CREDIT", "INTEREST", "REFUND",
         "PAYMENT FROM", "TRANSFER FROM", "ZELLE FROM", "VENMO FROM"])
    )
    
    try:
        amount_float = float(amount_clean.lstrip("+-"))
        if not is_credit and not amount.startswith("+"):
            amount_float = -abs(amount_float)
        else:
            amount_float = abs(amount_float)
    except ValueError:
        amount_float = 0.0
    
    # Clean balance
    balance_clean = balance.replace("$", "").replace(",", "").strip()
    try:
        balance_float = float(balance_clean) if balance_clean else None
    except ValueError:
        balance_float = None
    
    # Classify income source
    desc_upper = description.upper()
    if any(kw in desc_upper for kw in ["PAYROLL", "DIRECT DEP", "SALARY"]):
        income_type = "W2_SALARY"
    elif any(kw in desc_upper for kw in ["UBER", "LYFT", "DOORDASH", "INSTACART", "GRUBHUB"]):
        income_type = "GIG_PLATFORM"
    elif any(kw in desc_upper for kw in ["VENMO", "ZELLE", "CASHAPP", "PAYPAL"]):
        income_type = "P2P_TRANSFER"
    elif any(kw in desc_upper for kw in ["INTEREST"]):
        income_type = "INTEREST"
    else:
        income_type = "EXPENSE" if amount_float < 0 else "OTHER_INCOME"
    
    return {
        "date": date,
        "description": description,
        "amount": amount_float,
        "amount_raw": amount,
        "balance": balance_float,
        "balance_raw": balance,
        "type": "credit" if amount_float >= 0 else "debit",
        "category": income_type,
    }


# ═══════════════════════════════════════════════════════════
# CLAUDE API FALLBACK — AI (unknown bank formats)
# ═══════════════════════════════════════════════════════════

def _parse_with_llm(text: str, api_key: str | None = None) -> list[dict]:
    """
    Send raw text to Claude API for transaction extraction.
    Called ONLY when regex parsers fail.
    """
    try:
        import anthropic
    except ImportError:
        return []

    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key or key.startswith("sk-your"):
        return []
    
    try:
        client = anthropic.Anthropic(api_key=key)
        
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": (
                    "Extract every transaction from this bank statement text. "
                    "Return ONLY a JSON array with no other text. "
                    "Each transaction must have these exact fields:\n"
                    '{"date": "MM/DD", "description": "...", "amount": -123.45, '
                    '"balance": 1234.56, "type": "debit" or "credit", '
                    '"category": "W2_SALARY" or "GIG_PLATFORM" or "P2P_TRANSFER" '
                    'or "EXPENSE" or "INTEREST" or "OTHER_INCOME"}\n\n'
                    "Rules:\n"
                    "- Negative amounts for withdrawals/debits\n"
                    "- Positive amounts for deposits/credits\n"
                    "- If balance column exists, include it. If not, set to null.\n"
                    "- Classify deposits: payroll/salary → W2_SALARY, "
                    "Uber/Lyft/DoorDash → GIG_PLATFORM, Venmo/Zelle → P2P_TRANSFER\n"
                    "- Skip header rows and summary sections\n\n"
                    f"Bank statement text:\n\n{text[:6000]}"
                ),
            }],
        )
        
        response_text = response.content[0].text.strip()
        
        # Clean markdown fences if present
        response_text = re.sub(r'^```json\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)
        
        transactions = json.loads(response_text)
        
        if isinstance(transactions, list):
            # Standardize fields
            cleaned = []
            for t in transactions:
                cleaned.append({
                    "date": t.get("date", ""),
                    "description": t.get("description", ""),
                    "amount": float(t.get("amount", 0)),
                    "amount_raw": str(t.get("amount", "")),
                    "balance": float(t["balance"]) if t.get("balance") is not None else None,
                    "balance_raw": str(t.get("balance", "")),
                    "type": t.get("type", "debit"),
                    "category": t.get("category", "EXPENSE"),
                })
            return cleaned
        
        return []
    
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# MAIN PARSER — ORCHESTRATES REGEX → LLM FALLBACK
# ═══════════════════════════════════════════════════════════

def parse_transactions(text: str, api_key: str | None = None) -> dict:
    """
    Main entry point. Takes raw text from Component 1.
    Tries regex first. Falls back to LLM if regex fails.
    
    Returns:
    {
        "transactions": list[dict],
        "count": int,
        "bank_detected": str | None,
        "parser_used": "regex" | "llm" | "none",
        "ai_used": bool,
        "ai_cost_estimate": float,
        "income_summary": dict,
        "warnings": list[str],
    }
    """
    warnings = []
    
    # Step 1: Detect the bank
    bank = _detect_bank(text)
    
    # Step 2: Try bank-specific regex parser
    transactions = []
    parser_used = "none"
    
    if bank == "chase":
        transactions = _parse_chase(text)
        if transactions:
            parser_used = "regex"
    elif bank == "bofa":
        transactions = _parse_bofa(text)
        if transactions:
            parser_used = "regex"
    elif bank in ("wells_fargo", "capital_one", "citi"):
        transactions = _parse_generic(text)
        if transactions:
            parser_used = "regex"
    
    # Step 3: If no bank detected or regex failed, try generic regex
    if not transactions:
        transactions = _parse_generic(text)
        if transactions:
            parser_used = "regex"
            if not bank:
                warnings.append("Bank not identified. Used generic transaction parser.")
    
    # Step 4: If regex still failed, fall back to LLM
    ai_used = False
    ai_cost = 0.0
    
    if not transactions:
        warnings.append("Regex parsing failed. Attempting Claude API fallback.")
        transactions = _parse_with_llm(text, api_key)
        
        if transactions:
            parser_used = "llm"
            ai_used = True
            ai_cost = 0.02  # estimated cost per statement
        else:
            warnings.append("Both regex and LLM parsing failed. No transactions extracted.")
    
    # Step 5: Build income summary
    income_summary = _build_income_summary(transactions)
    
    return {
        "transactions": transactions,
        "count": len(transactions),
        "bank_detected": bank,
        "parser_used": parser_used,
        "ai_used": ai_used,
        "ai_cost_estimate": ai_cost,
        "income_summary": income_summary,
        "warnings": warnings,
    }


def _build_income_summary(transactions: list[dict]) -> dict:
    """Summarize income sources from parsed transactions."""
    credits = [t for t in transactions if t.get("amount", 0) > 0]
    debits = [t for t in transactions if t.get("amount", 0) < 0]
    
    total_income = sum(t["amount"] for t in credits)
    total_expenses = sum(abs(t["amount"]) for t in debits)
    
    # Group by category
    by_category = {}
    for t in credits:
        cat = t.get("category", "OTHER_INCOME")
        if cat not in by_category:
            by_category[cat] = {"count": 0, "total": 0.0}
        by_category[cat]["count"] += 1
        by_category[cat]["total"] += t["amount"]
    
    return {
        "total_deposits": round(total_income, 2),
        "total_withdrawals": round(total_expenses, 2),
        "net_cashflow": round(total_income - total_expenses, 2),
        "deposit_count": len(credits),
        "withdrawal_count": len(debits),
        "income_by_category": by_category,
    }
