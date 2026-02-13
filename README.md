# Enhancing Logical Consistency of Large Language Models with Ontology-Grounded RAG

A Bachelor Thesis project in Business Informatics demonstrating how formal loan ontologies can detect and correct logical hallucinations in RAG systems for financial loan documentation.

## Overview

Standard RAG systems generate answers that sound plausible but may violate strict domain-specific logical constraints. This project implements a **Validation Layer** that uses a **LOAN Ontology** and Description Logic reasoning to ensure logical consistency in LLM-generated loan and financial text.

### The Problem

LLMs can generate factually incorrect statements that violate fundamental logical rules in the loan domain, such as:
- Classifying a loan type incorrectly (e.g., claiming a commercial loan is a student loan)
- Stating conflicting loan characteristics (e.g., a subsidized loan with private lender)
- Violating cardinality constraints (e.g., multiple guarantors when only one is allowed)
- Asserting impossible relationships between borrowers, lenders, and loans

### The Solution

A three-component system:
1. **Generator (RAG Pipeline)**: Standard RAG using LangChain + ChromaDB
2. **Extractor**: LLM-based triple extraction mapping to LOAN ontology classes
3. **Validator**: Ontology reasoning with HermiT/Pellet to detect inconsistencies

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Query                               │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  Component A: RAG Pipeline (Generator)                      │
│  • Chunk & Embed Documents                                  │
│  • Retrieve Top-k Context                                   │
│  • Generate Answer (Temperature=0.7)                        │
└─────────────────┬───────────────────────────────────────────┘
                  │ Answer Text
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  Component B: Triple Extractor                              │
│  • Parse Answer                                             │
│  • Extract Entities & Relations                             │
│  • Map to LOAN Ontology Classes                             │
└─────────────────┬───────────────────────────────────────────┘
                  │ RDF Triples
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  Component C: Ontology Validator                            │
│  • Load LOAN Ontology                                       │
│  • Create Individuals                                       │
│  • Assert Properties                                        │
│  • Run HermiT/Pellet Reasoner                               │
│  • Detect Inconsistencies                                   │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
          ✓ Valid / ✗ Invalid + Explanation
```

## Tech Stack

- **Language**: Python 3.10+
- **Orchestration**: LangChain
- **Ontology & Reasoning**: Owlready2 (with HermiT/Pellet reasoners)
- **Vector DB**: ChromaDB (local, transient)
- **LLM**: OpenAI API (gpt-4o)
- **Data Format**: RDF/XML for ontologies

## LOAN Ontology Coverage

This project uses a custom LOAN ontology with the following modules:

### Loans General Module
- `Loan` (base class for all loan types)
- `Lender` (financial institutions providing loans)
- `Borrower` (entities receiving loans)
- Core properties: `hasLender`, `hasBorrower`, `hasLoanAmount`, `hasInterestRate`

### Loans Specific Module
- `ConsumerLoan` (loans to individual consumers)
- `CommercialLoan` (loans to businesses/corporations)
- `StudentLoan` (education financing)
- `SubsidizedStudentLoan` (government-subsidized education loans)
- `GreenLoan` (sustainable/environmental financing)
- `CardAccounts` (credit card accounts)

### Real Estate Loans Module
- `Mortgage` (real estate loans)
- Mortgage-specific properties and constraints

## Installation

### Prerequisites

- Python 3.10 or higher
- OpenAI API key
- LOAN ontology files (must be provided separately)

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/Enhancing-Logical-Consistency-of-Large-Language-Models-with-Ontology-Grounded-RAG.git
cd Enhancing-Logical-Consistency-of-Large-Language-Models-with-Ontology-Grounded-RAG
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up OpenAI API Key

```bash
# Option 1: Environment variable
export OPENAI_API_KEY='your-key-here'

# Option 2: Create .env file
echo "OPENAI_API_KEY=your-key-here" > .env
```

### Step 5: Set Up LOAN Ontologies

**IMPORTANT**: The project requires LOAN ontology files in the following structure:

```
ontologies/
├── loans general module/
│   └── Loans.rdf
├── loans specific module/
│   ├── ConsumerLoans.rdf
│   ├── CommercialLoans.rdf
│   ├── StudentLoans.rdf
│   ├── GreenLoans.rdf
│   └── CardAccounts.rdf
└── real estate loans module/
    └── Mortgages.rdf
```

These ontology files must be obtained separately. The `setup_ontologies.py` script in this repository attempts to download FIBO ontology files, which are **NOT** the correct ontologies for this system. You need LOAN-specific ontology files instead.

### Step 6: Add Loan Documentation

Place PDF documents related to loans in the `./data` directory:

```bash
mkdir -p data
# Copy your loan PDF documents to ./data
```

## Usage

### Interactive Mode

```bash
python main.py
```

This starts an interactive CLI where you can enter queries and see the complete validation pipeline in action.

### Single Query Mode

```bash
python main.py --query "What type of loan is described in the document?"
```

### Specify Documents

```bash
python main.py --docs data/loan_agreement.pdf data/facility_agreement.pdf
```

### Skip Validation (RAG Only)

```bash
python main.py --no-validate
```

### Command-Line Options

```
usage: main.py [-h] [--docs DOCS [DOCS ...]] [--query QUERY] [--no-validate]
               [--ontology-dir ONTOLOGY_DIR]

Options:
  --docs DOCS [DOCS ...]    PDF documents to load (default: all PDFs in ./data)
  --query QUERY             Single query to process (skip interactive mode)
  --no-validate             Skip ontology validation (RAG only)
  --ontology-dir DIR        Directory containing LOAN ontology files (default: ./ontologies)
```

## Project Structure

```
project/
├── data/                    # PDF loan documents for RAG
├── ontologies/              # LOAN ontology RDF/OWL files
│   ├── loans general module/
│   ├── loans specific module/
│   └── real estate loans module/
├── main.py                  # CLI entry point
├── rag_pipeline.py          # Component A: RAG Generator
├── extractor.py             # Component B: Triple Extractor
├── validator.py             # Component C: Ontology Validator
├── setup_ontologies.py      # Ontology download script (NOT FUNCTIONAL - downloads wrong ontology)
├── test_hermit_fix.py       # Tests for reasoner compatibility
├── test_extractor_loan_type.py  # Tests for loan type extraction
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (create this)
└── README.md                # This file
```

## How It Works

### 1. RAG Pipeline (Component A)

The RAG pipeline generates answers using standard retrieval-augmented generation from loan PDF documents.

```python
from rag_pipeline import RAGPipeline

pipeline = RAGPipeline()
pipeline.load_documents(["data/loan_agreement.pdf"])
result = pipeline.query("What type of loan is this?")
print(result["answer"])
```

**Note**: Temperature is set to 0.7 to encourage creative responses that may contain hallucinations for testing purposes.

### 2. Triple Extraction (Component B)

The extractor uses a specialized LLM prompt to map natural language to LOAN ontology-compliant triples:

```python
from extractor import TripleExtractor

extractor = TripleExtractor()
result = extractor.extract_triples("The loan is a Subsidized Student Loan for education purposes.")

# Output: [{"sub": "TheLoan", "pred": "rdf:type", "obj": "SubsidizedStudentLoan", ...}]
```

The extractor recognizes loan-specific entities like:
- Loan types (StudentLoan, Mortgage, CommercialLoan, etc.)
- Relationships (hasLender, hasBorrower, hasGuarantor)
- Type assertions (rdf:type for classifying loans)

### 3. Ontology Validation (Component C)

The validator checks triples against the LOAN ontology using HermiT or Pellet reasoner:

```python
from validator import OntologyValidator

validator = OntologyValidator()
result = validator.validate_triples(triples)

if not result.is_valid:
    print(f"Inconsistency detected: {result.explanation}")
```

### Types of Inconsistencies Detected

The system detects several types of logical violations:

1. **Disjointness Violations**
   - Example: An entity cannot be both a ConsumerLoan and a CommercialLoan
   - The ontology defines these classes as mutually exclusive

2. **Cardinality Violations**
   - Example: A property that should have exactly one value has multiple
   - Violating max/min cardinality constraints defined in the ontology

3. **Domain/Range Violations**
   - Example: Applying `hasLender` to an entity that isn't a Loan
   - Properties have specific domain and range restrictions

4. **Type Inconsistencies**
   - Example: Asserting incompatible types for the same entity
   - An entity cannot be both a StudentLoan and a Mortgage simultaneously

## Known Issues and Limitations

### 1. HermiT Reasoner langString Incompatibility

**Issue**: The HermiT reasoner does not support the `langString` datatype that appears in many RDF ontologies with language-tagged literals (e.g., `"Text"@en`).

**Symptoms**: When running validation, you may see:
```
[!] HermiT cannot handle langString datatype in ontology schema
```

**Workaround**: The system automatically falls back to the Pellet reasoner when HermiT fails due to langString issues. This is handled transparently in validator.py:230-294.

**Impact**: Validation still works, but uses Pellet instead of HermiT. Pellet is also a complete OWL-DL reasoner and provides equivalent inconsistency detection.

### 2. setup_ontologies.py Downloads Wrong Ontology

**Issue**: The `setup_ontologies.py` script downloads FIBO (Financial Industry Business Ontology) files, but the validator expects LOAN ontology files.

**Impact**: Running `python setup_ontologies.py` will download files that the system cannot use.

**Workaround**: You must manually obtain the LOAN ontology files and place them in the correct directory structure (see Installation Step 5).

### 3. Memory Requirements for Reasoning

**Issue**: Description Logic reasoning can be memory-intensive, especially with large ontologies.

**Configuration**: The validator sets Java heap memory to 4GB in validator.py:33:
```python
owlready2.reasoning.JAVA_MEMORY = 4000
```

**Workaround**: If you encounter memory errors, you can:
- Reduce the ontology scope (load fewer modules)
- Increase the memory limit if your system has more RAM
- Process fewer documents at once

### 4. Temperature Setting Encourages Hallucinations

**Not a Bug**: The RAG pipeline uses `temperature=0.7` (rag_pipeline.py:59) intentionally to encourage creative/hallucinated responses for testing the validation layer.

**Note**: For production use, you should set `temperature=0.0` or lower values for more deterministic outputs.

## Testing the System

### Test with Valid Loan Statement

```bash
python test_hermit_fix.py
```

This tests extraction and validation of a valid loan type statement.

### Test Individual Components

Each component can be tested independently:

```bash
# Test RAG Pipeline only
python rag_pipeline.py

# Test Triple Extractor only
python extractor.py

# Test Validator only
python validator.py
```

### Example Test Case

Create a test document or use the provided sample:

```python
from main import OVRAGSystem

system = OVRAGSystem()
system.load_documents(["data/facility_agreement_loan.pdf"])

# Valid query
result = system.process_query("What type of loan is described in the document?")

# The validator should accept valid loan classifications
# and reject logically inconsistent statements
```

## Configuration

Key parameters can be adjusted in the code:

**RAG Configuration** (rag_pipeline.py):
```python
temperature = 0.7      # Higher = more creative/risky answers
chunk_size = 1000      # Size of text chunks
chunk_overlap = 200    # Overlap between chunks
top_k = 3              # Number of chunks to retrieve
```

**LLM Models** (main.py):
```python
rag_model = "gpt-4o"              # For answer generation
extraction_model = "gpt-4o"        # For triple extraction
embedding_model = "text-embedding-3-small"  # For embeddings
```

**Java Memory for Reasoner** (validator.py):
```python
owlready2.reasoning.JAVA_MEMORY = 4000  # 4GB heap size
```

## Troubleshooting

### "LOAN ontology files not found"

Ensure your ontology files are in the correct directory structure:
```bash
ontologies/
├── loans general module/Loans.rdf
├── loans specific module/*.rdf
└── real estate loans module/Mortgages.rdf
```

The `setup_ontologies.py` script does NOT download the correct files. You must obtain LOAN ontology files separately.

### "OpenAI API key not found"

Set your API key:
```bash
export OPENAI_API_KEY='your-key-here'
# Or create a .env file with: OPENAI_API_KEY=your-key-here
```

### "No PDF files found"

Add loan PDF documents to the `./data` directory:
```bash
mkdir -p data
cp your_loan_agreement.pdf data/
```

### Reasoning Takes Too Long

The reasoner can be slow with complex ontologies. To improve performance:
- Reduce the number of ontology modules loaded
- Increase Java heap memory if you have sufficient RAM
- Consider using only essential ontology modules for your use case

### Memory Issues

If you encounter out-of-memory errors:
1. Increase `owlready2.reasoning.JAVA_MEMORY` in validator.py:33
2. Reduce chunk size in RAG pipeline
3. Process fewer documents at once
4. Reduce top-k retrieval parameter

### HermiT Reasoner Errors

If you see HermiT errors about langString:
- This is expected behavior with ontologies containing language tags
- The system automatically falls back to Pellet reasoner
- Validation still works correctly
- No action required

## Research Context

This project is part of a Bachelor Thesis investigating:

1. **Logical Consistency in LLMs**: How often do LLMs violate domain-specific logical constraints in the loan/financial domain?
2. **Ontology-Based Validation**: Can formal ontologies effectively detect these violations?
3. **RAG Enhancement**: Does adding an ontology validation layer improve RAG reliability for financial compliance?

### Evaluation Metrics

The system can be evaluated on:
- **Precision**: False positive rate (valid answers marked invalid)
- **Recall**: False negative rate (invalid answers marked valid)
- **Explanation Quality**: Usefulness of inconsistency explanations
- **Latency**: Time overhead of validation layer

## Future Work

Potential extensions:

1. **Automatic Correction**: Not just detect, but suggest corrected answers
2. **Expanded Ontology Coverage**: Include more loan types and financial instruments
3. **Other Domain Ontologies**: Test with different domain ontologies (medical, legal, etc.)
4. **User Feedback Loop**: Learn from user corrections to improve extraction
5. **Performance Optimization**: Caching, incremental reasoning, parallel processing
6. **Fine-tuned Extractor**: Train a specialized model for LOAN ontology extraction
7. **Fix setup_ontologies.py**: Create proper script to obtain LOAN ontology files

## Contributing

This is a thesis project, but suggestions and issues are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## References

- **Owlready2**: Python package for ontology-oriented programming - https://owlready2.readthedocs.io/
- **LangChain**: Framework for LLM applications - https://langchain.com/
- **HermiT Reasoner**: OWL reasoner - http://www.hermit-reasoner.com/
- **Pellet Reasoner**: Alternative OWL-DL reasoner - https://github.com/stardog-union/pellet
- **OpenAI API**: https://platform.openai.com/docs/api-reference

## Citation

If you use this work in your research, please cite:

```bibtex
@thesis{yourname2024,
  title={Enhancing Logical Consistency of Large Language Models with Ontology-Grounded Retrieval Augmented Generation},
  author={Your Name},
  year={2024},
  school={Your University},
  type={Bachelor's Thesis}
}
```

## Contact

For questions or feedback:
- Email: your.email@example.com
- GitHub Issues: https://github.com/yourusername/repo/issues

## Acknowledgments

- LOAN ontology development team
- Owlready2 maintainers
- LangChain community
- OpenAI for API access
- HermiT and Pellet reasoner developers
