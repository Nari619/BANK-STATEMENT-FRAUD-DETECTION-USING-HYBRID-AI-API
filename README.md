# StatementIQ — Component 1
## PDF Text Extraction + Vision AI Fallback

Upload a bank statement PDF → get clean, structured text back.

### How It Works

```
PDF comes in
    │
    ├── Text extraction works?  → YES → use it. Done. No AI. No cost.
    │
    ├── Text extraction fails?  → Is the image readable?
    │                                 │
    │                                 ├── YES → GPT-4.1 Vision. Done.
    │                                 │
    │                                 └── NO → Reject.
    │                                          No AI cost wasted.
```

### Quick Start

```bash
# 1. Clone / download the project
cd statementiq

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env and add your OpenAI API key (optional — only needed for scanned PDFs)

# 4. Generate test bank statements
python generate_test_pdfs.py

# 5. Run tests
python test_component1.py

# 6. Start the API
python main.py
```

API will be running at:
- **Server:** http://localhost:8000
- **Swagger Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/

### Test with curl

```bash
# Test with a machine-readable PDF (no AI used)
curl -X POST http://localhost:8000/extract \
  -F 'file=@test_statements/test_chase_text.pdf'

# Test with an image-based PDF (Vision AI used)
curl -X POST http://localhost:8000/extract \
  -F 'file=@test_statements/test_scan_image.pdf'

# Test with a blank PDF (rejected)
curl -X POST http://localhost:8000/extract \
  -F 'file=@test_statements/test_blank.pdf'
```

### Project Structure

```
statementiq/
├── main.py                      # FastAPI app — the API endpoint
├── orchestrator.py              # Brain — decides which path to take
├── models.py                    # Pydantic request/response schemas
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment config template
│
├── extractors/
│   ├── pdf_text.py              # pdfplumber text extraction (NO AI)
│   └── vision_fallback.py       # GPT-4.1 Vision fallback (AI)
│
├── quality/
│   ├── text_scorer.py           # Scores extracted text quality (NO AI)
│   └── image_gate.py            # Image quality check + PDF-to-image (NO AI)
│
├── test_statements/             # Synthetic test PDFs
│   ├── test_chase_text.pdf      # Machine-readable (Path A)
│   ├── test_scan_image.pdf      # Image-based (Path B)
│   └── test_blank.pdf           # Blank/poor quality (Path C)
│
├── generate_test_pdfs.py        # Creates test PDFs
└── test_component1.py           # Integration tests for all 3 paths
```

### Components

| Sub-component | AI? | Purpose |
|---|---|---|
| PDF upload endpoint | No | Accepts the uploaded PDF |
| PDF text extractor | No | pdfplumber extracts selectable text |
| Text quality scorer | No | Decides if extracted text is usable |
| PDF-to-image converter | No | Converts image PDFs to images |
| Image quality gate | No | Rejects blurry files before AI call |
| GPT-4.1 Vision fallback | **Yes** | Reads images only when text extraction fails |

**5 out of 6 sub-components are non-AI. AI is the last resort, not the default.**

### API Response

```json
{
  "statement_id": "stmt_8f3k2j9a",
  "filename": "bank_statement.pdf",
  "total_pages": 1,
  "extraction_method": "text_extraction",
  "ai_used": false,
  "ai_cost_estimate_usd": 0.0,
  "text_quality_score": 0.853,
  "pages": [...],
  "full_text": "CHASE\nPersonal Banking Statement\n...",
  "warnings": []
}
```

### Without OpenAI API Key

The API works fine without an API key for machine-readable PDFs (most bank-generated statements). The OpenAI key is only needed for scanned/image-based PDFs. The system will clearly tell you when Vision AI is needed but unavailable.
