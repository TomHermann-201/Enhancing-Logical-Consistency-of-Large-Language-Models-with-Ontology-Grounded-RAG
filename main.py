"""
main.py
CLI Entry Point - Ontology-Validated RAG System

Integrates all three components:
- Component A: RAG Pipeline (Generator)
- Component B: Triple Extractor
- Component C: Ontology Validator

Demonstrates the "Vertical Slice" prototype that detects and corrects
logical hallucinations in RAG-generated financial text.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

from rag_pipeline import RAGPipeline
from extractor import TripleExtractor
from validator import OntologyValidator

# Maximum number of correction attempts before hard-reject
MAX_CORRECTION_ATTEMPTS = 3


class OVRAGSystem:
    """
    Ontology-Validated RAG (OV-RAG) System.

    The complete vertical slice that demonstrates how a formal ontology
    can detect logical inconsistencies in LLM-generated financial text.
    """

    def __init__(
        self,
        ontology_dir: str = "ontologies",
        api_key: Optional[str] = None
    ):
        """
        Initialize the OV-RAG system.

        Args:
            ontology_dir: Directory containing FIBO ontology files
            api_key: OpenAI API key (optional)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
            )

        print("="*70)
        print("ONTOLOGY-VALIDATED RAG SYSTEM")
        print("="*70)
        print("Initializing components...")
        print()

        # Initialize all three components
        self.rag = RAGPipeline(api_key=self.api_key)
        self.extractor = TripleExtractor(api_key=self.api_key)
        self.validator = OntologyValidator(ontology_dir=ontology_dir)

        print()
        print("[OK] System ready")
        print("="*70)

    def load_documents(self, pdf_paths: List[str]) -> int:
        """
        Load PDF documents into the RAG pipeline.

        Args:
            pdf_paths: List of PDF file paths

        Returns:
            Number of chunks created
        """
        return self.rag.load_documents(pdf_paths)

    def process_query(self, question: str, validate: bool = True) -> dict:
        """
        Process a query through the complete OV-RAG pipeline with correction loop.

        Flow:
        1. Generate answer with RAG
        2. Extract triples
        3. Validate against ontology
        4. If invalid: re-prompt with feedback (up to MAX_CORRECTION_ATTEMPTS)
        5. If still invalid after max attempts: Hard-Reject

        Args:
            question: User question
            validate: Whether to run ontology validation

        Returns:
            Dict with answer, triples, validation results, and correction info
        """
        print("\n" + "="*70)
        print("QUERY PROCESSING")
        print("="*70)
        print(f"Question: {question}")
        print()

        # Step 1: Generate initial answer using RAG
        print("[1/3] Generating answer with RAG...")
        rag_result = self.rag.query(question)
        answer = rag_result["answer"]
        source_documents = rag_result["source_documents"]

        result = {
            "question": question,
            "answer": answer,
            "sources": source_documents,
            "triples": [],
            "validation": None,
            "correction_attempts": [],
            "hard_reject": False,
            "hard_reject_reason": None,
            "total_attempts": 1,
            "accepted_at_attempt": None,
        }

        if not validate:
            return result

        # === Extract-Validate Loop ===
        # Attempt 0 = initial answer, attempts 1..MAX = corrections
        current_answer = answer

        for attempt in range(MAX_CORRECTION_ATTEMPTS + 1):
            attempt_label = "initial" if attempt == 0 else f"correction {attempt}"
            print("\n" + "="*70)
            print(f"[2/3] Extracting triples ({attempt_label})...")
            extraction_result = self.extractor.extract_triples(current_answer)

            if not extraction_result.success:
                print(f"[X] Extraction failed: {extraction_result.error}")
                result["answer"] = current_answer
                result["total_attempts"] = attempt + 1
                return result

            triples = extraction_result.triples

            if not triples:
                print("[i] No triples extracted - skipping validation")
                result["answer"] = current_answer
                result["triples"] = triples
                result["total_attempts"] = attempt + 1
                return result

            # Validate against LOAN ontology
            print("\n" + "="*70)
            print(f"[3/3] Validating against LOAN ontology ({attempt_label})...")
            validation_result = self.validator.validate_text_answer(
                current_answer,
                triples
            )

            # Log this attempt
            attempt_log = {
                "attempt_number": attempt,
                "answer": current_answer,
                "triples": triples,
                "is_valid": validation_result.is_valid,
                "explanation": validation_result.explanation,
            }
            result["correction_attempts"].append(attempt_log)

            if validation_result.is_valid:
                # Accepted
                result["answer"] = current_answer
                result["triples"] = triples
                result["validation"] = validation_result
                result["total_attempts"] = attempt + 1
                result["accepted_at_attempt"] = attempt
                self._print_summary(result)
                return result

            # Validation failed
            if attempt < MAX_CORRECTION_ATTEMPTS:
                # Still have correction attempts left
                print(f"\n[!] Validation failed ({attempt_label}). "
                      f"Requesting correction ({attempt + 1}/{MAX_CORRECTION_ATTEMPTS})...")
                correction_result = self.rag.query_with_correction(
                    question=question,
                    previous_answer=current_answer,
                    validation_feedback=validation_result.explanation,
                    attempt_number=attempt + 1,
                    source_documents=source_documents,
                )
                current_answer = correction_result["answer"]
            else:
                # All correction attempts exhausted → Hard-Reject
                result["answer"] = current_answer
                result["triples"] = triples
                result["validation"] = validation_result
                result["total_attempts"] = attempt + 1
                result["hard_reject"] = True
                result["hard_reject_reason"] = (
                    f"Answer failed ontology validation after {MAX_CORRECTION_ATTEMPTS} "
                    f"correction attempt(s). Last failure: {validation_result.explanation}"
                )
                self._print_summary(result)
                return result

        return result

    def _print_summary(self, result: dict):
        """Print a summary of the processing results."""
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        print(f"Question: {result['question']}")
        print()
        print(f"Answer: {result['answer']}")
        print()
        print(f"Triples Extracted: {len(result['triples'])}")
        print(f"Total Attempts: {result['total_attempts']}")

        # Correction loop info
        if result['correction_attempts']:
            print()
            print("Correction Loop:")
            for attempt in result['correction_attempts']:
                attempt_num = attempt['attempt_number']
                label = "Initial" if attempt_num == 0 else f"Correction {attempt_num}"
                status = "PASS" if attempt['is_valid'] else "FAIL"
                print(f"  Attempt {attempt_num} ({label}): {status}")

        if result['validation']:
            print()
            if result['hard_reject']:
                print("[X] HARD-REJECT")
                print(f"  {result['hard_reject_reason']}")
            elif result['validation'].is_valid:
                accepted = result.get('accepted_at_attempt', 0)
                if accepted == 0:
                    print("[OK] VALIDATION: PASSED (first attempt)")
                else:
                    print(f"[OK] VALIDATION: PASSED (after {accepted} correction(s))")
                print("  The answer is logically consistent with LOAN ontology")
            else:
                print("[X] VALIDATION: FAILED")
                print("  Logical inconsistency detected!")
                print()
                print(result['validation'].explanation)

        print("="*70)

    def interactive_mode(self):
        """Run the system in interactive CLI mode."""
        print("\n" + "="*70)
        print("INTERACTIVE MODE")
        print("="*70)
        print("Enter queries to test the OV-RAG system.")
        print("Commands:")
        print("  'quit' or 'exit' - Exit the program")
        print("  'info' - Show system information")
        print("="*70)

        while True:
            print()
            try:
                question = input("Query> ").strip()

                if not question:
                    continue

                if question.lower() in ["quit", "exit", "q"]:
                    print("Goodbye!")
                    break

                if question.lower() == "info":
                    self._print_info()
                    continue

                # Process the query
                self.process_query(question)

            except KeyboardInterrupt:
                print("\n\nInterrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n[X] Error: {type(e).__name__}: {str(e)}")

    def _print_info(self):
        """Print system information."""
        print()
        print("System Information:")
        print(f"  RAG Model: {self.rag.model}")
        print(f"  Temperature: {self.rag.temperature}")
        print(f"  Top-k: {self.rag.top_k}")
        print(f"  Extractor Model: {self.extractor.model}")
        print(f"  Ontology Directory: {self.validator.ontology_dir}")


def main():
    """Main CLI entry point."""
    # Load environment variables
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Ontology-Validated RAG for Financial Compliance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode with default data directory
  python main.py

  # Process specific PDF files
  python main.py --docs data/report1.pdf data/report2.pdf

  # Single query mode
  python main.py --query "Who owns ACME Corporation?"

  # Skip validation (RAG only)
  python main.py --no-validate
        """
    )

    parser.add_argument(
        "--docs",
        nargs="+",
        help="PDF documents to load (default: all PDFs in ./data)"
    )

    parser.add_argument(
        "--query",
        type=str,
        help="Single query to process (skip interactive mode)"
    )

    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip ontology validation (RAG only)"
    )

    parser.add_argument(
        "--ontology-dir",
        default="ontologies",
        help="Directory containing LOAN ontology files (default: ./ontologies)"
    )

    args = parser.parse_args()

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("[X] Error: OPENAI_API_KEY not set")
        print()
        print("Set your OpenAI API key:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print()
        print("Or create a .env file:")
        print("  OPENAI_API_KEY=your-key-here")
        sys.exit(1)

    # Check for ontology files (if validation enabled)
    if not args.no_validate:
        ontology_path = Path(args.ontology_dir)
        # Check for LOAN ontology files in subdirectories
        if not ontology_path.exists() or not any(ontology_path.glob("**/*.rdf")):
            print("[X] Error: LOAN ontology files not found")
            print()
            print("Ensure your LOAN ontology files are in the ontologies directory")
            print("Expected structure: ontologies/loans general module/*.rdf")
            sys.exit(1)

    # Determine which documents to load
    if args.docs:
        pdf_paths = args.docs
    else:
        data_dir = Path("data")
        pdf_files = list(data_dir.glob("*.pdf"))

        if not pdf_files:
            print("[X] Error: No PDF files found in ./data directory")
            print()
            print("Add financial PDF documents to the ./data directory")
            print("Or specify documents with: --docs path/to/file.pdf")
            sys.exit(1)

        pdf_paths = [str(f) for f in pdf_files]

    try:
        # Initialize system
        system = OVRAGSystem(ontology_dir=args.ontology_dir)

        # Load documents
        print()
        num_chunks = system.load_documents(pdf_paths)

        if num_chunks == 0:
            print("[X] No documents loaded")
            sys.exit(1)

        # Single query mode
        if args.query:
            system.process_query(args.query, validate=not args.no_validate)
            return

        # Interactive mode
        system.interactive_mode()

    except KeyboardInterrupt:
        print("\n\nInterrupted. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n[X] Fatal Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
