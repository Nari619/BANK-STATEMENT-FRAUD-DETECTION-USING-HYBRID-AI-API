"""
StatementIQ API — Full MVP
5 Components: Text Extraction, Metadata Check, Balance Math, 
Transaction Parser, Memo Generator

Run: python main.py
Docs: http://localhost:8000/docs
"""

import os
import sys
import tempfile
import shutil
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator import process_statement
from extractors.metadata_check import check_metadata
from extractors.transaction_parser import parse_transactions
from extractors.balance_check import verify_balances
from extractors.memo_generator import generate_memo
from models import ExtractionResponse, RejectionResponse


# ── App Setup ──────────────────────────────────────────────
app = FastAPI(
    title="StatementIQ API",
    description=(
        "Bank statement fraud detection + cashflow intelligence.\n\n"
        "**5 Components:**\n"
        "1. PDF Text Extraction (No AI / Vision AI fallback)\n"
        "2. Metadata Fraud Check (No AI)\n"
        "3. Balance Math Verification (No AI)\n"
        "4. Transaction Parser (Regex + Claude AI fallback)\n"
        "5. Underwriting Memo Generator (Template + Claude AI)\n\n"
        "**Architecture:** ~70% rule-based, ~30% AI. "
        "AI is never the sole decision-maker."
    ),
    version="0.2.0",
)


def _save_upload(file: UploadFile) -> tuple[str, str, bytes]:
    """Validate and save uploaded PDF to temp file. Returns (temp_dir, temp_path, contents)."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, f"Only PDF files accepted. Got: {file.filename}")
    return file.filename


# ── Health Check ───────────────────────────────────────────
@app.get("/", tags=["Health"])
def health():
    key = os.getenv("ANTHROPIC_API_KEY", "")
    has_key = bool(key) and not key.startswith("sk-ant-your")
    
    return {
        "status": "running",
        "service": "StatementIQ MVP",
        "version": "0.2.0",
        "api_provider": "Anthropic (Claude) — single key for everything",
        "api_key_configured": has_key,
        "components": {
            "1_text_extraction": "ready (rules) / " + ("ready (Claude Vision)" if has_key else "no key (Claude Vision)"),
            "2_metadata_check": "ready (rules only, no AI needed)",
            "3_balance_math": "ready (rules only, no AI needed)",
            "4_transaction_parser": "ready (regex) / " + ("ready (Claude)" if has_key else "no key (Claude)"),
            "5_memo_generator": "ready (template) / " + ("ready (Claude)" if has_key else "no key (Claude)"),
        },
    }


# ── Component 1: Text Extraction ──────────────────────────
@app.post("/extract", tags=["Component 1 — Text Extraction"],
    summary="Extract text from bank statement PDF",
    description="Upload PDF → get clean text. AI used only if normal extraction fails.")
async def extract_text(file: UploadFile = File(...)):
    contents = await file.read()
    if len(contents) < 100:
        raise HTTPException(400, "File too small to be a valid PDF.")
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 20MB.")
    
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    try:
        with open(temp_path, "wb") as f:
            f.write(contents)
        result = process_statement(temp_path, api_key=os.getenv("ANTHROPIC_API_KEY"))
        if isinstance(result, RejectionResponse):
            return JSONResponse(status_code=422, content=result.model_dump())
        return result
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ── Component 2: Metadata Check ───────────────────────────
@app.post("/verify-metadata", tags=["Component 2 — Metadata Check"],
    summary="Check PDF metadata for fraud signals",
    description="Reads Creator, Producer, dates, Author. No AI. Catches Canva fakes instantly.")
async def verify_metadata(file: UploadFile = File(...)):
    contents = await file.read()
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    try:
        with open(temp_path, "wb") as f:
            f.write(contents)
        return check_metadata(temp_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ── Component 4: Transaction Parser ───────────────────────
@app.post("/parse-transactions", tags=["Component 4 — Transaction Parser"],
    summary="Parse transactions from extracted text",
    description="Regex for known banks (free). Claude API fallback for unknown formats (AI cost only when needed).")
async def parse_txns(file: UploadFile = File(...)):
    contents = await file.read()
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    try:
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        # First extract text (Component 1)
        extraction = process_statement(temp_path, api_key=os.getenv("ANTHROPIC_API_KEY"))
        if isinstance(extraction, RejectionResponse):
            return JSONResponse(status_code=422, content={"error": extraction.reason})
        
        # Then parse transactions (Component 4)
        return parse_transactions(
            extraction.full_text, 
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ── Component 3: Balance Math ─────────────────────────────
@app.post("/verify-balances", tags=["Component 3 — Balance Math"],
    summary="Verify running balance arithmetic",
    description="Checks every row: prev_balance + amount = current_balance. No AI. Pure math.")
async def verify_balance(file: UploadFile = File(...)):
    contents = await file.read()
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    try:
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        # Extract text → parse transactions → verify math
        extraction = process_statement(temp_path, api_key=os.getenv("ANTHROPIC_API_KEY"))
        if isinstance(extraction, RejectionResponse):
            return JSONResponse(status_code=422, content={"error": extraction.reason})
        
        txn_result = parse_transactions(
            extraction.full_text,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        
        return verify_balances(txn_result["transactions"])
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════
# FULL PIPELINE — Runs all 5 components in sequence
# ══════════════════════════════════════════════════════════
@app.post("/analyze", tags=["Full Pipeline"],
    summary="Full analysis: extract + metadata + parse + math + memo",
    description=(
        "Runs all 5 components on one PDF upload:\n"
        "1. Extract text from PDF\n"
        "2. Check metadata for fraud signals\n"
        "3. Parse transactions (regex → Claude fallback)\n"
        "4. Verify balance math\n"
        "5. Generate underwriting memo\n\n"
        "Returns everything in one response."
    ))
async def full_analysis(
    file: UploadFile = File(...),
    context: str = Query("tenant_screening", description="'tenant_screening' or 'lending'"),
    monthly_obligation: float = Query(0.0, description="Monthly rent or loan payment amount"),
):
    contents = await file.read()
    if len(contents) < 100:
        raise HTTPException(400, "File too small.")
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 20MB.")
    
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_path, "wb") as f:
            f.write(contents)
        
        results = {"ai_total_cost": 0.0, "warnings": []}
        
        # ── Component 1: Text Extraction ──
        extraction = process_statement(temp_path, api_key=os.getenv("ANTHROPIC_API_KEY"))
        if isinstance(extraction, RejectionResponse):
            return JSONResponse(status_code=422, content={
                "rejected": True,
                "reason": extraction.reason,
                "suggestion": extraction.suggestion,
            })
        
        results["extraction"] = {
            "method": extraction.extraction_method,
            "ai_used": extraction.ai_used,
            "text_quality": extraction.text_quality_score,
            "pages": extraction.total_pages,
            "chars_extracted": len(extraction.full_text),
        }
        results["ai_total_cost"] += extraction.ai_cost_estimate_usd
        
        # ── Component 2: Metadata Check ──
        metadata = check_metadata(temp_path)
        results["metadata"] = metadata
        
        # ── Component 4: Transaction Parser ──
        txn_result = parse_transactions(
            extraction.full_text,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
        results["transactions"] = {
            "count": txn_result["count"],
            "bank_detected": txn_result["bank_detected"],
            "parser_used": txn_result["parser_used"],
            "ai_used": txn_result["ai_used"],
            "income_summary": txn_result["income_summary"],
            "transactions": txn_result["transactions"][:10],  # first 10 for preview
            "total_in_response": min(10, txn_result["count"]),
            "total_available": txn_result["count"],
        }
        results["ai_total_cost"] += txn_result["ai_cost_estimate"]
        results["warnings"].extend(txn_result["warnings"])
        
        # ── Component 3: Balance Math ──
        balance = verify_balances(txn_result["transactions"])
        results["balance_verification"] = balance
        
        # ── Component 5: Memo Generator ──
        memo = generate_memo(
            metadata_result=metadata,
            transaction_result=txn_result,
            balance_result=balance,
            context=context,
            monthly_obligation=monthly_obligation,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        )
        results["memo"] = {
            "text": memo["memo"],
            "recommendation": memo["recommendation"],
            "ai_used": memo["ai_used"],
        }
        results["ai_total_cost"] += memo["ai_cost_estimate"]
        
        # ── Overall Summary ──
        fraud_signals = [s for s in metadata.get("signals", []) 
                        if s["severity"] in ("critical", "high")]
        
        results["summary"] = {
            "document_risk": metadata.get("risk_level", "unknown"),
            "balance_math_valid": balance["is_valid"],
            "total_fraud_signals": len(fraud_signals),
            "total_transactions": txn_result["count"],
            "total_ai_cost_usd": round(results["ai_total_cost"], 4),
            "verdict": _determine_verdict(metadata, balance, fraud_signals),
        }
        
        return results
    
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _determine_verdict(metadata, balance, fraud_signals):
    """Determine overall verdict based on all signals."""
    meta_risk = metadata.get("risk_level", "unknown")
    
    if meta_risk == "critical" or len(fraud_signals) >= 2:
        return "HIGH_RISK — Multiple fraud indicators detected. Do not proceed."
    elif meta_risk == "high" or not balance["is_valid"]:
        return "SUSPICIOUS — Document integrity concerns. Verify with bank directly."
    elif meta_risk == "medium":
        return "REVIEW — Minor concerns detected. Additional verification recommended."
    else:
        return "CLEAN — No fraud signals detected. Document appears authentic."


# ── Run Server ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    print("\n" + "=" * 56)
    print("  StatementIQ API — Full MVP (5 Components)")
    print("  Powered by Anthropic Claude — single API key")
    print("=" * 56)
    print(f"\n  Server:    http://localhost:{port}")
    print(f"  Docs:      http://localhost:{port}/docs")
    print(f"\n  Endpoints:")
    print(f"    POST /extract            Component 1 — Text Extraction")
    print(f"    POST /verify-metadata    Component 2 — Metadata Check")
    print(f"    POST /parse-transactions Component 4 — Transaction Parser")
    print(f"    POST /verify-balances    Component 3 — Balance Math")
    print(f"    POST /analyze            Full Pipeline (all 5)")
    
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or key.startswith("sk-ant-your"):
        print("\n  ⚠  No Anthropic API key set.")
        print("     Rules-based components work fine (metadata, math, regex).")
        print("     Claude features disabled (vision, LLM parsing, rich memos).")
        print("     Add ANTHROPIC_API_KEY to .env to enable them.")
    else:
        print("\n  ✓  Anthropic API key configured.")
        print("     All components ready — rules + Claude AI.")
    
    print("\n" + "=" * 56 + "\n")
    
    uvicorn.run(app, host=host, port=port)
