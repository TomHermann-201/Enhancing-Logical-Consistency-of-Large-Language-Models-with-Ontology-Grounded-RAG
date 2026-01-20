# Enhancing Logical Consistency of Large Language Models with Ontology-Grounded RAG

A Bachelor Thesis project in Business Informatics demonstrating how formal ontologies (FIBO) can detect and correct logical hallucinations in RAG systems.

## Overview

Standard RAG systems generate answers that sound plausible but may violate strict domain-specific logical constraints. This project implements a **Validation Layer** that uses the **Financial Industry Business Ontology (FIBO)** and Description Logic reasoning to ensure logical consistency in LLM-generated financial text.

### The Problem

LLMs can generate factually incorrect statements that violate fundamental logical rules, such as:
- Stating a "Natural Person" is a "Wholly Owned Subsidiary"
- Claiming a company owns itself
- Violating cardinality constraints (e.g., multiple sole owners)

### The Solution

A three-component system:
1. **Generator (RAG Pipeline)**: Standard RAG using LangChain + ChromaDB
2. **Extractor**: LLM-based triple extraction mapping to FIBO classes
3. **Validator**: Ontology reasoning with HermiT to detect inconsistencies

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Query                                │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  Component A: RAG Pipeline (Generator)                       │
│  • Chunk & Embed Documents                                   │
│  • Retrieve Top-k Context                                    │
│  • Generate Answer (Temperature=0.7)                         │
└─────────────────┬───────────────────────────────────────────┘
                  │ Answer Text
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  Component B: Triple Extractor                               │
│  • Parse Answer                                              │
│  • Extract Entities & Relations                              │
│  • Map to FIBO Classes (CURIEs)                              │
└─────────────────┬───────────────────────────────────────────┘
                  │ RDF Triples
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  Component C: Ontology Validator                             │
│  • Load FIBO Ontology                                        │
│  • Create Individuals                                        │
│  • Assert Properties                                         │
│  • Run HermiT Reasoner                                       │
│  • Detect Inconsistencies                                    │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
          ✓ Valid / ✗ Invalid + Explanation
```

## Tech Stack

- **Language**: Python 3.10+
- **Orchestration**: LangChain
- **Ontology & Reasoning**: Owlready2 (with HermiT reasoner)
- **Vector DB**: ChromaDB (local, transient)
- **LLM**: OpenAI API (gpt-4o)
- **Data Format**: RDF/XML for ontologies

## Installation

### Prerequisites

- Python 3.10 or higher
- OpenAI API key
- Internet connection (for initial ontology download)

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

### Step 5: Download FIBO Ontologies

```bash
python setup_ontologies.py
```

This will download the required FIBO modules:
- FND (Foundations): Relations, Agreements & Contracts
- BE (Business Entities): Legal Persons, Corporations, Corporate Control

### Step 6: Add Financial Documents

Place PDF documents in the `./data` directory:

```bash
mkdir -p data
# Copy your financial PDF documents to ./data
```

## Usage

### Interactive Mode

```bash
python main.py
```

This starts an interactive CLI where you can enter queries and see the complete validation pipeline in action.

### Single Query Mode

```bash
python main.py --query "Who owns ACME Corporation?"
```

### Specify Documents

```bash
python main.py --docs data/report1.pdf data/report2.pdf
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
  --ontology-dir DIR        Directory containing FIBO ontology files (default: ./ontologies)
```

## Project Structure

```
ov-rag-thesis/
├── data/                    # PDF documents for RAG
├── ontologies/              # FIBO RDF/OWL files
├── main.py                  # CLI entry point
├── rag_pipeline.py          # Component A: RAG Generator
├── extractor.py             # Component B: Triple Extractor
├── validator.py             # Component C: Ontology Validator
├── setup_ontologies.py      # Ontology download script
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (create this)
└── README.md                # This file
```

## How It Works

### 1. RAG Pipeline (Component A)

The RAG pipeline generates answers using standard retrieval-augmented generation:

```python
from rag_pipeline import RAGPipeline

pipeline = RAGPipeline()
pipeline.load_documents(["data/financial_report.pdf"])
result = pipeline.query("Who owns TechStart Inc.?")
print(result["answer"])
```

**Note**: Temperature is set to 0.7 to encourage creative responses that may contain hallucinations for testing purposes.

### 2. Triple Extraction (Component B)

The extractor uses a specialized LLM prompt to map natural language to FIBO-compliant triples:

```python
from extractor import TripleExtractor

extractor = TripleExtractor()
result = extractor.extract_triples("ACME Corp acquired TechStart Inc.")

# Output: [{"sub": "ACME Corp", "pred": "isAcquiredBy", "obj": "TechStart Inc.", ...}]
```

### 3. Ontology Validation (Component C)

The validator checks triples against FIBO using the HermiT reasoner:

```python
from validator import OntologyValidator

validator = OntologyValidator()
result = validator.validate_triples(triples)

if not result.is_valid:
    print(f"Inconsistency detected: {result.explanation}")
```

### Types of Inconsistencies Detected

The system detects three main types of logical violations:

1. **Disjointness Violations**
   - Example: A NaturalPerson cannot be a Corporation
   - FIBO defines these classes as mutually exclusive

2. **Cardinality Violations**
   - Example: `isWhollyOwnedBy` implies exactly one parent
   - Multiple ownership statements violate cardinality constraints

3. **Irreflexivity Violations**
   - Example: A company cannot own itself
   - Certain properties are defined as irreflexive in FIBO

## Testing the System

### Test with Valid Statement

```bash
python main.py --query "What is the corporate structure of ACME Corporation?"
```

Expected: Answer should validate successfully if it respects FIBO constraints.

### Test with Invalid Statement

Create a test document that contains a logical inconsistency, such as:
- "John Doe is the parent company of Global Industries"
- "The company is wholly owned by itself"

The validator should detect and flag these inconsistencies.

### Component Testing

Each component can be tested independently:

```bash
# Test RAG Pipeline only
python rag_pipeline.py

# Test Triple Extractor only
python extractor.py

# Test Validator only
python validator.py
```

## FIBO Ontology Scope

This project uses a focused subset of FIBO:

### FND (Foundations)
- `fibo-fnd-rel-rel`: Relations
- `fibo-fnd-agr-ctr`: Agreements and Contracts

### BE (Business Entities)
- `fibo-be-le-lp`: Legal Persons
- `fibo-be-corp-corp`: Corporations
- `fibo-be-oac-cctl`: Corporate Control and Subsidiaries

## Troubleshooting

### "FIBO ontology files not found"

Run the setup script:
```bash
python setup_ontologies.py
```

If automatic download fails, manually download from:
https://spec.edmcouncil.org/fibo/ontology/

### "OpenAI API key not found"

Set your API key:
```bash
export OPENAI_API_KEY='your-key-here'
# Or create a .env file with: OPENAI_API_KEY=your-key-here
```

### "No PDF files found"

Add PDF documents to the `./data` directory:
```bash
mkdir -p data
cp your_financial_report.pdf data/
```

### Reasoning Takes Too Long

The HermiT reasoner can be slow with large ontologies. Ensure you're only loading the required FIBO modules (not the entire FIBO ontology).

### Memory Issues

If you encounter memory errors:
- Reduce chunk size in RAG pipeline
- Process fewer documents at once
- Reduce top-k retrieval parameter

## Configuration

Key parameters can be adjusted in `main.py`:

```python
# RAG Configuration
temperature = 0.7      # Higher = more creative/risky answers
chunk_size = 1000      # Size of text chunks
chunk_overlap = 200    # Overlap between chunks
top_k = 3              # Number of chunks to retrieve

# LLM Models
rag_model = "gpt-4o"              # For answer generation
extraction_model = "gpt-4o"        # For triple extraction
embedding_model = "text-embedding-3-small"  # For embeddings
```

## Research Context

This project is part of a Bachelor Thesis investigating:

1. **Logical Consistency in LLMs**: How often do LLMs violate domain-specific logical constraints?
2. **Ontology-Based Validation**: Can formal ontologies effectively detect these violations?
3. **RAG Enhancement**: Does adding an ontology validation layer improve RAG reliability?

### Evaluation Metrics

The system can be evaluated on:
- **Precision**: False positive rate (valid answers marked invalid)
- **Recall**: False negative rate (invalid answers marked valid)
- **Explanation Quality**: Usefulness of inconsistency explanations

## Future Work

Potential extensions:

1. **Automatic Correction**: Not just detect, but suggest corrected answers
2. **Expanded FIBO Coverage**: Include more FIBO domains
3. **Other Ontologies**: Test with different domain ontologies (medical, legal, etc.)
4. **User Feedback Loop**: Learn from user corrections
5. **Performance Optimization**: Caching, incremental reasoning

## Contributing

This is a thesis project, but suggestions and issues are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## References

- **FIBO**: Financial Industry Business Ontology - https://spec.edmcouncil.org/fibo/
- **Owlready2**: Python package for ontology-oriented programming - https://owlready2.readthedocs.io/
- **LangChain**: Framework for LLM applications - https://langchain.com/
- **HermiT Reasoner**: OWL reasoner - http://www.hermit-reasoner.com/

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

- FIBO development team at EDM Council
- Owlready2 maintainers
- LangChain community
- OpenAI for API access
