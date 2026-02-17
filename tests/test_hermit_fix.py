"""
Test HermiT fixes with loan type validation
"""
import os
import sys

_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(_root, 'src'))
sys.path.insert(0, _root)

from dotenv import load_dotenv
from extractor import TripleExtractor
from validator import OntologyValidator

load_dotenv()

print("="*70)
print("TESTING HERMIT REASONER FIXES")
print("="*70)
print()

# Test text
test_text = "The loan type in the document is a Subsidized Student Loan for education purposes."

print("Step 1: Extract triples")
print("-"*70)
extractor = TripleExtractor()
result = extractor.extract_triples(test_text)

if not result.success:
    print(f"[X] Extraction failed: {result.error}")
    exit(1)

print(f"\n[OK] Extracted {len(result.triples)} triple(s)")
print()

# Test validation
print("Step 2: Initialize validator and load LOAN ontology")
print("-"*70)
validator = OntologyValidator(ontology_dir="ontologies")
print()

print("Step 3: Validate extracted triples")
print("-"*70)
validation_result = validator.validate_triples(result.triples)
print()

print("="*70)
print("FINAL RESULT")
print("="*70)
print(f"Validation Status: {'PASSED' if validation_result.is_valid else 'FAILED'}")
print(f"Explanation:\n{validation_result.explanation}")
print("="*70)
