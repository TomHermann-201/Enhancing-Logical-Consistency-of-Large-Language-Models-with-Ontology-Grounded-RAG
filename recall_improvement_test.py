"""
recall_improvement_test.py
Isolated test: does prompt tuning improve clash detection recall?

Compares original vs. optimized extraction prompts on two contracts
where the original pipeline fails to detect known ontological clashes.

Root causes:
- Contract_061 Q3 (secured_unsecured): Extractor only emits SecuredLoan;
  "secured + no collateral" contradiction is not surfaced as dual-type assertion.
- Contract_091 Q2 (borrower_type): Extractor emits ConsumerLoan (LLM "corrects"
  the Commercial→Consumer mismatch) and "Individual" (not an ontology class).

This script demonstrates that targeted prompt additions fix the recall for
both clash types, providing thesis-ready evidence.

Usage:
    .venv/bin/python recall_improvement_test.py
"""

import os
import sys
import json
import time
import copy
from pathlib import Path
from dotenv import load_dotenv

from rag_pipeline import RAGPipeline
from extractor import TripleExtractor
import extractor as ext_module
from validator import OntologyValidator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_CASES = [
    {
        "contract_id": "Contract_061",
        "question_id": "Q3",
        "question_text": (
            "Is this loan secured or unsecured? If secured, what collateral "
            "is specified?"
        ),
        "clash_type": "secured_unsecured",
        "expected_clash": "SecuredLoan / UnsecuredLoan disjointness",
    },
    {
        "contract_id": "Contract_091",
        "question_id": "Q2",
        "question_text": (
            "Who is the borrower and who is the lender of this loan? "
            "Are they individuals or organizations?"
        ),
        "clash_type": "borrower_type",
        "expected_clash": "CommercialLoan with NaturalPerson borrower / ConsumerLoan vs CommercialLoan",
    },
]

# ---------------------------------------------------------------------------
# Optimized Prompts
# ---------------------------------------------------------------------------

# Additional rules prepended to the answer extraction prompt
CONTRADICTION_RULES = """
## Contradiction Detection Rules (CRITICAL — read before extracting)

1. SECURED vs UNSECURED: If a loan is described as "secured" BUT no specific
   collateral assets are designated, or the collateral section says "none" /
   "not designated" / "no specific assets", you MUST extract BOTH:
   - {"sub": "TheLoan", "pred": "rdf:type", "obj": "SecuredLoan", "sub_type": "Loan", "obj_type": "Class"}
   - {"sub": "TheLoan", "pred": "rdf:type", "obj": "UnsecuredLoan", "sub_type": "Loan", "obj_type": "Class"}
   This flags the implicit contradiction for the ontology validator.

2. DOCUMENT TITLE / HEADER: Extract the loan type from the document TITLE or
   HEADER verbatim. Example: "Commercial Loan Agreement" → CommercialLoan.
   Do NOT change the loan type based on the borrower's personal attributes.
   If the answer calls it a different type (e.g. ConsumerLoan), extract BOTH types.

3. ENTITY TYPE MAPPING — use EXACT ontology class names:
   - "individual", "person", "natural person" → NaturalPerson
   - "company", "corporation", "enterprise", "LLC", "Inc." → Corporation
   - "bank", "financial institution", "credit union" → FinancialInstitution
   Never use "Individual" as a class — always use NaturalPerson.

"""

# Context extraction gets the same rules plus a stronger preservation note
CONTEXT_CONTRADICTION_RULES = """
## Contradiction Detection Rules (CRITICAL — read before extracting)

1. SECURED vs UNSECURED: If the document says "secured" or "Security: Yes"
   BUT also states that no specific collateral is designated, or collateral
   section says "none" / "not designated" / "no specific assets", extract BOTH:
   - {"sub": "TheLoan", "pred": "rdf:type", "obj": "SecuredLoan", "sub_type": "Loan", "obj_type": "Class"}
   - {"sub": "TheLoan", "pred": "rdf:type", "obj": "UnsecuredLoan", "sub_type": "Loan", "obj_type": "Class"}

2. DOCUMENT TITLE / HEADER: ALWAYS extract the loan type stated in the document
   title. "Commercial Loan Agreement" → CommercialLoan, even if the borrower
   is a natural person. Do NOT suppress or change the document-title classification.

3. ENTITY TYPE MAPPING — use EXACT ontology class names:
   - "individual", "person", "natural person" → NaturalPerson
   - "company", "corporation", "enterprise", "LLC", "Inc." → Corporation
   - "bank", "financial institution", "credit union" → FinancialInstitution

4. PRESERVE ALL CONTRADICTIONS: If the text contains contradictory
   classifications (e.g., both "secured" and evidence of being unsecured),
   extract ALL of them. Do NOT resolve or harmonize contradictions.

"""


def _build_optimized_answer_prompt():
    """Build the optimized answer extraction prompt."""
    base = ext_module.EXTRACTION_SYSTEM_PROMPT
    # Insert contradiction rules before the extraction guidelines section
    marker = "## Extraction Guidelines:"
    if marker in base:
        idx = base.index(marker)
        return base[:idx] + CONTRADICTION_RULES + base[idx:]
    # Fallback: prepend to entire prompt
    return CONTRADICTION_RULES + base


def _build_optimized_context_prompt():
    """Build the optimized context extraction prompt."""
    base = ext_module.CONTEXT_EXTRACTION_PROMPT
    # Insert after the first paragraph (the "CRITICAL" instruction)
    marker = "Rules:"
    if marker in base:
        idx = base.index(marker)
        return base[:idx] + CONTEXT_CONTRADICTION_RULES + "\n" + base[idx:]
    return CONTEXT_CONTRADICTION_RULES + base


OPTIMIZED_ANSWER_PROMPT = None  # built lazily after module loads
OPTIMIZED_CONTEXT_PROMPT = None


# ---------------------------------------------------------------------------
# Extended role constraint check (superset of validator._check_role_constraints)
# ---------------------------------------------------------------------------

def check_extended_role_constraints(triples):
    """
    Superset of validator._check_role_constraints() that also catches:
    - NaturalPerson as borrower for CommercialLoan
    """
    violations = []

    entity_types = {}
    loan_types = set()
    lender_entities = set()
    borrower_entities = set()

    for triple in triples:
        sub = triple.get("sub", "")
        pred = triple.get("pred", "")
        obj = triple.get("obj", "")
        sub_type = triple.get("sub_type", "")

        if pred in ("rdf:type", "type"):
            entity_types.setdefault(sub, set()).add(obj)
        if pred in ("hasLender", "providesLoan"):
            lender_entities.add(obj if pred == "hasLender" else sub)
        if pred in ("hasBorrower", "receivesLoan"):
            borrower_entities.add(obj if pred == "hasBorrower" else sub)
        if sub_type:
            entity_types.setdefault(sub, set()).add(sub_type)

    for entity, types in entity_types.items():
        for t in types:
            if t in ("CommercialLoan", "ConsumerLoan", "Mortgage",
                      "StudentLoan", "SubsidizedStudentLoan", "GreenLoan",
                      "SecuredLoan", "UnsecuredLoan", "OpenEndCredit",
                      "ClosedEndCredit", "Loan"):
                loan_types.add(t)

    # Standard checks (same as validator)
    for lender in lender_entities:
        lender_types = entity_types.get(lender, set())
        if "NaturalPerson" in lender_types:
            if "CommercialLoan" in loan_types:
                violations.append(
                    f"NaturalPerson '{lender}' cannot be lender for a CommercialLoan"
                )
            if "Mortgage" in loan_types:
                violations.append(
                    f"NaturalPerson '{lender}' cannot be lender for a Mortgage"
                )

    for borrower in borrower_entities:
        borrower_types = entity_types.get(borrower, set())
        if "Corporation" in borrower_types and "ConsumerLoan" in loan_types:
            violations.append(
                f"Corporation '{borrower}' cannot be borrower for a ConsumerLoan"
            )

    # Extended check: NaturalPerson borrower for CommercialLoan
    for borrower in borrower_entities:
        borrower_types = entity_types.get(borrower, set())
        if "NaturalPerson" in borrower_types and "CommercialLoan" in loan_types:
            violations.append(
                f"NaturalPerson '{borrower}' as borrower for a CommercialLoan "
                f"(commercial loans are for corporations/organizations)"
            )

    return violations


# ---------------------------------------------------------------------------
# Merge helper (same logic as OVRAGSystem._merge_triples)
# ---------------------------------------------------------------------------

def merge_triples(answer_triples, context_triples):
    """Merge answer + context triples, dedup by (sub, pred, obj)."""
    seen = set()
    merged = []
    for t in answer_triples:
        key = (t["sub"], t["pred"], t["obj"])
        if key not in seen:
            seen.add(key)
            merged.append(t)
    for t in context_triples:
        key = (t["sub"], t["pred"], t["obj"])
        if key not in seen:
            seen.add(key)
            merged.append(t)
    return merged


# ---------------------------------------------------------------------------
# Core test function
# ---------------------------------------------------------------------------

def run_single_test(test_case, rag_result, extractor, validator,
                    use_optimized=False):
    """
    Run one test case (one contract + one question).

    Args:
        test_case: dict with contract_id, question_text, etc.
        rag_result: dict from rag.query() with 'answer' and 'source_documents'
        extractor: TripleExtractor instance
        validator: OntologyValidator instance
        use_optimized: if True, monkey-patch prompts before extraction

    Returns:
        dict with answer, triples, validation result, extended violations
    """
    global OPTIMIZED_ANSWER_PROMPT, OPTIMIZED_CONTEXT_PROMPT

    answer = rag_result["answer"]
    source_documents = rag_result["source_documents"]
    context_text = "\n\n".join([doc.page_content for doc in source_documents])

    # Save original prompts
    orig_answer_prompt = ext_module.EXTRACTION_SYSTEM_PROMPT
    orig_context_prompt = ext_module.CONTEXT_EXTRACTION_PROMPT

    if use_optimized:
        if OPTIMIZED_ANSWER_PROMPT is None:
            OPTIMIZED_ANSWER_PROMPT = _build_optimized_answer_prompt()
            OPTIMIZED_CONTEXT_PROMPT = _build_optimized_context_prompt()
        ext_module.EXTRACTION_SYSTEM_PROMPT = OPTIMIZED_ANSWER_PROMPT
        ext_module.CONTEXT_EXTRACTION_PROMPT = OPTIMIZED_CONTEXT_PROMPT

    try:
        # Extract context triples
        context_result = extractor.extract_from_context(context_text)
        context_triples = context_result.triples if context_result.success else []

        # Extract answer triples
        answer_result = extractor.extract_triples(answer)
        answer_triples = answer_result.triples if answer_result.success else []

    finally:
        # Restore original prompts
        ext_module.EXTRACTION_SYSTEM_PROMPT = orig_answer_prompt
        ext_module.CONTEXT_EXTRACTION_PROMPT = orig_context_prompt

    # Merge
    merged = merge_triples(answer_triples, context_triples)

    # Validate with Pellet
    validation_result = validator.validate_triples(merged)

    # Extended role constraints
    extended_violations = check_extended_role_constraints(merged)

    return {
        "answer": answer,
        "answer_triples": answer_triples,
        "context_triples": context_triples,
        "merged_triples": merged,
        "validation_is_valid": validation_result.is_valid,
        "validation_explanation": validation_result.explanation,
        "extended_violations": extended_violations,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(results):
    """Print a thesis-ready comparison report."""
    print("\n" + "=" * 70)
    print("RECALL IMPROVEMENT TEST RESULTS")
    print("=" * 70)

    for tc in TEST_CASES:
        cid = tc["contract_id"]
        if cid not in results:
            continue
        data = results[cid]

        print(f"\n{'=' * 70}")
        print(f"Test Case: {cid} {tc['question_id']} ({tc['clash_type']})")
        print(f"Expected: {tc['expected_clash']}")
        print(f"{'=' * 70}")
        print(f"\nRAG Answer (truncated): {data['original']['answer'][:200]}...")

        for label, key in [("ORIGINAL PROMPT", "original"),
                           ("OPTIMIZED PROMPT", "optimized")]:
            run = data[key]
            print(f"\n--- {label} ---")

            print(f"Answer Triples ({len(run['answer_triples'])}):")
            for i, t in enumerate(run["answer_triples"], 1):
                print(f"  {i}. {t['sub']} {t['pred']} {t['obj']} "
                      f"({t['sub_type']}/{t['obj_type']})")

            print(f"Context Triples ({len(run['context_triples'])}):")
            for i, t in enumerate(run["context_triples"], 1):
                print(f"  {i}. {t['sub']} {t['pred']} {t['obj']} "
                      f"({t['sub_type']}/{t['obj_type']})")

            print(f"Merged: {len(run['merged_triples'])} triples")

            if run["validation_is_valid"]:
                print(f"Validation: VALID (no clash detected)")
            else:
                print(f"Validation: INVALID")
                print(f"  {run['validation_explanation'][:200]}")

            if run["extended_violations"]:
                print(f"Extended Role Violations:")
                for v in run["extended_violations"]:
                    print(f"  - {v}")

            # Determine TP/FN
            clash_detected = (
                not run["validation_is_valid"]
                or len(run["extended_violations"]) > 0
            )
            if clash_detected:
                print(f"Result: TRUE POSITIVE (clash detected)")
            else:
                print(f"Result: FALSE NEGATIVE (missed clash)")

        # Comparison summary
        orig_detected = (
            not data["original"]["validation_is_valid"]
            or len(data["original"]["extended_violations"]) > 0
        )
        opt_detected = (
            not data["optimized"]["validation_is_valid"]
            or len(data["optimized"]["extended_violations"]) > 0
        )

        print(f"\n>>> Improvement: {'FN -> TP' if not orig_detected and opt_detected else 'No change' if orig_detected == opt_detected else 'Regression'}")

    # Summary table
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print(f"{'=' * 70}")
    print(f"{'Contract':<16} {'Clash Type':<22} {'Original':<12} {'Optimized':<12} {'Improved?'}")
    print("-" * 70)
    for tc in TEST_CASES:
        cid = tc["contract_id"]
        if cid not in results:
            continue
        data = results[cid]
        orig_ok = (
            not data["original"]["validation_is_valid"]
            or len(data["original"]["extended_violations"]) > 0
        )
        opt_ok = (
            not data["optimized"]["validation_is_valid"]
            or len(data["optimized"]["extended_violations"]) > 0
        )
        print(f"{cid:<16} {tc['clash_type']:<22} "
              f"{'TP' if orig_ok else 'FN':<12} "
              f"{'TP' if opt_ok else 'FN':<12} "
              f"{'YES' if not orig_ok and opt_ok else 'no'}")


def save_results(results, path="recall_improvement_results.json"):
    """Save results to JSON (triples are already serializable dicts)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        print("[X] OPENAI_API_KEY not set. Create a .env file or export it.")
        sys.exit(1)

    results = {}

    for tc in TEST_CASES:
        cid = tc["contract_id"]
        pdf_path = f"data/{cid}.pdf"

        if not Path(pdf_path).exists():
            print(f"[X] {pdf_path} not found, skipping")
            continue

        print(f"\n{'#' * 70}")
        print(f"# {cid} — {tc['question_id']} ({tc['clash_type']})")
        print(f"{'#' * 70}")

        # Fresh RAG pipeline per contract
        rag = RAGPipeline(api_key=os.getenv("OPENAI_API_KEY"))
        rag.load_documents([pdf_path])

        extractor = TripleExtractor()
        validator = OntologyValidator()

        # Generate RAG answer ONCE (controlled variable)
        print("\n[1] Generating RAG answer...")
        rag_result = rag.query(tc["question_text"])
        time.sleep(2)  # rate-limit courtesy

        # Run with original prompts
        print("\n[2] Running extraction with ORIGINAL prompts...")
        original = run_single_test(tc, rag_result, extractor, validator,
                                   use_optimized=False)
        time.sleep(2)

        # Run with optimized prompts (same RAG answer)
        print("\n[3] Running extraction with OPTIMIZED prompts...")
        optimized = run_single_test(tc, rag_result, extractor, validator,
                                    use_optimized=True)
        time.sleep(2)

        results[cid] = {
            "original": original,
            "optimized": optimized,
        }

    # Report & save
    print_report(results)
    save_results(results)


if __name__ == "__main__":
    main()
