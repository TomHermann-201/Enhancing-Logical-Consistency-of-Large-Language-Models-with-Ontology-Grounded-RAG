"""
evaluate_optimized_10.py
Run the standard evaluation pipeline on 10 representative contracts
with the OPTIMIZED extraction prompts (from recall_improvement_test.py).

Contracts selected:
  Clean  : 001, 010, 020, 030, 040  (diverse loan types)
  Clash  : 061 (secured_unsecured), 070 (secured_unsecured),
           076 (openend_closedend), 091 (borrower_type), 096 (lender_type)

Conditions: ovrag only (plain RAG doesn't use extraction at all)
Questions : Q1–Q5

Usage:
    .venv/bin/python evaluate_optimized_10.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    print("[X] OPENAI_API_KEY not set")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 1. Monkey-patch the extraction prompts BEFORE importing evaluate/extractor
# ---------------------------------------------------------------------------
from recall_improvement_test import (
    CONTRADICTION_RULES,
    CONTEXT_CONTRADICTION_RULES,
)
import extractor as ext_module

# Build optimized answer prompt
_base_answer = ext_module.EXTRACTION_SYSTEM_PROMPT
_marker = "## Extraction Guidelines:"
if _marker in _base_answer:
    _idx = _base_answer.index(_marker)
    ext_module.EXTRACTION_SYSTEM_PROMPT = (
        _base_answer[:_idx] + CONTRADICTION_RULES + _base_answer[_idx:]
    )
else:
    ext_module.EXTRACTION_SYSTEM_PROMPT = CONTRADICTION_RULES + _base_answer

# Build optimized context prompt
_base_ctx = ext_module.CONTEXT_EXTRACTION_PROMPT
_marker_ctx = "Rules:"
if _marker_ctx in _base_ctx:
    _idx_ctx = _base_ctx.index(_marker_ctx)
    ext_module.CONTEXT_EXTRACTION_PROMPT = (
        _base_ctx[:_idx_ctx] + CONTEXT_CONTRADICTION_RULES + "\n" + _base_ctx[_idx_ctx:]
    )
else:
    ext_module.CONTEXT_EXTRACTION_PROMPT = CONTEXT_CONTRADICTION_RULES + _base_ctx

print("[OK] Extraction prompts patched with optimized contradiction rules")

# ---------------------------------------------------------------------------
# 2. Import evaluate and run
# ---------------------------------------------------------------------------
from evaluate import EvaluationRunner, QUESTIONS

CONTRACTS = [
    # 5 clean
    "001", "010", "020", "030", "040",
    # 5 clash (one from each type, two for secured_unsecured)
    "061", "070", "076", "091", "096",
]

OUTPUT_DIR = "evaluation_optimized_10"

runner = EvaluationRunner(
    contracts=CONTRACTS,
    questions=[q["id"] for q in QUESTIONS],
    conditions=["ovrag"],          # only OV-RAG (plain doesn't use extraction)
    output_dir=OUTPUT_DIR,
    resume=False,
    dry_run=False,
)

print(f"\nRunning evaluation on {len(CONTRACTS)} contracts x 5 questions x ovrag = {len(CONTRACTS)*5} queries")
print(f"Output directory: {OUTPUT_DIR}/")
runner.run()
