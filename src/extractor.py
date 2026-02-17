"""
extractor.py
The Triple Extractor - Bridges text and ontology.

Uses an LLM with a specialized system prompt to extract entities and relations
from natural language text and map them strictly to LOAN ontology classes.

Output: JSON List of Triples (Subject, Predicate, Object) with LOAN ontology types.

FEATURE: Dynamisches Prompt-Loading aus vocabulary_cache.json
- Wenn vocabulary_cache.json existiert, wird der dynamisch generierte Prompt geladen
- Andernfalls wird der statische Fallback-Prompt verwendet
"""

import os
import json
from typing import List, Dict, Optional
from dataclasses import dataclass

from openai import OpenAI


# Versuche dynamischen Prompt aus Cache zu laden
def _load_dynamic_prompt() -> Optional[str]:
    """Lädt den dynamisch generierten Prompt aus dem Vokabular-Cache."""
    cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'vocabulary_cache.json')
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            prompt = data.get('generated_prompt')
            if prompt:
                print(f"[OK] Dynamischer Prompt geladen aus {cache_path}")
                return prompt
        except Exception as e:
            print(f"[!] Fehler beim Laden des Caches: {e}")
    return None


# LOAN ontology extraction prompt (FALLBACK - statisch)
STATIC_EXTRACTION_PROMPT = """You are a Semantic Translator for financial loan documents. Extract facts from the text and map them to these LOAN ontology concepts:

Classes:
- Loan (general loan concept)
- ConsumerLoan (loans to individual consumers)
- CommercialLoan (loans to businesses/corporations)
- Mortgage (real estate loans)
- StudentLoan (education financing)
- SubsidizedStudentLoan (government-subsidized education loans)
- GreenLoan (sustainable/environmental financing)
- Lender (financial institution providing the loan)
- Borrower (entity receiving the loan)
- Corporation (business entity)
- FinancialInstitution (banks, lending organizations)

Properties:
- rdf:type (entity is of a certain type/class)
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
1. Extract factual assertions including TYPE CLASSIFICATIONS (e.g., "X is a StudentLoan")
2. For unnamed entities (like "the loan", "the document"), use descriptive subjects like "TheLoan" or "DocumentLoan"
3. IMPORTANT: Type assertions like "the loan is a StudentLoan" should extract as:
   - sub: "TheLoan", pred: "rdf:type", obj: "StudentLoan", sub_type: "Loan", obj_type: "Class"
4. Map entities to the MOST SPECIFIC loan class that applies (e.g., SubsidizedStudentLoan > StudentLoan > Loan)
5. Include relationships between lenders, borrowers, and loans
6. Include loan characteristics (amount, rate, type, etc.) when mentioned
7. Each triple must have: sub, pred, obj, sub_type, obj_type

Examples:
- "The loan is a Subsidized Student Loan" → {"sub": "TheLoan", "pred": "rdf:type", "obj": "SubsidizedStudentLoan", "sub_type": "Loan", "obj_type": "Class"}
- "ACME Corp borrowed from Bank XYZ" → {"sub": "ACME Corp", "pred": "receivesLoan", "obj": "Bank XYZ", "sub_type": "Borrower", "obj_type": "Lender"}

Return JSON in this exact format:
{"triples": [{"sub": "...", "pred": "...", "obj": "...", "sub_type": "...", "obj_type": "..."}]}

If no triples can be extracted, return: {"triples": []}
"""

# Context extraction prompt: extracts ALL facts from source documents,
# preserving contradictions so the validator can detect clashes.
CONTEXT_EXTRACTION_PROMPT = """You are a Semantic Extractor for financial loan documents. Your task is to extract ALL factual assertions from the source text and map them to LOAN ontology concepts.

CRITICAL: Extract EVERY classification and assertion you find, even if they contradict each other. Do NOT resolve contradictions — preserve them all.

Classes:
- Loan, SecuredLoan, UnsecuredLoan
- ConsumerLoan, CommercialLoan
- Mortgage, StudentLoan, SubsidizedStudentLoan, GreenLoan
- OpenEndCredit, ClosedEndCredit
- Lender, Borrower
- Corporation, FinancialInstitution, NaturalPerson

Keyword mapping (apply ALL that match):
- "secured", "collateral", "pledge", "backed by" → SecuredLoan
- "unsecured", "no collateral", "without collateral" → UnsecuredLoan
- "open-end", "revolving", "line of credit" → OpenEndCredit
- "closed-end", "fixed term", "installment" → ClosedEndCredit
- "consumer", "personal", "individual", "household" → ConsumerLoan
- "commercial", "business", "corporate", "enterprise" → CommercialLoan
- "mortgage", "real estate", "home loan" → Mortgage
- "student loan", "education loan" → StudentLoan
- "green loan", "sustainable", "environmental" → GreenLoan

Properties:
- rdf:type (entity classification)
- hasLender, hasBorrower, hasLoanAmount, hasInterestRate
- hasMaturityDate, hasGuarantor, hasCollateral

Rules:
1. Use "TheLoan" as subject for all loan-related assertions (to match answer extraction)
2. Extract type assertions as: {"sub": "TheLoan", "pred": "rdf:type", "obj": "<ClassName>", "sub_type": "Loan", "obj_type": "Class"}
3. Extract ALL applicable types — if the text says both "secured" and "unsecured", extract BOTH
4. For borrower/lender entities, use their names or "TheBorrower"/"TheLender"
5. Each triple must have: sub, pred, obj, sub_type, obj_type

Return JSON: {"triples": [{"sub": "...", "pred": "...", "obj": "...", "sub_type": "...", "obj_type": "..."}]}
If no triples can be extracted, return: {"triples": []}
"""

# Lade dynamischen Prompt oder verwende statischen Fallback
_DYNAMIC_PROMPT = _load_dynamic_prompt()
EXTRACTION_SYSTEM_PROMPT = _DYNAMIC_PROMPT if _DYNAMIC_PROMPT else STATIC_EXTRACTION_PROMPT


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

        # Zeige an, welcher Prompt verwendet wird
        prompt_type = "dynamisch (vocabulary_cache.json)" if _DYNAMIC_PROMPT else "statisch (Fallback)"
        print(f"[OK] Triple Extractor initialized (model: {model}, prompt: {prompt_type})")

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

    def extract_from_context(self, context_text: str) -> ExtractionResult:
        """
        Extract triples from source document context, preserving contradictions.

        Uses a specialized prompt that captures ALL factual assertions from
        the source text, even contradictory ones, so the validator can detect
        clashes between source documents and LLM answers.

        Args:
            context_text: Concatenated text from source documents

        Returns:
            ExtractionResult with context triples
        """
        print(f"\nExtracting context triples from source documents...")
        print(f"Context: {context_text[:100]}..." if len(context_text) > 100 else f"Context: {context_text}")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CONTEXT_EXTRACTION_PROMPT},
                    {"role": "user", "content": context_text}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )

            raw_response = response.choices[0].message.content
            print(f"\nRaw context extraction response:\n{raw_response}")

            parsed = json.loads(raw_response)
            triples = parsed.get("triples", [])

            validated_triples = []
            for triple in triples:
                if self._validate_triple_structure(triple):
                    validated_triples.append(triple)
                else:
                    print(f"Warning: Invalid context triple structure: {triple}")

            result = ExtractionResult(
                triples=validated_triples,
                raw_response=raw_response,
                success=True
            )

            print(f"\n[Context] {result}")
            if validated_triples:
                print("\nContext triples:")
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
                error=f"Context extraction error: {type(e).__name__}: {str(e)}"
            )


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

    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Check if API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not set. Set it to run the test:")
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
