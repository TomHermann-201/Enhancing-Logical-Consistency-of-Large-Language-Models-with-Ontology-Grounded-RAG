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
        Process a query through the complete OV-RAG pipeline.

        Args:
            question: User question
            validate: Whether to run ontology validation

        Returns:
            Dict with answer, triples, and validation results
        """
        print("\n" + "="*70)
        print("QUERY PROCESSING")
        print("="*70)
        print(f"Question: {question}")
        print()

        # Step 1: Generate answer using RAG
        print("[1/3] Generating answer with RAG...")
        rag_result = self.rag.query(question)
        answer = rag_result["answer"]

        result = {
            "question": question,
            "answer": answer,
            "sources": rag_result["source_documents"],
            "triples": [],
            "validation": None
        }

        if not validate:
            return result

        # Step 2: Extract triples from the answer
        print("\n" + "="*70)
        print("[2/3] Extracting triples...")
        extraction_result = self.extractor.extract_triples(answer)

        if not extraction_result.success:
            print(f"[X] Extraction failed: {extraction_result.error}")
            return result

        result["triples"] = extraction_result.triples

        if not extraction_result.triples:
            print("[i] No triples extracted - skipping validation")
            return result

        # Step 3: Validate triples against LOAN ontology
        print("\n" + "="*70)
        print("[3/3] Validating against LOAN ontology...")
        validation_result = self.validator.validate_text_answer(
            answer,
            extraction_result.triples
        )

        result["validation"] = validation_result

        # Print summary
        self._print_summary(result)

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

        if result['validation']:
            print()
            if result['validation'].is_valid:
                print("[OK] VALIDATION: PASSED")
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
        if not ontology_path.exists() or not any(ontology_path.glob("*.rdf")):
            print("[X] Error: FIBO ontology files not found")
            print()
            print("Run the setup script first:")
            print("  python setup_ontologies.py")
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
