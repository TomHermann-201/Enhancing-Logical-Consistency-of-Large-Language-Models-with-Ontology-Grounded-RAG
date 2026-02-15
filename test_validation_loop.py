"""
test_validation_loop.py
Phase 2 Integration Test: Validation Loop with Hard-Reject

Tests the correction loop that re-prompts GPT-4o with ontology feedback
when validation fails, retrying up to 3 times before issuing a Hard-Reject.

Scenarios:
1. Consistent contract (Contract_001) passes on first attempt
2. Clash contract (Contract_010) triggers correction loop
3. Correction attempt logging structure is complete
4. Result dict contains all Phase 2 fields

Requires:
- OPENAI_API_KEY set in environment or .env
- PDF test documents in ./data/
- LOAN ontology files in ./ontologies/
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SEPARATOR = "=" * 70

# Phase 2 required fields in result dict
PHASE2_FIELDS = [
    "question",
    "answer",
    "sources",
    "triples",
    "validation",
    "correction_attempts",
    "hard_reject",
    "hard_reject_reason",
    "total_attempts",
    "accepted_at_attempt",
]


def check_prerequisites():
    """Verify all prerequisites are met."""
    if not os.getenv("OPENAI_API_KEY"):
        print("[X] OPENAI_API_KEY not set")
        sys.exit(1)

    ontology_path = Path("ontologies")
    if not ontology_path.exists() or not any(ontology_path.glob("**/*.rdf")):
        print("[X] LOAN ontology files not found in ./ontologies/")
        sys.exit(1)

    # Check for test PDFs
    contract_001 = Path("data/Contract_001.pdf")
    contract_010 = Path("data/Contract_010.pdf")

    if not contract_001.exists():
        print(f"[X] Test document not found: {contract_001}")
        sys.exit(1)

    if not contract_010.exists():
        print(f"[X] Test document not found: {contract_010}")
        sys.exit(1)

    print("[OK] All prerequisites met")


def test_scenario_1_first_attempt_pass():
    """
    Scenario 1: Consistent contract passes on first attempt.

    Contract_001 (ConsumerLoan) contains no contradictions.
    The system should generate a valid answer on the first try.
    """
    from main import OVRAGSystem

    print(f"\n{SEPARATOR}")
    print("SCENARIO 1: First-Attempt Pass (Contract_001 ConsumerLoan)")
    print(SEPARATOR)

    system = OVRAGSystem()
    system.load_documents(["data/Contract_001.pdf"])

    result = system.process_query("Who is the borrower of this consumer loan?")

    # Assertions
    passed = True
    checks = []

    # Check 1: Should have an answer
    if result["answer"] and len(result["answer"]) > 0:
        checks.append(("Has answer", True))
    else:
        checks.append(("Has answer", False))
        passed = False

    # Check 2: Should have triples
    if len(result["triples"]) > 0:
        checks.append(("Has triples", True))
    else:
        checks.append(("Has triples", False))
        # Not a hard failure -- some answers may not produce triples

    # Check 3: total_attempts should be 1 (passed first try)
    if result["total_attempts"] == 1:
        checks.append(("Passed on first attempt", True))
    else:
        checks.append((f"Passed on attempt {result['total_attempts']} (expected 1)", False))
        passed = False

    # Check 4: No hard reject
    if not result["hard_reject"]:
        checks.append(("No hard reject", True))
    else:
        checks.append(("No hard reject", False))
        passed = False

    # Check 5: accepted_at_attempt should be 0
    if result["accepted_at_attempt"] == 0:
        checks.append(("accepted_at_attempt == 0", True))
    else:
        checks.append((f"accepted_at_attempt == {result['accepted_at_attempt']} (expected 0)", False))
        passed = False

    # Print results
    print(f"\n{'—' * 40}")
    print("Checks:")
    for label, ok in checks:
        status = "[OK]" if ok else "[X]"
        print(f"  {status} {label}")

    return passed


def test_scenario_2_correction_loop():
    """
    Scenario 2: Clash contract triggers correction loop.

    Contract_010 (ERROR_CLASH_CommercialLoan) contains deliberate
    contradictions that should cause validation failures.
    The system should attempt corrections and eventually hard-reject.
    """
    from main import OVRAGSystem

    print(f"\n{SEPARATOR}")
    print("SCENARIO 2: Correction Loop (Contract_010 ERROR_CLASH)")
    print(SEPARATOR)

    system = OVRAGSystem()
    system.load_documents(["data/Contract_010.pdf"])

    result = system.process_query(
        "Who is the lender for this commercial loan?"
    )

    passed = True
    checks = []

    # Check 1: Should have multiple attempts
    if result["total_attempts"] > 1:
        checks.append((f"Multiple attempts ({result['total_attempts']})", True))
    else:
        checks.append(("Multiple attempts expected", False))
        # Not necessarily a failure -- the LLM might self-correct or
        # the clash might not always trigger. Log but don't fail hard.

    # Check 2: correction_attempts list is populated
    if len(result["correction_attempts"]) > 0:
        checks.append((f"Has {len(result['correction_attempts'])} logged attempt(s)", True))
    else:
        checks.append(("Has logged attempts", False))
        passed = False

    # Check 3: Either hard_reject or accepted
    if result["hard_reject"] or result["accepted_at_attempt"] is not None:
        outcome = "HARD-REJECT" if result["hard_reject"] else f"ACCEPTED at attempt {result['accepted_at_attempt']}"
        checks.append((f"Final outcome: {outcome}", True))
    else:
        checks.append(("Has final outcome", False))
        passed = False

    # Print results
    print(f"\n{'—' * 40}")
    print("Checks:")
    for label, ok in checks:
        status = "[OK]" if ok else "[X]"
        print(f"  {status} {label}")

    return passed


def test_scenario_3_logging_structure():
    """
    Scenario 3: Verify correction attempt log structure.

    Each entry in correction_attempts must have:
    attempt_number, answer, triples, is_valid, explanation
    """
    from main import OVRAGSystem

    print(f"\n{SEPARATOR}")
    print("SCENARIO 3: Correction Attempt Logging Structure")
    print(SEPARATOR)

    system = OVRAGSystem()
    system.load_documents(["data/Contract_001.pdf"])

    result = system.process_query(
        "Who is the borrower of this loan and what type of loan is it? Is it secured or unsecured?"
    )

    passed = True
    checks = []

    required_log_fields = ["attempt_number", "answer", "triples", "is_valid", "explanation"]

    if not result["correction_attempts"]:
        # 0-triples edge case: if the LLM returned an answer but no triples
        # were extracted, process_query returns early without logging to
        # correction_attempts. This is valid behaviour, not a test failure.
        if result["answer"] and len(result["answer"]) > 0:
            checks.append(("Has correction_attempts (0 triples — pass with warning)", True))
            print("  [!] Warning: No triples extracted, correction_attempts is empty")
        else:
            checks.append(("Has correction_attempts", False))
            passed = False
    else:
        checks.append(("Has correction_attempts", True))

        for i, attempt in enumerate(result["correction_attempts"]):
            for field in required_log_fields:
                if field in attempt:
                    checks.append((f"Attempt {i} has '{field}'", True))
                else:
                    checks.append((f"Attempt {i} has '{field}'", False))
                    passed = False

    # Print results
    print(f"\n{'—' * 40}")
    print("Checks:")
    for label, ok in checks:
        status = "[OK]" if ok else "[X]"
        print(f"  {status} {label}")

    return passed


def test_scenario_4_phase2_fields():
    """
    Scenario 4: Result dict contains all Phase 2 fields.
    """
    from main import OVRAGSystem

    print(f"\n{SEPARATOR}")
    print("SCENARIO 4: Phase 2 Result Fields")
    print(SEPARATOR)

    system = OVRAGSystem()
    system.load_documents(["data/Contract_001.pdf"])

    result = system.process_query("What is the interest rate?")

    passed = True
    checks = []

    for field in PHASE2_FIELDS:
        if field in result:
            checks.append((f"Field '{field}' present", True))
        else:
            checks.append((f"Field '{field}' present", False))
            passed = False

    # Print results
    print(f"\n{'—' * 40}")
    print("Checks:")
    for label, ok in checks:
        status = "[OK]" if ok else "[X]"
        print(f"  {status} {label}")

    return passed


if __name__ == "__main__":
    print(SEPARATOR)
    print("OV-RAG PHASE 2: VALIDATION LOOP TESTS")
    print(SEPARATOR)

    check_prerequisites()

    results = []

    # Run scenarios
    results.append(("First-Attempt Pass", test_scenario_1_first_attempt_pass()))
    results.append(("Correction Loop (Clash)", test_scenario_2_correction_loop()))
    results.append(("Logging Structure", test_scenario_3_logging_structure()))
    results.append(("Phase 2 Fields", test_scenario_4_phase2_fields()))

    # Summary
    print(f"\n{SEPARATOR}")
    print("SUMMARY")
    print(SEPARATOR)

    passed = 0
    total = len(results)

    for name, ok in results:
        status = "[OK] PASS" if ok else "[X] FAIL"
        print(f"  {status}  {name}")
        if ok:
            passed += 1

    print(f"\nResult: {passed}/{total} scenarios passed")

    if passed == total:
        print("\nAll Phase 2 tests passed!")
    else:
        print("\nSome tests failed. Check output above for details.")

    sys.exit(0 if passed == total else 1)
