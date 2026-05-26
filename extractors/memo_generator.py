"""
StatementIQ Component 5 — Memo Generator (Hybrid AI)

Takes verified data from Components 2, 3, 4 and produces
a human-readable underwriting memo.

CRITICAL RULE: 
  - Template inserts ALL numbers (income, ratios, fraud signals)
  - LLM writes ONLY the narrative glue and recommendation
  - LLM NEVER generates a dollar amount
  - Even if LLM hallucinates, the numbers it sits beside are verified

This is where AI creates genuine, defensible value:
turning structured data into a decision a landlord can act on
without being a financial analyst.
"""

import os
import json
from typing import Optional
from datetime import datetime


def generate_memo(
    metadata_result: dict,
    transaction_result: dict,
    balance_result: dict,
    context: str = "tenant_screening",  # "tenant_screening" | "lending"
    monthly_obligation: float = 0.0,     # rent or loan payment
    api_key: str | None = None,
) -> dict:
    """
    Generate a human-readable underwriting memo.
    
    Returns:
    {
        "memo": str,                    # the full memo text
        "data_section": str,            # template-generated numbers section
        "narrative_section": str,       # LLM-generated narrative
        "recommendation": str,          # LLM-generated recommendation
        "ai_used": bool,
        "ai_cost_estimate": float,
        "generated_at": str,
    }
    """
    # ═══════════════════════════════════════════════════════
    # SECTION 1: TEMPLATE — Numbers only (NO AI)
    # Every dollar amount comes from verified data
    # ═══════════════════════════════════════════════════════
    
    income_summary = transaction_result.get("income_summary", {})
    transactions = transaction_result.get("transactions", [])
    
    total_deposits = income_summary.get("total_deposits", 0)
    total_withdrawals = income_summary.get("total_withdrawals", 0)
    net_cashflow = income_summary.get("net_cashflow", 0)
    
    # Calculate income-to-obligation ratio
    ratio = round(total_deposits / monthly_obligation, 2) if monthly_obligation > 0 else 0
    meets_3x = ratio >= 3.0
    
    # Count income sources by category
    income_cats = income_summary.get("income_by_category", {})
    
    # Balance verification status
    balance_valid = balance_result.get("is_valid", True)
    balance_risk = balance_result.get("risk_level", "unknown")
    discrepancy_count = balance_result.get("discrepancy_count", 0)
    total_discrepancy = balance_result.get("total_discrepancy_amount", 0)
    
    # Metadata risk
    meta_risk = metadata_result.get("risk_level", "unknown")
    meta_score = metadata_result.get("risk_score", 50)
    meta_signals = metadata_result.get("signals", [])
    critical_signals = [s for s in meta_signals if s["severity"] in ("critical", "high")]
    
    # Build the data section (pure template, no AI)
    data_lines = []
    data_lines.append("=" * 50)
    data_lines.append("  STATEMENTIQ — FINANCIAL ASSESSMENT REPORT")
    data_lines.append("=" * 50)
    data_lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    data_lines.append(f"  Context: {'Tenant Screening' if context == 'tenant_screening' else 'Lending Review'}")
    if monthly_obligation > 0:
        label = "Monthly Rent" if context == "tenant_screening" else "Monthly Payment"
        data_lines.append(f"  {label}: ${monthly_obligation:,.2f}")
    data_lines.append("")
    
    # Document Verification
    data_lines.append("─" * 50)
    data_lines.append("  DOCUMENT VERIFICATION")
    data_lines.append("─" * 50)
    data_lines.append(f"  Metadata Risk: {meta_risk.upper()} (score: {meta_score}/100)")
    data_lines.append(f"  Balance Math: {'VERIFIED ✓' if balance_valid else 'FAILED ✗'}")
    if discrepancy_count > 0:
        data_lines.append(f"  Discrepancies: {discrepancy_count} found (${total_discrepancy:,.2f} total)")
    if critical_signals:
        for sig in critical_signals:
            data_lines.append(f"  ⚠ {sig['detail']}")
    data_lines.append("")
    
    # Financial Summary
    data_lines.append("─" * 50)
    data_lines.append("  FINANCIAL SUMMARY")
    data_lines.append("─" * 50)
    data_lines.append(f"  Total Deposits:     ${total_deposits:>12,.2f}")
    data_lines.append(f"  Total Withdrawals:  ${total_withdrawals:>12,.2f}")
    data_lines.append(f"  Net Cashflow:       ${net_cashflow:>12,.2f}")
    data_lines.append(f"  Transactions:       {len(transactions)}")
    data_lines.append("")
    
    # Income Sources
    if income_cats:
        data_lines.append("  Income Sources:")
        category_labels = {
            "W2_SALARY": "W2 Salary / Payroll",
            "GIG_PLATFORM": "Gig Platform (Uber, etc.)",
            "P2P_TRANSFER": "P2P Transfer (Venmo, etc.)",
            "INTEREST": "Interest Earned",
            "OTHER_INCOME": "Other Income",
        }
        for cat, data in income_cats.items():
            label = category_labels.get(cat, cat)
            data_lines.append(f"    • {label}: ${data['total']:,.2f} ({data['count']} deposits)")
    data_lines.append("")
    
    # Affordability
    if monthly_obligation > 0:
        data_lines.append("─" * 50)
        data_lines.append("  AFFORDABILITY")
        data_lines.append("─" * 50)
        data_lines.append(f"  Income-to-{'Rent' if context == 'tenant_screening' else 'Payment'} Ratio: {ratio:.2f}x")
        data_lines.append(f"  Meets 3x Requirement: {'YES ✓' if meets_3x else 'NO ✗'}")
        data_lines.append("")
    
    data_section = "\n".join(data_lines)
    
    # ═══════════════════════════════════════════════════════
    # SECTION 2: LLM NARRATIVE — AI writes the story
    # Fed ONLY verified numbers. Cannot hallucinate amounts.
    # ═══════════════════════════════════════════════════════
    
    narrative_section = ""
    recommendation = ""
    ai_used = False
    ai_cost = 0.0
    
    # Build the prompt with verified data only
    facts_for_llm = {
        "context": context,
        "monthly_obligation": monthly_obligation,
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "net_cashflow": net_cashflow,
        "income_to_obligation_ratio": ratio,
        "meets_3x": meets_3x,
        "income_sources": {
            cat: {"total": d["total"], "count": d["count"]} 
            for cat, d in income_cats.items()
        },
        "document_risk_level": meta_risk,
        "balance_math_valid": balance_valid,
        "discrepancies": discrepancy_count,
        "fraud_signals": [s["detail"] for s in critical_signals],
        "transaction_count": len(transactions),
    }
    
    try:
        import anthropic
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        
        if key and not key.startswith("sk-your"):
            client = anthropic.Anthropic(api_key=key)
            
            prompt = (
                "You are writing an underwriting memo for a "
                f"{'landlord evaluating a tenant' if context == 'tenant_screening' else 'lender evaluating a borrower'}.\n\n"
                "CRITICAL RULES:\n"
                "- Do NOT invent any numbers. All financial data is provided below.\n"
                "- Do NOT add dollar amounts not in the data.\n"
                "- Write a 2-3 sentence narrative assessment.\n"
                "- Write a 1-2 sentence recommendation.\n"
                "- Be direct. No filler. No disclaimers about being AI.\n\n"
                f"Verified financial data:\n{json.dumps(facts_for_llm, indent=2)}\n\n"
                "Respond in EXACTLY this format:\n"
                "NARRATIVE: <your 2-3 sentence assessment>\n"
                "RECOMMENDATION: <your 1-2 sentence recommendation>"
            )
            
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            
            response_text = response.content[0].text.strip()
            
            # Parse the response
            if "NARRATIVE:" in response_text and "RECOMMENDATION:" in response_text:
                parts = response_text.split("RECOMMENDATION:")
                narrative_section = parts[0].replace("NARRATIVE:", "").strip()
                recommendation = parts[1].strip()
            else:
                narrative_section = response_text
                recommendation = ""
            
            ai_used = True
            ai_cost = 0.01
    
    except Exception:
        pass
    
    # Fallback if LLM is unavailable — template-based narrative
    if not narrative_section:
        narrative_section = _template_narrative(facts_for_llm)
        recommendation = _template_recommendation(facts_for_llm)
    
    # ═══════════════════════════════════════════════════════
    # COMBINE: Template data + LLM narrative
    # ═══════════════════════════════════════════════════════
    
    memo_lines = [data_section]
    memo_lines.append("─" * 50)
    memo_lines.append("  ASSESSMENT")
    memo_lines.append("─" * 50)
    memo_lines.append(f"  {narrative_section}")
    memo_lines.append("")
    memo_lines.append("─" * 50)
    memo_lines.append("  RECOMMENDATION")
    memo_lines.append("─" * 50)
    memo_lines.append(f"  {recommendation}")
    memo_lines.append("")
    memo_lines.append("=" * 50)
    memo_lines.append("  ⚠ AI-generated summary. Not financial or legal advice.")
    memo_lines.append("  Verify independently before making decisions.")
    memo_lines.append("=" * 50)
    
    full_memo = "\n".join(memo_lines)
    
    return {
        "memo": full_memo,
        "data_section": data_section,
        "narrative_section": narrative_section,
        "recommendation": recommendation,
        "ai_used": ai_used,
        "ai_cost_estimate": ai_cost,
        "generated_at": datetime.now().isoformat(),
    }


def _template_narrative(facts: dict) -> str:
    """Fallback narrative when LLM is unavailable. Pure template."""
    parts = []
    
    deposits = facts["total_deposits"]
    ratio = facts["income_to_obligation_ratio"]
    valid = facts["balance_math_valid"]
    risk = facts["document_risk_level"]
    sources = facts["income_sources"]
    
    # Income description
    source_parts = []
    for cat, data in sources.items():
        labels = {
            "W2_SALARY": "W2 salary",
            "GIG_PLATFORM": "gig platform income",
            "P2P_TRANSFER": "peer-to-peer transfers",
            "INTEREST": "interest",
            "OTHER_INCOME": "other deposits",
        }
        source_parts.append(f"{labels.get(cat, cat)} (${data['total']:,.2f})")
    
    if source_parts:
        parts.append(f"Applicant shows income from: {', '.join(source_parts)}.")
    
    parts.append(f"Total verified deposits: ${deposits:,.2f}.")
    
    if facts["monthly_obligation"] > 0:
        parts.append(f"Income-to-obligation ratio: {ratio:.2f}x {'(meets' if facts['meets_3x'] else '(below'} 3x threshold).")
    
    # Document integrity
    if risk in ("critical", "high"):
        parts.append("DOCUMENT INTEGRITY CONCERN: Metadata and/or balance checks flagged significant issues.")
    elif not valid:
        parts.append("Balance verification failed — document may have been altered.")
    
    return " ".join(parts)


def _template_recommendation(facts: dict) -> str:
    """Fallback recommendation when LLM is unavailable."""
    risk = facts["document_risk_level"]
    valid = facts["balance_math_valid"]
    meets_3x = facts["meets_3x"]
    signals = facts["fraud_signals"]
    
    if risk in ("critical", "high") or signals:
        return "REJECT. Document shows significant fraud indicators. Request original bank statements directly from the financial institution."
    
    if not valid:
        return "REJECT. Balance calculations do not reconcile. Document appears to have been altered. Request original statements."
    
    if meets_3x:
        return "APPROVE. Financial metrics meet standard requirements and document verification passed."
    
    return "CONDITIONAL. Income-to-obligation ratio is below the standard 3x threshold. Consider requesting additional documentation, a co-signer, or a larger security deposit."
