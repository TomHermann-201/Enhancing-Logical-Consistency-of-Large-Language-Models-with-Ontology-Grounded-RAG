"""
Test extractor with loan type statements
"""
import os
from dotenv import load_dotenv
from extractor import TripleExtractor

load_dotenv()

# Test text similar to what RAG generated
test_text = "The loan type in the document is a Subsidized Student Loan for education purposes."

print("Testing Triple Extractor with Loan Type Statement")
print("="*70)
print(f"Text: {test_text}")
print()

extractor = TripleExtractor()
result = extractor.extract_triples(test_text)

print()
print("="*70)
print("RESULT:")
print(f"Success: {result.success}")
print(f"Number of triples: {len(result.triples)}")
print(f"Triples: {result.triples}")
