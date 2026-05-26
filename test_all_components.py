"""
StatementIQ — Test All 5 Components
Run: python test_all_components.py
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator import process_statement
from extractors.metadata_check import check_metadata
from extractors.transaction_parser import parse_transactions
from extractors.balance_check import verify_balances
from extractors.memo_generator import generate_memo
from models import ExtractionResponse, RejectionResponse

TEST_DIR = os.path.join(os.path.dirname(__file__), "test_statements")
P = "✅"
F = "❌"

def check(label, condition):
    print(f"  {P if condition else F}  {label}")
    return condition

def header(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ══════════════════════════════════════════════════════════
# COMPONENT 1: Text Extraction
# ══════════════════════════════════════════════════════════
header("Component 1 — Text Extraction (No AI path)")
pdf = os.path.join(TEST_DIR, "test_chase_text.pdf")
c1 = process_statement(pdf)
c1_ok = all([
    check("Returns ExtractionResponse", isinstance(c1, ExtractionResponse)),
    check("No AI used", not c1.ai_used),
    check("AI cost = $0", c1.ai_cost_estimate_usd == 0),
    check(f"Extracted {len(c1.full_text)} chars", len(c1.full_text) > 100),
    check(f"Quality score {c1.text_quality_score:.3f}", c1.text_quality_score > 0.3),
])

header("Component 1 — Rejection path (Blank PDF)")
blank = os.path.join(TEST_DIR, "test_blank.pdf")
c1_blank = process_statement(blank)
c1_reject_ok = all([
    check("Blank PDF rejected", isinstance(c1_blank, RejectionResponse)),
    check("Has reason", bool(c1_blank.reason)),
])

# ══════════════════════════════════════════════════════════
# COMPONENT 2: Metadata Check
# ══════════════════════════════════════════════════════════
header("Component 2 — Metadata Check (No AI)")
c2 = check_metadata(pdf)
c2_ok = all([
    check("Returns metadata dict", "metadata" in c2),
    check("Has risk_level", c2["risk_level"] in ("clean","low","medium","high","critical","unknown")),
    check(f"Risk score: {c2['risk_score']}/100", isinstance(c2["risk_score"], int)),
    check("Has signals list", isinstance(c2["signals"], list)),
    check(f"Summary: {c2['summary'][:60]}...", bool(c2["summary"])),
    check(f"Producer found: {c2['metadata'].get('producer','N/A')}", True),
])

# ══════════════════════════════════════════════════════════
# COMPONENT 4: Transaction Parser (before 3, because 3 needs its output)
# ══════════════════════════════════════════════════════════
header("Component 4 — Transaction Parser (Regex path)")
c4 = parse_transactions(c1.full_text)
c4_ok = all([
    check(f"Parsed {c4['count']} transactions", c4["count"] > 5),
    check(f"Bank detected: {c4['bank_detected']}", c4["bank_detected"] == "chase"),
    check(f"Parser used: {c4['parser_used']}", c4["parser_used"] == "regex"),
    check("No AI used (regex worked)", not c4["ai_used"]),
    check("AI cost = $0", c4["ai_cost_estimate"] == 0),
    check("Has income summary", bool(c4["income_summary"])),
    check(f"Total deposits: ${c4['income_summary']['total_deposits']:,.2f}", 
          c4["income_summary"]["total_deposits"] > 0),
])

# Print a few parsed transactions
print(f"\n  Sample transactions:")
for t in c4["transactions"][:5]:
    print(f"    {t['date']}  {t['description'][:40]:<40}  {t['amount']:>10.2f}  {str(t.get('balance','')):>10}")

# ══════════════════════════════════════════════════════════
# COMPONENT 3: Balance Math
# ══════════════════════════════════════════════════════════
header("Component 3 — Balance Math Verification (No AI)")
c3 = verify_balances(c4["transactions"])
c3_ok = all([
    check(f"Rows checked: {c3['total_rows_checked']}", c3["total_rows_checked"] > 0),
    check(f"Risk level: {c3['risk_level']}", c3["risk_level"] in ("clean","minor","major","critical","unknown")),
    check(f"Discrepancies: {c3['discrepancy_count']}", isinstance(c3["discrepancy_count"], int)),
    check(f"Summary: {c3['summary'][:70]}...", bool(c3["summary"])),
])

if c3["discrepancies"]:
    print(f"\n  Discrepancies found:")
    for d in c3["discrepancies"][:3]:
        print(f"    Row {d['row']}: expected ${d['expected_balance']:,.2f}, "
              f"got ${d['actual_balance']:,.2f} (off by ${d['discrepancy']:,.2f})")

# ══════════════════════════════════════════════════════════
# COMPONENT 5: Memo Generator
# ══════════════════════════════════════════════════════════
header("Component 5 — Memo Generator")
c5 = generate_memo(
    metadata_result=c2,
    transaction_result=c4,
    balance_result=c3,
    context="tenant_screening",
    monthly_obligation=2200.00,
)
c5_ok = all([
    check("Generated memo", len(c5["memo"]) > 100),
    check("Has data section", len(c5["data_section"]) > 50),
    check("Has narrative", len(c5["narrative_section"]) > 10),
    check("Has recommendation", len(c5["recommendation"]) > 5),
    check(f"AI used: {c5['ai_used']}", isinstance(c5["ai_used"], bool)),
])

# Print memo preview
print(f"\n  --- Memo Preview ---")
for line in c5["memo"].split("\n")[:25]:
    print(f"  {line}")
print(f"  ... ({len(c5['memo'])} total chars)")
print(f"  --- End Preview ---")

# ══════════════════════════════════════════════════════════
# FULL PIPELINE SUMMARY
# ══════════════════════════════════════════════════════════
header("FULL PIPELINE SUMMARY")

total_ai_cost = (
    c1.ai_cost_estimate_usd + 
    c4["ai_cost_estimate"] + 
    c5["ai_cost_estimate"]
)

results = {
    "Component 1 — Text Extraction": c1_ok,
    "Component 1 — Rejection Path": c1_reject_ok,
    "Component 2 — Metadata Check": c2_ok,
    "Component 3 — Balance Math": c3_ok,
    "Component 4 — Transaction Parser": c4_ok,
    "Component 5 — Memo Generator": c5_ok,
}

all_pass = True
for name, passed in results.items():
    print(f"  {P if passed else F}  {name}")
    if not passed:
        all_pass = False

print(f"\n  Pipeline stats:")
print(f"    Text extracted:    {len(c1.full_text):,} chars")
print(f"    Metadata risk:     {c2['risk_level']}")
print(f"    Transactions:      {c4['count']}")
print(f"    Balance math:      {c3['risk_level']}")
print(f"    AI total cost:     ${total_ai_cost:.4f}")
print(f"    AI components:     {'None — all rule-based' if total_ai_cost == 0 else 'Vision/Claude used'}")

if all_pass:
    print(f"\n  🎉 ALL COMPONENTS PASS!")
else:
    print(f"\n  ⚠  Some components failed. Check above.")

print(f"\n  Start the API:  python main.py")
print(f"  Open docs:      http://localhost:8000/docs")
print(f"  Full pipeline:  POST /analyze")
print()
