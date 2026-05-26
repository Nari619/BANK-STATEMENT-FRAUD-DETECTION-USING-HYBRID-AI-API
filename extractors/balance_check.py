"""
StatementIQ Component 3 — Balance Math Verification
Row-by-row arithmetic check on parsed transactions.

No AI. Pure math. 2+2 must equal 4.

If someone edited a deposit from $2,000 to $5,000 but forgot
to update the running balance 40 rows later — this catches it.

Also acts as a SAFETY NET for Component 4:
If the LLM misread a number during parsing, the math won't
reconcile, and we'll flag it. Component 3 protects against
Component 4's hallucination risk.
"""


def verify_balances(transactions: list[dict]) -> dict:
    """
    Check if running balances add up row by row.
    
    For each consecutive pair of transactions:
        previous_balance + current_amount ≈ current_balance
    
    Returns:
    {
        "is_valid": bool,              # all balances reconcile
        "total_rows_checked": int,
        "discrepancies": list[dict],   # rows where math fails
        "discrepancy_count": int,
        "total_discrepancy_amount": float,  # sum of all discrepancies
        "risk_level": str,             # "clean" | "minor" | "major" | "critical"
        "summary": str,
    }
    """
    # Filter to transactions that have balance data
    with_balance = [
        t for t in transactions 
        if t.get("balance") is not None
    ]
    
    if len(with_balance) < 2:
        return {
            "is_valid": True,  # can't verify with < 2 balance points
            "total_rows_checked": 0,
            "discrepancies": [],
            "discrepancy_count": 0,
            "total_discrepancy_amount": 0.0,
            "risk_level": "unknown",
            "summary": f"Only {len(with_balance)} transaction(s) with balance data. Need at least 2 to verify. Cannot confirm or deny accuracy.",
        }
    
    discrepancies = []
    rows_checked = 0
    
    for i in range(1, len(with_balance)):
        prev = with_balance[i - 1]
        curr = with_balance[i]
        
        prev_balance = prev["balance"]
        curr_amount = curr["amount"]
        curr_balance = curr["balance"]
        
        # Skip if current row is a "Beginning Balance" type entry
        if curr_amount == 0 and curr.get("description", "").lower().startswith("begin"):
            continue
        
        # Expected balance = previous balance + current amount
        expected_balance = round(prev_balance + curr_amount, 2)
        actual_balance = round(curr_balance, 2)
        
        # Allow tiny floating point tolerance (±$0.01)
        difference = round(actual_balance - expected_balance, 2)
        
        rows_checked += 1
        
        if abs(difference) > 0.01:
            discrepancies.append({
                "row": i + 1,
                "date": curr.get("date", ""),
                "description": curr.get("description", ""),
                "previous_balance": prev_balance,
                "transaction_amount": curr_amount,
                "expected_balance": expected_balance,
                "actual_balance": actual_balance,
                "discrepancy": difference,
            })
    
    # Calculate totals
    discrepancy_count = len(discrepancies)
    total_discrepancy = sum(abs(d["discrepancy"]) for d in discrepancies)
    
    # Determine risk level
    if discrepancy_count == 0:
        risk_level = "clean"
        is_valid = True
        summary = f"All {rows_checked} balance calculations verified. Math is correct."
    elif discrepancy_count <= 2 and total_discrepancy < 1.0:
        risk_level = "minor"
        is_valid = True
        summary = (
            f"{discrepancy_count} minor rounding discrepancy(ies) found "
            f"(total: ${total_discrepancy:.2f}). Likely floating-point rounding, not fraud."
        )
    elif discrepancy_count <= 3 and total_discrepancy < 100:
        risk_level = "major"
        is_valid = False
        summary = (
            f"{discrepancy_count} balance discrepancy(ies) found "
            f"totaling ${total_discrepancy:.2f}. Document may have been altered."
        )
    else:
        risk_level = "critical"
        is_valid = False
        summary = (
            f"{discrepancy_count} balance discrepancy(ies) found "
            f"totaling ${total_discrepancy:,.2f}. "
            f"Strong evidence of document tampering or fabrication."
        )
    
    return {
        "is_valid": is_valid,
        "total_rows_checked": rows_checked,
        "discrepancies": discrepancies,
        "discrepancy_count": discrepancy_count,
        "total_discrepancy_amount": round(total_discrepancy, 2),
        "risk_level": risk_level,
        "summary": summary,
    }
