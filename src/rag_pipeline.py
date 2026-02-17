"""
rag_pipeline.py
Component A: The Generator - Standard RAG Pipeline

A simplified RAG (Retrieval Augmented Generation) pipeline using LangChain.
This is the baseline system that generates answers which will be validated
against the FIBO ontology.

Pipeline:
1. Chunk text from PDF documents
2. Embed & Store in ChromaDB
3. Retrieve (Top-k=3)
4. Generate Answer (Temperature=0.7 to encourage hallucinations for testing)
"""

import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate


# RAG Prompt Template
RAG_PROMPT_TEMPLATE = """You are a financial analyst assistant. Use the following context to answer the question.

Context:
{context}

Question: {question}

Instructions:
- Provide a clear, concise answer based on the context
- If the answer is not in the context, say "I don't have enough information to answer this question."
- Focus on factual information about entities, relationships, and ownership structures
- Be specific about company names, ownership percentages, and corporate relationships

Answer:"""


# Correction Prompt Template - used when ontology validation fails
CORRECTION_PROMPT_TEMPLATE = """You are a financial analyst assistant. Your previous answer was rejected because it contained logical inconsistencies with respect to a formal loan ontology.

Context (from the original documents):
{context}

Question: {question}

Your previous answer (REJECTED - attempt {attempt_number}):
{previous_answer}

Ontology validation feedback:
{validation_feedback}

Instructions:
- Rewrite your answer so that it is logically consistent with the LOAN ontology
- Fix the specific inconsistencies described in the validation feedback
- Do NOT introduce new facts that are not supported by the context
- Keep the answer factual, concise, and based on the context provided
- If the context genuinely contains contradictory information, state that clearly rather than guessing

Corrected answer:"""


class RAGPipeline:
    """
    Simple RAG pipeline for financial document Q&A.

    This is the baseline generator that produces answers which may
    contain logical inconsistencies (hallucinations) that the
    ontology validator will detect.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        embedding_model: str = "text-embedding-3-small",
        temperature: float = 0.7,  # Higher temp to encourage hallucinations
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        top_k: int = 3
    ):
        """
        Initialize the RAG pipeline.

        Args:
            api_key: OpenAI API key (or None to use env variable)
            model: LLM model for generation
            embedding_model: Model for embeddings
            temperature: Generation temperature (0.7 for testing hallucinations)
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            top_k: Number of chunks to retrieve
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model
        self.temperature = temperature
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k

        # Initialize components
        # API key will be read from environment (OPENAI_API_KEY)
        self.embeddings = OpenAIEmbeddings(
            model=embedding_model
        )

        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature
        )

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )

        self.vectorstore = None
        self.retriever = None

        print(f"[OK] RAG Pipeline initialized")
        print(f"  Model: {model}")
        print(f"  Temperature: {temperature} (encourages creative/hallucinated responses)")
        print(f"  Top-k: {top_k}")

    def load_documents(self, pdf_paths: List[str]) -> int:
        """
        Load and process PDF documents into the vector store.

        Args:
            pdf_paths: List of paths to PDF files

        Returns:
            Number of chunks created
        """
        print(f"\nLoading {len(pdf_paths)} document(s)...")

        all_chunks = []

        for pdf_path in pdf_paths:
            path = Path(pdf_path)
            if not path.exists():
                print(f"[X] File not found: {pdf_path}")
                continue

            print(f"  Processing: {path.name}")

            try:
                # Load PDF
                loader = PyPDFLoader(str(path))
                documents = loader.load()

                # Split into chunks
                chunks = self.text_splitter.split_documents(documents)
                all_chunks.extend(chunks)

                print(f"    [OK] Created {len(chunks)} chunk(s)")

            except Exception as e:
                print(f"    [X] Error loading {path.name}: {e}")

        if not all_chunks:
            print("[X] No documents loaded")
            return 0

        # Create vector store
        print(f"\nCreating vector store with {len(all_chunks)} chunk(s)...")
        self.vectorstore = Chroma.from_documents(
            documents=all_chunks,
            embedding=self.embeddings,
            collection_name="financial_docs"
        )

        # Create retriever
        self.retriever = self.vectorstore.as_retriever(search_kwargs={"k": self.top_k})

        print(f"[OK] Vector store ready with {len(all_chunks)} chunk(s)")
        return len(all_chunks)

    def query(self, question: str) -> dict:
        """
        Query the RAG pipeline.

        Args:
            question: User question

        Returns:
            Dict with 'answer' and 'source_documents'
        """
        if not self.retriever:
            raise RuntimeError("No documents loaded. Call load_documents() first.")

        print(f"\nQuery: {question}")
        print("Retrieving relevant context...")

        # Retrieve relevant documents
        sources = self.retriever.invoke(question)

        print(f"\nRetrieved {len(sources)} chunk(s)")

        # Format context from retrieved documents
        context = "\n\n".join([doc.page_content for doc in sources])

        # Create prompt with context
        prompt_text = RAG_PROMPT_TEMPLATE.format(context=context, question=question)

        # Generate answer
        answer = self.llm.invoke(prompt_text).content

        print(f"\nAnswer:\n{answer}")

        return {
            "answer": answer,
            "source_documents": sources,
            "question": question
        }

    def query_with_correction(
        self,
        question: str,
        previous_answer: str,
        validation_feedback: str,
        attempt_number: int,
        source_documents: list
    ) -> dict:
        """
        Re-generate an answer incorporating ontology validation feedback.

        Reuses the same source documents from the original query to avoid
        retrieval drift across correction attempts.

        Args:
            question: Original user question
            previous_answer: The rejected answer
            validation_feedback: Explanation from the ontology validator
            attempt_number: Current correction attempt (1-based)
            source_documents: Source docs from the original retrieval

        Returns:
            Dict with 'answer' and 'source_documents'
        """
        print(f"\nCorrection attempt {attempt_number}...")

        # Reuse the same context from original retrieval
        context = "\n\n".join([doc.page_content for doc in source_documents])

        prompt_text = CORRECTION_PROMPT_TEMPLATE.format(
            context=context,
            question=question,
            previous_answer=previous_answer,
            validation_feedback=validation_feedback,
            attempt_number=attempt_number
        )

        answer = self.llm.invoke(prompt_text).content

        print(f"\nCorrected Answer:\n{answer}")

        return {
            "answer": answer,
            "source_documents": source_documents,
            "question": question
        }

    def get_answer_only(self, question: str) -> str:
        """
        Convenience method to get just the answer text.

        Args:
            question: User question

        Returns:
            Answer string
        """
        result = self.query(question)
        return result["answer"]


# Convenience function for quick usage
def create_rag_pipeline(
    pdf_paths: List[str],
    api_key: Optional[str] = None
) -> RAGPipeline:
    """
    Convenience function to create and initialize a RAG pipeline.

    Args:
        pdf_paths: List of PDF file paths to load
        api_key: Optional OpenAI API key

    Returns:
        Initialized RAGPipeline
    """
    pipeline = RAGPipeline(api_key=api_key)
    pipeline.load_documents(pdf_paths)
    return pipeline


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    # Test the RAG pipeline
    print("Testing RAG Pipeline...")
    print()

    # Check if API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY not set. Set it to run the test:")
        print("  export OPENAI_API_KEY='your-key-here'")
        exit(1)

    # Check for test documents
    data_dir = Path("data")
    pdf_files = list(data_dir.glob("*.pdf"))

    if not pdf_files:
        print("WARNING: No PDF files found in ./data directory")
        print("  Add some financial PDF documents to test the pipeline")
        print()
        print("Creating a sample text file for basic testing...")

        # Create a sample text document
        sample_text = """
        ACME Corporation Financial Report

        Corporate Structure:
        ACME Corporation is a publicly traded company headquartered in New York.
        The company has several wholly owned subsidiaries:

        1. TechStart Inc. - Acquired in 2023, now a wholly owned subsidiary
        2. Global Industries - Subsidiary since 2020
        3. Innovation Labs - Research and development arm

        Ownership:
        - ACME Corporation is wholly owned by its shareholders
        - John Smith is the CEO and major shareholder (15% stake)
        - Institutional investors hold 60% of shares

        Recent Transactions:
        In Q4 2023, ACME Corporation acquired TechStart Inc. for $50M.
        The acquisition made TechStart a wholly owned subsidiary.
        """

        sample_file = data_dir / "sample_financial_report.txt"
        data_dir.mkdir(exist_ok=True)
        sample_file.write_text(sample_text)
        print(f"  Created: {sample_file}")
        print()
        print("Note: This is a text file. For full testing, add PDF documents.")
        exit(0)

    print(f"Found {len(pdf_files)} PDF file(s) in ./data")
    print()

    # Initialize pipeline
    pipeline = RAGPipeline()
    pipeline.load_documents([str(f) for f in pdf_files])

    # Test queries
    test_queries = [
        "What companies are mentioned in the document?",
        "Who owns TechStart Inc.?",
        "What is the relationship between ACME Corporation and TechStart Inc.?"
    ]

    print("\n" + "="*70)
    print("Testing Queries")
    print("="*70)

    for query in test_queries:
        print("\n" + "-"*70)
        result = pipeline.query(query)
        print("-"*70)
