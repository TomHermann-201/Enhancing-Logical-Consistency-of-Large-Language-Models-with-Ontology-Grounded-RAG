"""
extractor.py
The Triple Extractor - Bridges text and ontology.

Uses an LLM with a specialized system prompt to extract entities and relations
from natural language text and map them strictly to LOAN ontology classes.

Output: JSON List of Triples (Subject, Predicate, Object) with LOAN ontology types.
"""

import os
import json
from typing import List, Dict, Optional
from dataclasses import dataclass

from openai import OpenAI


# LOAN ontology extraction prompt
EXTRACTION_SYSTEM_PROMPT = """You are a Semantic Translator for financial loan documents. Extract facts from the text and map them to these LOAN ontology concepts:

Classes:
- Loan (general loan concept)
- ConsumerLoan (loans to individual consumers)
- CommercialLoan (loans to businesses/corporations)
- Mortgage (real estate loans)
- StudentLoan (education financing)
- GreenLoan (sustainable/environmental financing)
- Lender (financial institution providing the loan)
- Borrower (entity receiving the loan)
- Corporation (business entity)
- FinancialInstitution (banks, lending organizations)

Properties:
- hasLender (loan has a lender)
- hasBorrower (loan has a borrower)
- hasLoanAmount (loan has an amount)
- hasInterestRate (loan has interest rate)
- hasMaturityDate (loan has end date)
- hasGuarantor (loan has guarantor)
- hasCollateral (loan secured by collateral)
- providesLoan (lender provides loan)
- receivesLoan (borrower receives loan)

Guidelines:
1. Extract only factual assertions that are explicitly stated in the text
2. Map entities to the MOST SPECIFIC loan class that applies
3. Focus on relationships between lenders, borrowers, and loans
4. Include loan characteristics (amount, rate, type, etc.) when mentioned
5. Each triple must have: sub, pred, obj, sub_type, obj_type

Return JSON in this exact format:
{"triples": [{"sub": "...", "pred": "...", "obj": "...", "sub_type": "...", "obj_type": "..."}]}

If no triples can be extracted, return: {"triples": []}
"""


@dataclass
class ExtractionResult:
    """Result of triple extraction."""
    triples: List[Dict]
    raw_response: str
    success: bool
    error: Optional[str] = None

    def __str__(self) -> str:
        if not self.success:
            return f"[X] Extraction failed: {self.error}"
        return f"[OK] Extracted {len(self.triples)} triple(s)"


class TripleExtractor:
    """
    Extracts structured triples from natural language using an LLM.

    This component acts as a semantic translator, converting free-text
    loan/financial statements into LOAN ontology-compliant RDF triples.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize the triple extractor.

        Args:
            api_key: OpenAI API key (or None to use env variable)
            model: OpenAI model to use for extraction
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model
        self.client = OpenAI(api_key=self.api_key)

        print(f"[OK] Triple Extractor initialized (model: {model})")

    def extract_triples(self, text: str) -> ExtractionResult:
        """
        Extract LOAN ontology-compliant triples from text.

        Args:
            text: Natural language text to extract from

        Returns:
            ExtractionResult with extracted triples
        """
        print(f"\nExtracting triples from text...")
        print(f"Text: {text[:100]}..." if len(text) > 100 else f"Text: {text}")

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                temperature=0.0,  # Deterministic extraction
                response_format={"type": "json_object"}  # Force JSON output
            )

            raw_response = response.choices[0].message.content
            print(f"\nRaw extraction response:\n{raw_response}")

            # Parse JSON response
            parsed = json.loads(raw_response)
            triples = parsed.get("triples", [])

            # Validate triple structure
            validated_triples = []
            for triple in triples:
                if self._validate_triple_structure(triple):
                    validated_triples.append(triple)
                else:
                    print(f"Warning: Invalid triple structure: {triple}")

            result = ExtractionResult(
                triples=validated_triples,
                raw_response=raw_response,
                success=True
            )

            print(f"\n{result}")
            if validated_triples:
                print("\nExtracted triples:")
                for i, triple in enumerate(validated_triples, 1):
                    print(f"  {i}. {triple['sub']} ({triple['sub_type']}) "
                          f"{triple['pred']} "
                          f"{triple['obj']} ({triple['obj_type']})")

            return result

        except json.JSONDecodeError as e:
            return ExtractionResult(
                triples=[],
                raw_response="",
                success=False,
                error=f"JSON parsing error: {e}"
            )

        except Exception as e:
            return ExtractionResult(
                triples=[],
                raw_response="",
                success=False,
                error=f"Extraction error: {type(e).__name__}: {str(e)}"
            )

    def _validate_triple_structure(self, triple: Dict) -> bool:
        """
        Validate that a triple has the required fields.

        Args:
            triple: Dictionary representing a triple

        Returns:
            bool: True if valid structure
        """
        required_fields = ["sub", "pred", "obj", "sub_type", "obj_type"]

        for field in required_fields:
            if field not in triple:
                return False
            if not isinstance(triple[field], str) or not triple[field].strip():
                return False

        return True

    def extract_from_answer(
        self, answer: str, context: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract triples from an LLM-generated answer.

        Args:
            answer: The answer text to extract from
            context: Optional context (e.g., the original query)

        Returns:
            ExtractionResult
        """
        # If context provided, include it in the extraction prompt
        if context:
            extraction_text = f"Context: {context}\n\nAnswer: {answer}"
        else:
            extraction_text = answer

        return self.extract_triples(extraction_text)


# Convenience function for quick extraction
def extract_triples_from_text(
    text: str,
    api_key: Optional[str] = None,
    model: str = "gpt-4o"
) -> List[Dict]:
    """
    Convenience function to extract triples from text.

    Args:
        text: Text to extract from
        api_key: OpenAI API key (optional)
        model: Model to use

    Returns:
        List of triple dictionaries
    """
    extractor = TripleExtractor(api_key=api_key, model=model)
    result = extractor.extract_triples(text)

    if result.success:
        return result.triples
    else:
        print(f"Extraction failed: {result.error}")
        return []


if __name__ == "__main__":
    # Test the extractor with sample text
    print("Testing Triple Extractor...")
    print()

    # Example 1: Valid financial statement
    test_text_1 = """
    ACME Corporation acquired TechStart Inc. in 2023.
    TechStart Inc. is a wholly owned subsidiary of ACME Corporation.
    """

    # Example 2: Potentially problematic statement (Natural person as company)
    test_text_2 = """
    John Doe is the parent company of Global Industries.
    Global Industries is wholly owned by John Doe.
    """

    # Check if API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠ OPENAI_API_KEY not set. Set it to run the test:")
        print("  export OPENAI_API_KEY='your-key-here'")
        exit(1)

    extractor = TripleExtractor()

    print("\n" + "="*70)
    print("Test 1: Valid Financial Statement")
    print("="*70)
    result1 = extractor.extract_triples(test_text_1)

    print("\n" + "="*70)
    print("Test 2: Potentially Problematic Statement")
    print("="*70)
    result2 = extractor.extract_triples(test_text_2)

    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    print(f"Test 1: {result1}")
    print(f"Test 2: {result2}")
