# Enhancing Logical Consistency of Large Language Models with Ontology-Grounded RAG

A Bachelor Thesis prototype demonstrating how formal loan ontologies (FIBO/LOAN) can detect and correct logical hallucinations in RAG-generated financial text. The system extracts structured triples from LLM answers, validates them against an OWL ontology using the Pellet reasoner, and triggers a correction loop when inconsistencies are found.

## The Problem

Standard RAG systems generate answers that sound plausible but may violate strict domain-specific logical constraints. In the loan domain, an LLM might:

- Describe a mortgage as "unsecured" while listing collateral (SecuredLoan / UnsecuredLoan disjointness)
- Call a credit card a "closed-end" loan (OpenEndCredit / ClosedEndCredit disjointness)
- Issue a consumer loan to a corporation (borrower type constraint)
- Have a natural person as lender for a commercial loan (lender type constraint)

These are not just factual errors — they are **logically impossible** according to the LOAN ontology's formal axioms.

## The Solution: OV-RAG Pipeline

A three-component pipeline with a correction loop:

```
         User Query
              │
              ▼
┌──────────────────────────────┐
│  Component A: RAG Generator  │  GPT-4o + ChromaDB + LangChain
│  Retrieve context → Answer   │
└──────────┬───────────────────┘
           │ Answer + Source Documents
           ▼
┌──────────────────────────────┐
│  Component B: Triple         │  GPT-4o → JSON triples
│  Extractor (Answer+Context)  │  Mapped to LOAN ontology classes
└──────────┬───────────────────┘
           │ Merged Triples
           ▼
┌──────────────────────────────┐
│  Component C: Ontology       │  owlready2 + Pellet Reasoner
│  Validator                   │  Disjointness + Role checks
└──────────┬───────────────────┘
           │
     ┌─────┴─────┐
     │           │
   Valid    Invalid
     │           │
     ▼           ▼
  Accept    Correction Loop (up to 3x)
              │
         Still invalid?
              │
              ▼
         Hard-Reject
```

### Key Features

- **Dual-source extraction**: Triples extracted from both the LLM answer and the source documents, then merged — catches contradictions between what the document says and what the LLM claims
- **Correction loop**: Invalid answers are re-prompted with ontology feedback up to 3 times
- **Hard-reject**: Answers that remain inconsistent after all corrections are rejected
- **4 clash types detected**: secured/unsecured, open-end/closed-end, borrower type, lender type
- **100 synthetic contracts**: 60 clean + 40 with planted ontological contradictions

## Project Structure

```
.
├── src/                              # Core pipeline modules
│   ├── rag_pipeline.py               # Component A: RAG Generator (GPT-4o + ChromaDB)
│   ├── extractor.py                  # Component B: Triple Extractor (GPT-4o → LOAN triples)
│   ├── validator.py                  # Component C: Ontology Validator (Pellet Reasoner)
│   ├── vocabulary_scanner.py         # Scans RDF files → dynamic extractor prompt
│   └── setup_ontologies.py           # Ontology setup utility
│
├── evaluation/                       # Evaluation pipeline
│   ├── evaluate.py                   # Main evaluation (100 contracts × 5 questions × 2 conditions)
│   ├── evaluate_optimized_10.py      # 10-contract run with optimized extraction prompts
│   ├── evaluate_optimized_100.py     # Full 100-contract optimized run
│   ├── generate_test_pdfs.py         # Generates 100 synthetic loan contract PDFs
│   ├── recall_improvement_test.py    # Prompt tuning A/B test for clash detection
│   └── results/                      # Evaluation outputs
│       ├── baseline/                 # Original prompts, full evaluation
│       ├── optimized_10/             # Optimized prompts, 10 contracts
│       ├── optimized_100/            # Optimized prompts, 100 contracts
│       ├── run_10q/                  # Quick 10-query test run
│       ├── run_mini/                 # Mini evaluation run
│       ├── run_10contracts/          # 10-contract evaluation
│       └── run_verify/              # Verification run
│
├── tests/                            # Test scripts (standalone, no pytest)
│   ├── test_extractor_loan_type.py   # Loan type extraction test
│   ├── test_hermit_fix.py            # Reasoner compatibility test
│   ├── test_manual_clash.py          # Manual OWL clash test (self-contained ontology)
│   ├── test_validation_loop.py       # End-to-end correction loop test
│   └── test_vocabulary_scanner.py    # Vocabulary scanner test
│
├── config/                           # Configuration files
│   ├── contract_ground_truth.json    # Ground truth for 100 contracts (labels + reference answers)
│   └── vocabulary_cache.json         # Cached ontology vocabulary + dynamic prompt
│
├── data/                             # 100 synthetic loan contract PDFs
│   └── Contract_001..100.pdf
│
├── ontologies/                       # FIBO/LOAN ontology RDF files
│   ├── loans general module/         # Loans.rdf (base classes)
│   ├── loans specific module/        # ConsumerLoans, CommercialLoans, StudentLoans, etc.
│   └── real estate loans module/     # Mortgages.rdf
│
├── docs/                             # Documentation
│   ├── REQUIREMENTS.md               # Original requirements specification
│   └── PHASE_1_PLAN.md               # Phase 1 implementation plan
│
├── main.py                           # CLI entry point
├── app.py                            # Streamlit Web UI (Demo, Batch, Dashboard)
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment variable template
└── README.md
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| LLM | OpenAI GPT-4o |
| RAG Orchestration | LangChain |
| Vector DB | ChromaDB (local, transient) |
| Embeddings | text-embedding-3-small |
| Ontology Reasoning | owlready2 + Pellet Reasoner |
| Ontology Format | RDF/XML (FIBO/LOAN) |
| Web UI | Streamlit + Plotly |
| NLP Metrics | rouge-score, bert-score |
| PDF Generation | ReportLab |

## Installation

### Prerequisites

- Python 3.10+
- Java Runtime (for Pellet reasoner) — Java 11+ recommended
- OpenAI API key

### Setup

```bash
# 1. Clone
git clone https://github.com/yourusername/Enhancing-Logical-Consistency-of-Large-Language-Models-with-Ontology-Grounded-RAG.git
cd Enhancing-Logical-Consistency-of-Large-Language-Models-with-Ontology-Grounded-RAG

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API key
cp .env.example .env
# Edit .env and add your OpenAI API key: OPENAI_API_KEY=sk-...

# 5. Place LOAN ontology files in ontologies/ (see structure above)

# 6. Generate test contracts (optional — 100 synthetic PDFs)
python evaluation/generate_test_pdfs.py
```

## Usage

### CLI — Single Query

```bash
python main.py --query "Is this loan secured or unsecured?" --docs data/Contract_001.pdf
```

### CLI — Interactive Mode

```bash
python main.py --docs data/Contract_061.pdf
# Then type queries at the prompt
```

### CLI — RAG Only (no validation)

```bash
python main.py --no-validate --query "What type of loan is this?"
```

### Streamlit Web UI

```bash
streamlit run app.py
```

Three pages:
- **Demo**: Select a contract, ask a question, see the full pipeline step by step
- **Batch Evaluation**: Run evaluation over multiple contracts and questions
- **Dashboard**: Visualize evaluation results (confusion matrix, NLP metrics, latency)

### Evaluation Pipeline

```bash
# Full evaluation (100 contracts × 5 questions × 2 conditions = 1000 queries)
.venv/bin/python evaluation/evaluate.py

# Dry run (print plan, no API calls)
.venv/bin/python evaluation/evaluate.py --dry-run

# Subset: specific contracts and questions
.venv/bin/python evaluation/evaluate.py --contracts 001 061 076 --questions Q1 Q3

# OV-RAG only (skip plain RAG baseline)
.venv/bin/python evaluation/evaluate.py --conditions ovrag

# Resume interrupted run
.venv/bin/python evaluation/evaluate.py --resume

# Optimized prompts (10 representative contracts)
.venv/bin/python evaluation/evaluate_optimized_10.py

# Optimized prompts (full 100 contracts)
.venv/bin/python evaluation/evaluate_optimized_100.py
```

## Test Data: 100 Synthetic Contracts

Generated by `evaluation/generate_test_pdfs.py` with `random.seed(42)` for reproducibility.

| Range | Count | Label | Description |
|-------|-------|-------|-------------|
| 001–060 | 60 | CLEAN | Diverse loan types, no ontological contradictions |
| 061–075 | 15 | CLASH | **Secured vs Unsecured** — e.g., mortgage listed as "unsecured" with collateral |
| 076–090 | 15 | CLASH | **OpenEnd vs ClosedEnd** — e.g., credit card with fixed maturity date |
| 091–095 | 5 | CLASH | **Borrower Type** — e.g., ConsumerLoan issued to a corporation |
| 096–100 | 5 | CLASH | **Lender Type** — e.g., CommercialLoan from a natural person |

Ground truth including reference answers for NLP metrics is stored in `config/contract_ground_truth.json`.

## Evaluation Metrics

The evaluation pipeline measures:

### Clash Detection (OV-RAG condition)
- **Precision**: Of all answers flagged as inconsistent, how many actually contain clashes?
- **Recall**: Of all planted clashes, how many were detected?
- **F1 Score**: Harmonic mean of precision and recall
- **Confusion Matrix**: TP (clash detected), TN (clean passed), FP (false alarm), FN (missed clash)
- **Per-clash-type breakdown**: Detection rate for each of the 4 clash types

### Answer Quality (both conditions)
- **ROUGE-L**: Textual overlap between generated answer and ground truth reference
- **BERTScore-F1**: Semantic similarity between generated answer and reference

### Efficiency
- **Latency per query**: RAG time, extraction time, validation time, total time
- **Latency overhead**: Additional cost of the ontology validation layer vs plain RAG

### Evaluation Results (Optimized Prompts, 10 Contracts)

| Metric | Value |
|--------|-------|
| Precision | 0.556 |
| Recall | 0.200 |
| F1 | 0.294 |
| Avg BERTScore-F1 | 0.895 |
| Avg ROUGE-L | 0.356 |
| Avg Latency (OV-RAG) | 10.5s |
| Hard-Reject Rate | 18% |

## LOAN Ontology

The project uses FIBO-based LOAN ontology modules with the following key concepts:

### Classes (Loan Types)
`Loan`, `ConsumerLoan`, `CommercialLoan`, `Mortgage`, `StudentLoan`, `SubsidizedStudentLoan`, `GreenLoan`, `CardAccount`

### Classes (Credit Types)
`SecuredLoan`, `UnsecuredLoan`, `OpenEndCredit`, `ClosedEndCredit`

### Classes (Entities)
`Lender`, `Borrower`, `Corporation`, `FinancialInstitution`, `NaturalPerson`

### Key Properties
`hasLender`, `hasBorrower`, `hasCollateral`, `hasLoanAmount`, `hasInterestRate`, `hasMaturityDate`, `rdf:type`

### Disjointness Axioms (Critical for Clash Detection)
- `SecuredLoan` ⊥ `UnsecuredLoan` — a loan cannot be both secured and unsecured
- `OpenEndCredit` ⊥ `ClosedEndCredit` — a loan cannot be both revolving and fixed-term
- `ConsumerLoan` ⊥ `CommercialLoan` — consumer and commercial are distinct categories

## How It Works

### 1. RAG Generation (Component A)

```python
from rag_pipeline import RAGPipeline

rag = RAGPipeline(api_key="sk-...")
rag.load_documents(["data/Contract_061.pdf"])
result = rag.query("Is this loan secured or unsecured?")
print(result["answer"])
```

The PDF is chunked (1000 chars, 200 overlap), embedded with `text-embedding-3-small`, stored in ChromaDB, and the top-3 chunks are retrieved as context for GPT-4o.

### 2. Triple Extraction (Component B)

```python
from extractor import TripleExtractor

extractor = TripleExtractor()
# Extract from LLM answer
result = extractor.extract_triples(answer_text)
# Extract from source documents (preserves contradictions)
context_result = extractor.extract_from_context(source_text)
```

Produces JSON triples like:
```json
{"sub": "TheLoan", "pred": "rdf:type", "obj": "SecuredLoan", "sub_type": "Loan", "obj_type": "Class"}
{"sub": "TheLoan", "pred": "rdf:type", "obj": "UnsecuredLoan", "sub_type": "Loan", "obj_type": "Class"}
```

The extractor uses a dynamic prompt generated from the ontology vocabulary (`config/vocabulary_cache.json`) if available, or falls back to a static prompt.

### 3. Ontology Validation (Component C)

```python
from validator import OntologyValidator

validator = OntologyValidator()
result = validator.validate_triples(merged_triples)

if not result.is_valid:
    print(f"Inconsistency: {result.explanation}")
    # e.g., "SecuredLoan and UnsecuredLoan are disjoint classes"
```

The validator:
1. Loads the LOAN ontology RDF files
2. Creates OWL individuals from the extracted triples
3. Runs the Pellet reasoner to check for logical consistency
4. Performs additional role-constraint checks (borrower/lender type rules)

### 4. Correction Loop

When validation fails, the system re-prompts GPT-4o with the validation feedback:

```
"Your previous answer was flagged as logically inconsistent:
 SecuredLoan and UnsecuredLoan are disjoint — a loan cannot be both.
 Please correct your answer..."
```

Up to 3 correction attempts. If still invalid → **Hard-Reject**.

## Configuration

| Parameter | Location | Default | Description |
|-----------|----------|---------|-------------|
| `OPENAI_API_KEY` | `.env` | — | OpenAI API key |
| `temperature` | `src/rag_pipeline.py` | 0.7 | RAG generation temperature |
| `top_k` | `src/rag_pipeline.py` | 3 | Number of chunks to retrieve |
| `chunk_size` | `src/rag_pipeline.py` | 1000 | Text chunk size |
| `MAX_CORRECTION_ATTEMPTS` | `main.py` | 3 | Max correction loop iterations |
| `JAVA_MEMORY` | `src/validator.py` | 4000 | Java heap for Pellet (MB) |

## Running Tests

```bash
# Loan type extraction
python tests/test_extractor_loan_type.py

# Reasoner compatibility
python tests/test_hermit_fix.py

# Manual OWL clash (no API key needed)
python tests/test_manual_clash.py

# End-to-end correction loop
python tests/test_validation_loop.py

# Vocabulary scanner
python tests/test_vocabulary_scanner.py
```

## Known Limitations

1. **HermiT reasoner retired**: HermiT does not support `langString` datatypes in FIBO RDF files. The system uses **Pellet** exclusively.

2. **Recall depends on extraction quality**: If the extractor fails to produce dual-type triples (e.g., both `SecuredLoan` and `UnsecuredLoan`), the validator cannot detect the clash. Optimized prompts improve recall from 0% to 20%.

3. **Java dependency**: The Pellet reasoner requires a Java runtime. Tested with Java 25.

4. **Rate limits**: The evaluation pipeline includes `tenacity` retry (5 attempts, exponential backoff) and a 2-second cooldown between API calls to handle OpenAI 429 errors.

5. **Memory**: Pellet reasoning requires ~4 GB Java heap. Configurable via `JAVA_MEMORY`.

## Research Context

This project investigates three research questions:

1. **Can formal ontologies detect logical hallucinations in RAG-generated financial text?**
   Yes — the Pellet reasoner detects disjointness violations (SecuredLoan ⊥ UnsecuredLoan, OpenEndCredit ⊥ ClosedEndCredit) when the extractor produces the correct triples.

2. **Does a correction loop improve answer quality?**
   Partially — the correction success rate is ~10%, meaning most clashes persist through all 3 correction attempts and result in a hard-reject.

3. **What is the latency cost of ontology validation?**
   The validation layer adds ~5–15 seconds per query depending on the number of extracted triples and whether corrections are triggered.

## License

This project is licensed under the MIT License.

## References

- [Owlready2](https://owlready2.readthedocs.io/) — Python ontology-oriented programming
- [LangChain](https://langchain.com/) — LLM application framework
- [Pellet Reasoner](https://github.com/stardog-union/pellet) — OWL-DL reasoner
- [FIBO](https://spec.edmcouncil.org/fibo/) — Financial Industry Business Ontology
- [OpenAI API](https://platform.openai.com/docs/api-reference)
- [ChromaDB](https://www.trychroma.com/) — Vector database
