# StatementIQ — Bank Statement Fraud Detection Using Hybrid AI

## Why I Built This

I found a real problem that no one has solved affordably.

**36% of the US workforce** earns through gig work, freelancing, or self-employment. When they apply for housing or loans, they submit PDF bank statements. Two things go wrong:

1. **Landlords can't detect fakes.** 1 in 16 documents submitted to lenders show signs of fraud. AI-generated fake bank statements increased 5x in 2025. A single fraudulent tenant costs $15K–$30K in eviction and lost rent.

2. **Manual review takes forever.** Landlords eyeball PDFs. Non-QM loan officers spend 30–60 minutes per statement set. They're not financial analysts — they're guessing.

**Existing solutions don't serve small operators:**
- **Plaid LendScore** — requires Plaid Link integration. Doesn't accept PDF uploads.
- **Inscribe** — detects fraud but doesn't analyze cashflow. Enterprise pricing.
- **Ocrolus** — does both but costs $5K+/year and users report slow processing.

**Nobody built an affordable, fast API combining fraud detection + cashflow intelligence for PDF bank statements.** That's the gap. That's what StatementIQ fills — at $0.02 per document instead of $5,000/year.

---

## Why This Matters for Product Management

This project demonstrates five PM competencies in one artifact:

**1. User Research → Problem Discovery**
The problem wasn't found by Googling. It was found by understanding who receives bank statements as PDFs (landlords, non-QM lenders, small credit unions), what they do with them (manual review), and what tools they have (none they can afford).

**2. Competitive Analysis → Positioning**
I researched Plaid, Inscribe, Ocrolus, DocuClipper, and Veryfi. Each has a gap. StatementIQ isn't better than Inscribe — it's Inscribe for the 90% who can't afford enterprise pricing. That's a product positioning decision, not a technical one.

**3. Architecture Decisions → Where AI Helps and Where It Hurts**
The most important PM decision in this project was choosing where to use AI and where NOT to. I chose a hybrid approach: 70% rules-based (metadata forensics, balance math, regex parsing) and 30% AI (Claude Vision for scanned documents, Claude for memo generation). The AI never makes the final fraud decision. The rules do. The AI reads documents and writes English — tasks where deterministic logic fails.

This matters because at any AI company, PMs must decide where AI creates genuine value versus where it introduces unnecessary risk. A PM who puts AI everywhere is as dangerous as one who avoids it entirely.

**4. Metrics Framework → Measuring What Matters**
If this were a real product: fraud detection precision (target >90%), false positive rate (<5%), time-to-decision reduction (from 45 min manual review to <30 seconds), adoption rate among property managers with 5–50 units.

**5. Technical Literacy → Earning Engineering Trust**
I built a working prototype, not a slide deck. Three API endpoints. Five components. Clean Swagger documentation. Engineers can read this codebase and verify every claim. The prototype proves the concept is real — the PRD I'd write alongside it proves I'm a PM, not an engineer cosplaying.

---

## Architecture — Hybrid AI (Rules + Claude)

```
PDF uploaded
     │
     ├── [pikepdf]      Read metadata           — NO AI (free)
     │                   Producer = Canva? → FRAUD SIGNAL
     │
     ├── [pdfplumber]    Extract text             — NO AI (free)
     │                   Text readable? → use it
     │                   Text empty? → Claude Vision reads the image
     │
     ├── [regex/Claude]  Parse transactions       — HYBRID
     │                   Known bank? → regex (free, instant)
     │                   Unknown bank? → Claude API ($0.01)
     │
     ├── [pandas]        Verify balance math      — NO AI (free)
     │                   Row-by-row arithmetic check
     │                   Also catches Claude parsing errors
     │
     └── [template/Claude] Generate memo          — HYBRID
                          Numbers from template (verified)
                          Narrative from Claude (never generates $amounts)
```

**Key architectural rule:** The AI never generates a number. The AI never makes the fraud decision. Numbers come from pandas math. Fraud signals come from deterministic rules. Claude reads messy documents and writes English. If Claude hallucinates, the verified numbers visible in the output contradict it — the human reader sees both.

---

## What This Catches vs. What It Doesn't

**Catches (~70-80% of real-world fraud):**
- PDFs created in Canva, Photoshop, Google Docs (metadata forensics)
- Edited statements where someone changed a deposit but forgot to update running balances (balance math)
- Statements with dates that don't make sense (creation date vs. statement period)
- Documents with an individual's name in the Author field (banks use systems, not people)

**Does NOT catch:**
- AI-generated fake statements with spoofed metadata, correct math, and realistic transaction patterns
- Pixel-perfect visual forgeries created by tools trained on real bank templates

Catching those requires computer vision models trained on millions of documents — what Inscribe spent 8+ years and millions of dollars building. This prototype honestly acknowledges that limitation. Stating what your product can't do is a PM skill, not a weakness.

---

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Generate test bank statements (real + fake)
python generate_test_pdfs.py

# Run tests — all 5 components
python test_all_components.py

# Start the API
python main.py

# Open docs
# http://localhost:8000/docs
```

**Without API key:** Rules-based components work perfectly (metadata, math, regex). No cost.

**With API key:** Add `ANTHROPIC_API_KEY` to `.env` file to enable Claude Vision (scanned PDFs), Claude transaction parsing (unknown bank formats), and richer memo narratives.

---

## API Endpoints

| Endpoint | What It Does | AI? |
|---|---|---|
| `POST /extract` | PDF → clean text | No (Claude Vision fallback for scans) |
| `POST /verify-metadata` | PDF → fraud signals | No |
| `POST /parse-transactions` | PDF → structured transactions | No (Claude fallback for unknown banks) |
| `POST /verify-balances` | PDF → math verification | No |
| **`POST /analyze`** | **Full pipeline — all 5 components** | **Only when rules can't handle it** |

---

## Tech Stack

- **Python 3.11+** / **FastAPI** — API framework
- **pdfplumber** — text extraction from PDFs
- **pikepdf** — PDF metadata forensics
- **pandas** — balance arithmetic verification
- **Anthropic Claude API** — vision OCR + transaction parsing + memo generation
- **Pydantic** — request/response validation

---

## Project Structure

```
statementiq/
├── main.py                         # FastAPI app — all endpoints
├── orchestrator.py                 # Decides: text vs. vision vs. reject
├── models.py                       # Pydantic schemas
├── extractors/
│   ├── pdf_text.py                 # Component 1: pdfplumber extraction
│   ├── vision_fallback.py          # Component 1: Claude Vision fallback
│   ├── metadata_check.py           # Component 2: pikepdf fraud signals
│   ├── transaction_parser.py       # Component 4: regex + Claude parsing
│   ├── balance_check.py            # Component 3: row-by-row math
│   └── memo_generator.py           # Component 5: template + Claude narrative
├── quality/
│   ├── text_scorer.py              # Scores extraction quality
│   └── image_gate.py               # Rejects blurry images before AI call
├── test_statements/                # Synthetic test PDFs
├── generate_test_pdfs.py           # Creates test data
├── test_all_components.py          # Integration tests
└── test_component1.py              # Component 1 tests
```

---

## What I'd Build in v2

With a real engineering team and production resources:

- **Multi-statement longitudinal analysis** — 12-24 months of statements, tracking income trends and seasonal patterns
- **Computer vision layer** — pixel-level forensics for AI-generated fakes (the 20% this prototype can't catch)
- **Integration with tenant screening platforms** — RentSpree, TurboTenant, Buildium
- **FCRA compliance layer** — required for any lending use case
- **Stripe-like pricing** — $1.50/statement for landlords, $0.75/statement at volume for lenders

---

*Built by [Nari619](https://github.com/Nari619) — Product Manager exploring the intersection of financial services and AI.*
