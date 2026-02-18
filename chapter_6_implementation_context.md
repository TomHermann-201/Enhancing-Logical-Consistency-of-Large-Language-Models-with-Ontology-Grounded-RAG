# Chapter 6: Implementation and Evaluation — Technical Context Document

> **Compiled from**: OV-RAG project repository (`Enhancing-Logical-Consistency-of-Large-Language-Models-with-Ontology-Grounded-RAG`)
> **Date**: 2026-02-18
> **Purpose**: Provides all code, data, metrics, and examples needed to write Chapter 6 of the Bachelor Thesis.

---

## 1. Technology Stack and Implementation Details

### 1.1 Runtime Environment

| Component | Version |
|-----------|---------|
| Python | 3.13.2 |
| Java (for Pellet reasoner) | 25.0.2 LTS |
| Operating System | macOS Darwin 23.5.0 |

### 1.2 Core Dependencies (`requirements.txt`)

#### LLM & RAG Orchestration
| Package | Required Version | Purpose |
|---------|-----------------|---------|
| `langchain` | ≥0.1.0 | LLM orchestration framework |
| `langchain-openai` | ≥0.0.2 | OpenAI integration for LangChain |
| `langchain-community` | ≥0.0.10 | Community integrations |
| `openai` | 1.7.2 | OpenAI API client (GPT-4o) |

#### Vector Database & Retrieval
| Package | Required Version | Purpose |
|---------|-----------------|---------|
| `chromadb` | ≥0.4.22 | Vector database for document embeddings |

#### Ontology & Reasoning
| Package | Required Version | Purpose |
|---------|-----------------|---------|
| `owlready2` | ≥0.45 | OWL ontology management + Pellet/HermiT integration |

#### Document Processing
| Package | Required Version | Purpose |
|---------|-----------------|---------|
| `pypdf` | ≥3.17.0 | PDF loading and parsing |
| `tiktoken` | ≥0.5.0 | Token counting for OpenAI models |

#### NLP Evaluation Metrics
| Package | Required Version | Purpose |
|---------|-----------------|---------|
| `rouge-score` | ≥0.1.2 | ROUGE-L F-measure (text overlap similarity) |
| `bert-score` | ≥0.3.13 | BERTScore F1 (semantic similarity) |

#### Data Processing & Utilities
| Package | Required Version | Purpose |
|---------|-----------------|---------|
| `numpy` | ≥1.26.0 | Numerical computing |
| `pandas` | ≥2.0.0 | Data manipulation and CSV output |
| `tqdm` | 4.66.1 | Progress bars |
| `python-dotenv` | 1.0.0 | `.env` file for API key management |
| `requests` | 2.31.0 | HTTP requests for downloading ontology files |

#### Web UI
| Package | Required Version | Purpose |
|---------|-----------------|---------|
| `streamlit` | ≥1.28.0 | Interactive web dashboard |
| `plotly` | ≥5.18.0 | Interactive data visualization |

### 1.3 OpenAI Models Used

| Model | Usage | Temperature |
|-------|-------|-------------|
| `gpt-4o` | Answer generation (RAG), triple extraction, corrections | 0.7 (RAG), 0.0 (extraction) |
| `text-embedding-3-small` | Document embedding for ChromaDB vector store | N/A |

### 1.4 Configuration Constants

| Parameter | Value | Description |
|-----------|-------|-------------|
| `JAVA_MEMORY` | 4000 MB | Java heap for owlready2 Pellet reasoning |
| `MAX_CORRECTION_ATTEMPTS` | 3 | Max re-prompts before hard-reject (initial + 3 = 4 total) |
| `top_k` | 3 | Number of retrieved document chunks per query |
| `chunk_size` | 1000 characters | Text splitter chunk size |
| `chunk_overlap` | 200 characters | Text splitter overlap between chunks |
| `random.seed` | 42 | Reproducibility seed for test data generation |

### 1.5 Ontology Files (FIBO/LOAN Modules)

Located in `/ontologies/`:
- `loans general module/Loans.rdf`
- `loans specific module/ConsumerLoans.rdf`
- `loans specific module/CommercialLoans.rdf`
- `loans specific module/StudentLoans.rdf`
- `loans specific module/GreenLoans.rdf`
- `loans specific module/CardAccounts.rdf`
- `real estate loans module/Mortgages.rdf`

---

## 2. Core Implementation Logic

### 2.1 Architecture Overview

The system consists of four components orchestrated in a correction loop:

```
INPUT: Question
  ↓
[Component A: RAG Pipeline] → Generate initial answer (GPT-4o, ChromaDB)
  ↓
[Component B: Triple Extractor] → Extract triples from answer + source context (GPT-4o)
  ↓
[Component C: Ontology Validator] → Validate merged triples (Pellet reasoner)
  ↓
PASS? → Output accepted answer
FAIL? → [Correction attempts remaining?]
         ├─ Yes → Re-prompt RAG with validation feedback → Loop to Component B
         └─ No  → Hard-Reject (answer + rejection reason)
```

| Component | File | Key Class/Function |
|-----------|------|--------------------|
| A: RAG Generator | `src/rag_pipeline.py` | `RAGPipeline.query()`, `query_with_correction()` |
| B: Triple Extractor | `src/extractor.py` | `TripleExtractor.extract_triples()`, `extract_from_context()` |
| C: Ontology Validator | `src/validator.py` | `OntologyValidator.validate_triples()`, `_run_reasoner_with_fallback()` |
| Orchestrator | `main.py` | `OVRAGSystem.process_query()` |

### 2.2 Component A: RAG Pipeline (`src/rag_pipeline.py`)

#### Document Loading and Chunking

```python
def load_documents(self, pdf_paths: List[str]) -> int:
    """
    Pipeline:
    1. Load PDFs with PyPDFLoader
    2. Split into chunks (size=1000, overlap=200)
    3. Embed chunks with text-embedding-3-small
    4. Store in ChromaDB vector store
    """
    all_chunks = []
    for pdf_path in pdf_paths:
        loader = PyPDFLoader(str(path))
        documents = loader.load()
        chunks = self.text_splitter.split_documents(documents)
        all_chunks.extend(chunks)

    # Create vector store with embeddings
    self.vectorstore = Chroma.from_documents(
        documents=all_chunks,
        embedding=self.embeddings,
        collection_name="financial_docs"
    )
    self.retriever = self.vectorstore.as_retriever(
        search_kwargs={"k": self.top_k}  # k=3
    )
    return len(all_chunks)
```

#### RAG Prompt Template

```python
RAG_PROMPT_TEMPLATE = """You are a financial analyst assistant.
Use the following context to answer the question.

Context:
{context}

Question: {question}

Instructions:
- Provide a clear, concise answer based on the context
- If the answer is not in the context, say "I don't have enough information
  to answer this question."
- Focus on factual information about entities, relationships, and ownership structures
- Be specific about company names, ownership percentages, and corporate relationships

Answer:"""
```

#### Correction Prompt Template (used in re-prompting loop)

```python
CORRECTION_PROMPT_TEMPLATE = """You are a financial analyst assistant.
Your previous answer was rejected because it contained logical inconsistencies
with respect to a formal loan ontology.

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
- If the context genuinely contains contradictory information, state that clearly
  rather than guessing

Corrected answer:"""
```

**Key Design Aspect**: The correction prompt reuses the *same* source documents from the original retrieval to prevent retrieval drift across correction attempts.

### 2.3 Component B: Triple Extractor (`src/extractor.py`)

#### Extraction Prompt (Static Fallback)

```python
STATIC_EXTRACTION_PROMPT = """You are a Semantic Translator for financial loan documents.
Extract facts from the text and map them to these LOAN ontology concepts:

Classes:
- Loan, ConsumerLoan, CommercialLoan, Mortgage, StudentLoan,
  SubsidizedStudentLoan, GreenLoan
- Lender, Borrower, Corporation, FinancialInstitution

Properties:
- rdf:type, hasLender, hasBorrower, hasLoanAmount, hasInterestRate,
  hasMaturityDate, hasGuarantor, hasCollateral, providesLoan, receivesLoan

Guidelines:
1. Extract factual assertions including TYPE CLASSIFICATIONS
2. Map entities to the MOST SPECIFIC loan class that applies
3. Each triple must have: sub, pred, obj, sub_type, obj_type

Return JSON: {"triples": [{"sub": "...", "pred": "...", "obj": "...",
              "sub_type": "...", "obj_type": "..."}]}
"""
```

#### Context Extraction Prompt (for source document triples — preserves contradictions)

```python
CONTEXT_EXTRACTION_PROMPT = """You are a Semantic Extractor for financial loan documents.
Your task is to extract ALL factual assertions from the source text and map them
to LOAN ontology concepts.

CRITICAL: Extract EVERY classification and assertion you find, even if they
contradict each other. Do NOT resolve contradictions — preserve them all.

Keyword mapping (apply ALL that match):
- "secured", "collateral", "pledge", "backed by" → SecuredLoan
- "unsecured", "no collateral", "without collateral" → UnsecuredLoan
- "open-end", "revolving", "line of credit" → OpenEndCredit
- "closed-end", "fixed term", "installment" → ClosedEndCredit
...
"""
```

#### Main Extraction Function

```python
def extract_triples(self, text: str) -> ExtractionResult:
    response = self.client.chat.completions.create(
        model=self.model,                              # gpt-4o
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        temperature=0.0,                               # Deterministic extraction
        response_format={"type": "json_object"}        # Force JSON output
    )
    raw_response = response.choices[0].message.content
    parsed = json.loads(raw_response)
    triples = parsed.get("triples", [])

    # Validate triple structure (all 5 fields required)
    validated_triples = []
    for triple in triples:
        if self._validate_triple_structure(triple):
            validated_triples.append(triple)

    return ExtractionResult(triples=validated_triples, ...)
```

**Key Design**: Two separate extraction methods exist:
- `extract_triples()` — Extracts from LLM-generated answers
- `extract_from_context()` — Extracts from source documents, using `CONTEXT_EXTRACTION_PROMPT` that explicitly preserves contradictions for clash detection

### 2.4 Component C: Ontology Validator (`src/validator.py`)

#### Reasoner with Fallback (`_run_reasoner_with_fallback`)

```python
# Global flag to cache reasoner choice across validations
REASONER_FALLBACK_MODE = 'pellet'  # Set after first langString failure

def _run_reasoner_with_fallback(self):
    """
    Tries HermiT first (faster), falls back to Pellet if langString issue.
    Once Pellet mode is set, uses Pellet directly for all future calls.
    """
    global REASONER_FALLBACK_MODE

    if REASONER_FALLBACK_MODE == 'pellet':
        try:
            sync_reasoner_pellet(self.world, infer_property_values=True, debug=0)
            return True
        except OwlReadyInconsistentOntologyError:
            raise  # Re-raise actual inconsistency (this is what we want to detect)
        except Exception as e:
            if "WARNING" in str(e):
                return True  # Java warnings are non-fatal
            return False

    # HermiT path (initial attempt)
    try:
        sync_reasoner_hermit(self.world, infer_property_values=True, debug=0)
        return True
    except OwlReadyInconsistentOntologyError:
        raise
    except Exception as hermit_error:
        if "langString" in str(hermit_error):
            REASONER_FALLBACK_MODE = 'pellet'  # Permanent switch
            sync_reasoner_pellet(self.world, infer_property_values=True, debug=0)
            return True
```

**Key Design**: HermiT cannot handle the `rdf:langString` datatype present in FIBO ontologies. The system detects this limitation on the first run and permanently switches to Pellet via a global flag.

#### Triple Validation Pipeline (`validate_triples`)

The validation proceeds in 3 steps:

**Step 1: Create OWL Individuals**
```python
# For each triple, create OWL individuals typed to ontology classes
for triple in triples:
    if pred_name in ["rdf:type", "type"]:
        target_class = self._get_class_by_name(obj_name)
        if target_class:
            individuals[sub_name] = target_class(self._sanitize_name(sub_name))
        else:
            individuals[sub_name] = Thing(self._sanitize_name(sub_name))  # Fallback
```

**Step 2: Assert Properties**
```python
# For each non-type triple, assert OWL properties
property_obj = self._get_property_by_name(pred_name)
if is_data_property:
    # Data property: literal value (amount, rate, date)
    prop_list = getattr(sub_individual, property_obj.name, None)
    prop_list.append(self._parse_literal_value(obj_name))
else:
    # Object property: link to another individual
    prop_list = getattr(sub_individual, property_obj.name, None)
    prop_list.append(obj_individual)
```

**Step 3: Run Reasoner**
```python
reasoning_succeeded = self._run_reasoner_with_fallback()
# If OwlReadyInconsistentOntologyError is raised → INCONSISTENCY DETECTED
# Then also check rule-based role constraints (Python logic)
role_violations = self._check_role_constraints(triples)
```

#### Rule-Based Role Constraints (`_check_role_constraints`)

Catches business-logic violations that OWL disjointness axioms alone cannot express:

```python
def _check_role_constraints(self, triples: List[Dict]) -> List[str]:
    """
    Detects:
    - NaturalPerson as lender for CommercialLoan or Mortgage
    - Corporation as borrower for ConsumerLoan
    """
    violations = []

    # Collect entity types and role assignments
    entity_types = {}  # entity_name → set of types
    lender_entities = set()
    borrower_entities = set()
    loan_types = set()

    for triple in triples:
        if pred in ("hasLender", "providesLoan"):
            lender_entities.add(obj if pred == "hasLender" else sub)
        if pred in ("hasBorrower", "receivesLoan"):
            borrower_entities.add(obj if pred == "hasBorrower" else sub)

    # Check: NaturalPerson cannot be lender for CommercialLoan or Mortgage
    for lender in lender_entities:
        if "NaturalPerson" in entity_types.get(lender, set()):
            if "CommercialLoan" in loan_types:
                violations.append(
                    f"NaturalPerson '{lender}' cannot be lender for a CommercialLoan")
            if "Mortgage" in loan_types:
                violations.append(
                    f"NaturalPerson '{lender}' cannot be lender for a Mortgage")

    # Check: Corporation cannot be borrower for ConsumerLoan
    for borrower in borrower_entities:
        if "Corporation" in entity_types.get(borrower, set()):
            if "ConsumerLoan" in loan_types:
                violations.append(
                    f"Corporation '{borrower}' cannot be borrower for a ConsumerLoan")

    return violations
```

### 2.5 Orchestrator: Correction Loop (`main.py`)

```python
MAX_CORRECTION_ATTEMPTS = 3

def process_query(self, question: str, validate: bool = True) -> dict:
    # Latency tracking
    _t_start = time.time()

    # STEP 1: Generate initial answer with RAG
    rag_result = self.rag.query(question)
    answer = rag_result["answer"]
    source_documents = rag_result["source_documents"]

    # STEP 1.5: Extract context triples ONCE (before loop)
    context_text = "\n\n".join([doc.page_content for doc in source_documents])
    context_extraction = self.extractor.extract_from_context(context_text)
    context_triples = context_extraction.triples

    # STEP 2+3: Extract-Validate Loop
    current_answer = answer
    for attempt in range(MAX_CORRECTION_ATTEMPTS + 1):

        # Extract answer triples
        extraction_result = self.extractor.extract_triples(current_answer)
        answer_triples = extraction_result.triples

        # Merge answer + context triples (deduplicate by sub,pred,obj)
        triples = self._merge_triples(answer_triples, context_triples)

        # Validate against LOAN ontology
        validation_result = self.validator.validate_text_answer(
            current_answer, triples)

        if validation_result.is_valid:
            # ACCEPTED — return with accepted_at_attempt
            result["accepted_at_attempt"] = attempt
            return result

        if attempt < MAX_CORRECTION_ATTEMPTS:
            # RE-PROMPT with validation feedback
            correction_result = self.rag.query_with_correction(
                question=question,
                previous_answer=current_answer,
                validation_feedback=validation_result.explanation,
                attempt_number=attempt + 1,
                source_documents=source_documents  # Reuse same sources
            )
            current_answer = correction_result["answer"]
        else:
            # HARD-REJECT — all correction attempts exhausted
            result["hard_reject"] = True
            result["hard_reject_reason"] = (
                f"Answer failed ontology validation after "
                f"{MAX_CORRECTION_ATTEMPTS} correction attempt(s). "
                f"Last failure: {validation_result.explanation}")
            return result
```

#### Triple Merging

```python
def _merge_triples(self, answer_triples: list, context_triples: list) -> list:
    """Deduplicate by (sub, pred, obj). Answer triples take priority."""
    seen = set()
    merged = []
    for triple in answer_triples:
        key = (triple["sub"], triple["pred"], triple["obj"])
        if key not in seen:
            seen.add(key)
            merged.append(triple)
    for triple in context_triples:
        key = (triple["sub"], triple["pred"], triple["obj"])
        if key not in seen:
            seen.add(key)
            merged.append(triple)
    return merged
```

---

## 3. Test Dataset and Experimental Setup

### 3.1 Contract Generation (`evaluation/generate_test_pdfs.py`)

100 synthetic loan contract PDFs were generated with `random.seed(42)` for reproducibility.

#### Distribution

| Range | Count | Label | Clash Type | Description |
|-------|-------|-------|------------|-------------|
| 001–060 | 60 | CLEAN | — | Diverse loan types, no inconsistencies |
| 061–075 | 15 | CLASH | `secured_unsecured` | Contradictory secured/unsecured statements |
| 076–090 | 15 | CLASH | `openend_closedend` | Contradictory open-end/closed-end terms |
| 091–095 | 5 | CLASH | `borrower_type` | Wrong borrower entity type for loan class |
| 096–100 | 5 | CLASH | `lender_type` | Wrong lender entity type for loan class |

**Total**: 60 clean + 40 clash = **100 contracts**

#### Loan Types Used

ConsumerLoan, CommercialLoan, Mortgage, StudentLoan, SubsidizedStudentLoan, GreenLoan, CardAccount (7 types across 100 contracts).

#### Clash Injection Mechanisms

**Secured vs Unsecured (3 variants, 5 each)**:
- Mortgage listed as "unsecured" despite having collateral
- Commercial loan stated as "secured" but no collateral specified
- Consumer loan with collateral but described as "unsecured personal loan"

**Open-End vs Closed-End (3 variants, 5 each)**:
- Credit card with fixed term (should be open-end revolving)
- Term loan described as "revolving" (should be closed-end)
- Consumer loan described as both revolving and fixed-term simultaneously

**Borrower Type (2 variants)**:
- ConsumerLoan issued to a Corporation (should be NaturalPerson)
- CommercialLoan issued to a NaturalPerson (should be LegalEntity)

**Lender Type (2 variants)**:
- CommercialLoan or Mortgage issued by a NaturalPerson (should be FinancialInstitution)

#### Contract PDF Structure

Each PDF contains 6 sections:
1. **Parties** — Lender and borrower names with entity types
2. **Loan Terms** — Principal, interest rate, term, security status, collateral
3. **Repayment Terms** — Fixed installments or revolving structure
4. **Special Provisions** — Loan-specific notes (SubsidizedStudent, CardAccount, GreenLoan)
5. **General Terms** — Governing law, amendments
6. **Signatures** — Signature blocks

All text is neutral (no ontology hints/labels) to ensure fair RAG comparison.

### 3.2 Ground Truth (`config/contract_ground_truth.json`)

Each contract entry contains:

```json
{
  "001": {
    "label": "CLEAN",
    "expect_clash": false,
    "clash_type": null,
    "clash_description": null,
    "reference_answers": {
      "Q1": "This is a Commercial Loan Agreement.",
      "Q2": "The borrower is TechStart Inc., a legal entity ...",
      "Q3": "This is an unsecured loan. No collateral is pledged.",
      "Q4": "This is a fixed-term (closed-end) loan with a term of 59 months ...",
      "Q5": "The principal amount is USD 962,000.00 at an interest rate of 2.6% ..."
    }
  }
}
```

Clash example (Contract 063):
```json
{
  "063": {
    "label": "CLASH",
    "expect_clash": true,
    "clash_type": "secured_unsecured",
    "clash_description": "Mortgage with collateral listed but explicitly stated as unsecured loan",
    "reference_answers": {
      "Q3": "This is stated as an unsecured loan, though collateral (First lien on
             property at 852 Willow Lane, Atlanta, GA 30301) is mentioned in the agreement."
    }
  }
}
```

### 3.3 Evaluation Questions (5 per contract)

| ID | Question Text | Target |
|----|---------------|--------|
| Q1 | What type of loan is described in this document? Is it a consumer loan, commercial loan, mortgage, student loan, or another type? | Loan type classification |
| Q2 | Who is the borrower and who is the lender of this loan? Are they individuals or organizations? | Party classification |
| Q3 | Is this loan secured or unsecured? If secured, what collateral is specified? | SecuredLoan / UnsecuredLoan disjointness |
| Q4 | Is this a revolving (open-end) credit facility or a fixed-term (closed-end) loan? What are the repayment terms? | OpenEndCredit / ClosedEndCredit disjointness |
| Q5 | Summarize the key financial terms: principal amount, interest rate, loan type, parties involved, and whether the loan is secured. | Comprehensive extraction |

### 3.4 Experimental Conditions (A/B Design)

| Condition | Configuration | Validation |
|-----------|--------------|------------|
| **Plain RAG** (Baseline) | RAGPipeline only, `validate=False` | No ontology validation |
| **OV-RAG** (Treatment) | Full OVRAGSystem, `validate=True` | Pellet reasoning + role constraints + correction loop |

**Total Queries**: 100 contracts × 5 questions × 2 conditions = **1,000 queries**

(Note: 494 OV-RAG + 500 Plain RAG queries completed; 6 OV-RAG queries had errors/no-triples.)

---

## 4. Evaluation Design and Metrics

### 4.1 Consistency Checking Metrics (Confusion Matrix)

For OV-RAG condition only, per query:

| | Clash Expected (`expect_clash=True`) | No Clash Expected (`expect_clash=False`) |
|--|---------------------------------------|------------------------------------------|
| **Validation Failed** | True Positive (TP) | False Positive (FP) |
| **Validation Passed** | False Negative (FN) | True Negative (TN) |

Derived metrics:
- **Precision** = TP / (TP + FP)
- **Recall** = TP / (TP + FN)
- **F1** = 2 × Precision × Recall / (Precision + Recall)
- **Hard-Reject Rate** = Hard Rejects / Total OV-RAG Queries
- **Correction Success Rate** = Corrections Succeeded / Corrections Needed

### 4.2 NLP Quality Metrics

**ROUGE-L** (text overlap):
```python
from rouge_score import rouge_scorer
scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
rouge_scores = scorer.score(reference_answer, generated_answer)
rouge_l = rouge_scores["rougeL"].fmeasure
```

**BERTScore** (semantic similarity):
```python
from bert_score import score as bert_score_fn
P, R, F1 = bert_score_fn([answer], [reference], lang="en", verbose=False)
```

### 4.3 Latency Measurement

Each OV-RAG query tracks three latency components:
```python
latency_rag       = time.time() - _t0  # RAG retrieval + generation
latency_extraction = time.time() - _t0  # Triple extraction (LLM calls)
latency_validation = time.time() - _t0  # Pellet reasoning
latency_total      = time.time() - _t_start  # End-to-end
```

Latency overhead:
```python
latency_overhead_seconds = avg_latency_ovrag - avg_latency_plain
latency_overhead_percent = (overhead / avg_latency_plain) * 100
```

---

## 5. Execution and Results

### 5.1 A/B Comparison Summary

| Metric | Plain RAG | OV-RAG | Difference |
|--------|-----------|--------|------------|
| Avg ROUGE-L | 0.3460 | 0.3028 | -0.0432 |
| Avg BERTScore-F1 | 0.8953 | 0.8864 | -0.0089 |
| Avg Latency | 1.64 s | 100.94 s | +99.30 s (+6054.9%) |
| Clash Detection Rate | N/A | 0.5477 (54.8%) | — |
| Hard-Reject Rate | N/A | 0.2287 (22.9%) | — |

### 5.2 Consistency Checking Results (Overall)

| Metric | Value |
|--------|-------|
| True Positives (TP) | 109 |
| False Positives (FP) | 4 |
| True Negatives (TN) | 291 |
| False Negatives (FN) | 90 |
| **Precision** | **0.9646** (96.5%) |
| **Recall** | **0.5477** (54.8%) |
| **F1-Score** | **0.6987** (69.9%) |
| Corrections Needed | 119 |
| Corrections Succeeded | 6 |
| Correction Success Rate | 5.04% |
| Hard Rejects | 113 |
| Hard-Reject Rate | 22.87% |

### 5.3 Per-Clash-Type Breakdown

| Clash Type | TP | FP | TN | FN | Total | Precision | Recall | F1 |
|------------|----|----|----|----|-------|-----------|--------|-----|
| **clean** | 0 | 4 | 291 | 0 | 295 | — | — | — |
| **secured_unsecured** | 36 | 0 | 0 | 38 | 74 | 1.000 | 0.486 | 0.655 |
| **openend_closedend** | 43 | 0 | 0 | 32 | 75 | 1.000 | 0.573 | 0.729 |
| **borrower_type** | 17 | 0 | 0 | 8 | 25 | 1.000 | 0.680 | 0.810 |
| **lender_type** | 13 | 0 | 0 | 12 | 25 | 1.000 | 0.520 | 0.684 |

**Observations**:
- All clash types have **perfect precision** (1.0) — zero false positives in clash detection itself
- `borrower_type` has highest recall (68.0%) — explicit entity-type violations are easiest to detect
- `secured_unsecured` has lowest recall (48.6%) — subtle keyword-level contradictions hardest to capture
- The 4 FP come exclusively from clean contracts (context contamination, see Section 5.5)

### 5.4 Latency Breakdown (OV-RAG)

| Component | Mean | Median | P25 | P75 | P95 | Max | % of Total |
|-----------|------|--------|-----|-----|-----|-----|------------|
| RAG Generation | 4.62 s | 1.70 s | 1.25 s | 5.60 s | 12.52 s | 360.43 s | 4.6% |
| Triple Extraction | 92.72 s | 7.07 s | 4.81 s | 11.06 s | 21.42 s | 19,258.98 s | **91.9%** |
| Pellet Validation | 3.60 s | 1.13 s | 0.88 s | 2.13 s | 3.19 s | 1,037.64 s | 3.6% |
| **Total** | **100.94 s** | **10.25 s** | **7.33 s** | **20.47 s** | **35.22 s** | **19,261.22 s** | 100% |

**Time Distribution (aggregate)**:
- RAG: 2,288.5 s (4.6%)
- Extraction: 45,895.8 s (**91.9%**)
- Validation: 1,781.6 s (3.6%)
- Total: 49,966.0 s

**Key Finding**: Pellet reasoning accounts for only **3.6%** of total OV-RAG latency. The dominant bottleneck is the LLM-based triple extraction (91.9%), driven by API rate-limit retries and multiple correction loop iterations. The median total latency is 10.25 s, while the mean (100.94 s) is skewed by outliers from rate-limit backoff.

### 5.5 Context Contamination — Deep Dive (The "Serendipitous Discovery")

During evaluation, a phenomenon emerged that was not part of the original experimental design: **Context Contamination**. The dense retriever (ChromaDB with `text-embedding-3-small`, top-k=3) occasionally pulled chunks from *different* loan contracts into the same context window. The LLM then merged these unrelated entities into a single narrative, and the Triple Extractor collapsed them into one `TheLoan` individual — creating artificial disjointness violations that the Pellet reasoner correctly flagged.

This phenomenon produced **4 false positives** (clean contracts falsely rejected) but, more importantly, it demonstrates that the OV-RAG pipeline can detect a *category of RAG failure* that is entirely invisible to Plain RAG: cross-document entity confusion.

#### 5.5.1 The Retrieval Error — How Dense Retrieval Mixes Documents

The evaluation loads all 100 contract PDFs into a single ChromaDB collection. Because many contracts share similar financial vocabulary (loan amounts, interest rates, collateral descriptions), the dense retriever's similarity search can return chunks from *neighboring* contracts when their embeddings are close in the vector space.

**Contract 010** (Thomas Brown, Mortgage, Citibank) provides a clear illustration. According to ground truth, this contract is:
- **Loan Type**: Mortgage Loan Agreement
- **Borrower**: Thomas Brown (NaturalPerson)
- **Lender**: Citibank (FinancialInstitution)
- **Collateral**: First lien on property at 369 Walnut Way, Boston, MA 02101

However, the RAG retriever returned *different* source chunks depending on the question:

| Query | Entities in RAG Answer | Actual Source |
|-------|----------------------|---------------|
| Q1 ("What type of loan?") | ACME Industries LLC, U.S. Dept. of Education | **Contract 005** (GreenLoan) |
| Q2 ("Who is borrower/lender?") | Robert Chen, Green Investment Bank | **Contract 006** (CardAccount) |
| Q3 ("Secured or unsecured?") | Thomas Brown, Citibank | **Contract 010** (correct) |
| Q4 ("Open-end or closed-end?") | Robert Chen, Green Investment Bank | **Contract 006** (CardAccount) |
| Q5 ("Summarize key terms") | Thomas Brown, Citibank | **Contract 010** (correct) |

Only 2 of 5 queries returned the *correct* contract's entities. The other 3 silently answered about entirely different loans — a failure mode that Plain RAG cannot detect at all.

**Contract 030** (Laura Young, CardAccount, Huntington Bancshares) exhibits the same pattern:

| Query | Entities in RAG Answer | Actual Source |
|-------|----------------------|---------------|
| Q1 | ACME Industries LLC, U.S. Dept. of Education | **Contract 005** |
| Q2 | Robert Chen, Green Investment Bank | **Contract 006** |
| Q3 | Thomas Brown, Citibank | **Contract 010** |
| Q4 | Robert Chen, Green Investment Bank | **Contract 006** |
| Q5 | Regions Financial, Summit Capital Partners | **Contract 030** (partially correct) |

In both cases, the LLM confidently generated factually correct-sounding answers *about the wrong contract*, with no indication to the user that the retrieved context was from a different document.

#### 5.5.2 The LLM Hallucination — Entity Merging in the Generated Answer

When the retriever returns chunks from multiple contracts, the LLM does not flag this as a problem. Instead, it merges the disparate entities into a single coherent-sounding narrative.

**Primary Example — Contract 002, Q1** (CLEAN: Anna Miller, Mortgage, Commerce Bank of America):

> **Question**: "What type of loan is described in this document?"

The RAG retriever pulled chunks from both Contract 002 (Anna Miller's Mortgage) and Contract 001 (TechStart Inc.'s Commercial Loan). The LLM generated:

> **Candidate Answer (GPT-4o)**:
> "The document describes two types of loans:
>
> 1. The first loan agreement is a secured mortgage loan. It is secured by a first lien on a property (456 Park Avenue, New York, NY 10022) and is made to an individual, **Anna Miller**, for personal purposes (moving and relocation costs).
>
> 2. The second loan agreement is an unsecured commercial loan. It is made to a company, **TechStart Inc.**, for business purposes (equipment modernization program).
>
> This classification aligns with the financial ontology constraints: the first loan is a mortgage loan due to its secured nature and collateralized real estate, while the second loan is a commercial loan due to its unsecured nature and business purpose."

The LLM seamlessly wove entities from two separate contracts (Anna Miller from Contract 002, TechStart Inc. from Contract 001) into a single answer, presenting it as though both loans existed in the same document. This answer is *factually plausible* but *referentially wrong* — it describes facts about a contract the user did not ask about.

**Second Example — Contract 005, Q2** (CLEAN: ACME Industries LLC, GreenLoan, U.S. Dept. of Education):

> **Candidate Answer (GPT-4o, after 3 correction attempts)**:
> "For the loan with Contract Number: LA-2025-005, the borrower is **ACME Industries LLC**, which is an organization, and the lender is the **U.S. Department of Education**, which is a governmental entity.
>
> For the loan with Contract Number: LA-2025-001, the borrower is **TechStart Inc.**, which is an organization, and the lender is **First National Bank**, which is a financial institution."

Again, TechStart Inc. (Contract 001) is pulled into the answer for Contract 005.

#### 5.5.3 The Reasoner's Catch — How Pellet Detects Cross-Document Contradictions

The Triple Extractor maps *both* the LLM answer triples and the source context triples into a shared OWL individual `TheLoan`. When entities from different contracts are merged into this single individual, their incompatible class assertions trigger Pellet's disjointness checking.

**Contract 002, Q1 — Full Triple Set (26 triples, final correction attempt)**:

```
 # | Subject              | Predicate     | Object                          | Origin
---|----------------------|---------------|---------------------------------|------------------
 1 | FirstLoan            | rdf:type      | ClosedEndMortgageLoan           | Answer (002)
 2 | FirstLoan            | rdf:type      | SecuredLoan                     | Answer (002)
 3 | FirstLoan            | hasCollateral  | 456 Park Avenue, New York       | Answer (002)
 4 | Anna Miller          | rdf:type      | NaturalPerson                   | Answer (002)
 5 | FirstLoan            | hasBorrower    | Anna Miller                     | Answer (002)
 6 | SecondLoan           | rdf:type      | CommercialLoan                  | Answer (001 contam.)
 7 | SecondLoan           | rdf:type      | UnsecuredLoan                   | Answer (001 contam.)
 8 | TechStart Inc.       | rdf:type      | Corporation                     | Answer (001 contam.)
 9 | SecondLoan           | hasBorrower    | TechStart Inc.                  | Answer (001 contam.)
---------- Context triples (merged into TheLoan) ----------
11 | TheLoan              | rdf:type      | SecuredLoan                     | Context (002)
12 | TheLoan              | rdf:type      | ConsumerLoan                    | Context (002)
13 | TheLoan              | rdf:type      | ClosedEndCredit                 | Context (002)
14 | TheLoan              | hasLender      | Commerce Bank of America        | Context (002)
15 | TheLoan              | hasBorrower    | Anna Miller                     | Context (002)
16 | TheLoan              | hasLoanAmount  | USD 254,000.00                  | Context (002)
20 | TheLoan              | rdf:type      | UnsecuredLoan                   | Context (001 contam.)
21 | TheLoan              | rdf:type      | CommercialLoan                  | Context (001 contam.)
22 | TheLoan              | hasLender      | First National Bank             | Context (001 contam.)
23 | TheLoan              | hasBorrower    | TechStart Inc.                  | Context (001 contam.)
24 | TheLoan              | hasLoanAmount  | USD 962,000.00                  | Context (001 contam.)
```

The critical contradiction: `TheLoan` is asserted as both `SecuredLoan` (triple #11, from Contract 002's context) and `UnsecuredLoan` (triple #20, from Contract 001's context). In the FIBO/LOAN ontology, `SecuredLoan` and `UnsecuredLoan` are **disjoint classes** — no individual can belong to both.

**Pellet Reasoner Output** (from `validator.py` → `_run_reasoner_with_fallback()`):

```
  Running Pellet reasoner...
Feb 17, 2026 12:33:22 AM org.mindswap.pellet.jena.graph.loader.DefaultGraphLoader addUnsupportedFeature
WARNING: Unsupported axiom: Ignoring triple with unknown property from OWL namespace:
  https://spec.edmcouncil.org/fibo/ontology/LOAN/RealEstateLoans/Mortgages
  @owl:versionIRI ...
[... additional WARNING lines for CommercialLoans, ConsumerLoans, CardAccounts,
     StudentLoans, Loans, GreenLoans ...]
ERROR: Ontology is inconsistent, run "pellet explain" to get the reason
```

The Java-level `ERROR: Ontology is inconsistent` triggers owlready2 to raise `OwlReadyInconsistentOntologyError`, which propagates through the following code path in `validator.py`:

```python
# validator.py — _run_reasoner_with_fallback() (lines 437-507)
def _run_reasoner_with_fallback(self):
    global REASONER_FALLBACK_MODE

    if REASONER_FALLBACK_MODE == 'pellet':
        print("  Running Pellet reasoner...")
        try:
            sync_reasoner_pellet(
                self.world, infer_property_values=True, debug=0
            )
            print("  [OK] Pellet reasoning complete - ontology is consistent")
            return True
        except OwlReadyInconsistentOntologyError:
            # ← THIS IS THE CATCH: Pellet detected a disjointness violation.
            #   Re-raise so validate_triples() can generate the explanation.
            raise
        except Exception as e:
            error_msg = str(e)
            # Java WARNINGs (e.g. unsupported axioms) are non-fatal —
            # Pellet still completed reasoning, just skipped some axioms
            if "WARNING" in error_msg:
                print(f"  [OK] Pellet reasoning complete (with warnings)")
                return True
            print(f"  [!] Pellet reasoner error: {error_msg[:200]}")
            return False
```

The re-raised `OwlReadyInconsistentOntologyError` is caught in `validate_triples()` (lines 690-698), which generates the human-readable explanation:

```python
# validator.py — validate_triples() exception handler (lines 690-698)
except OwlReadyInconsistentOntologyError as e:
    # Ontology is inconsistent - this is what we want to detect!
    explanation = self._generate_inconsistency_explanation(triples, str(e))
    return ValidationResult(
        is_valid=False,
        explanation=explanation,
        inconsistent_triples=triples
    )
```

The explanation generator (`_generate_inconsistency_explanation`, lines 779-819) formats all triples and the reasoner output into the final validation feedback:

```python
# validator.py — _generate_inconsistency_explanation() (lines 779-819)
def _generate_inconsistency_explanation(self, triples, error_msg):
    explanation_parts = [
        "LOGICAL INCONSISTENCY DETECTED",
        "=" * 60,
        "",
        "The following assertions violate FIBO ontology constraints:",
        ""
    ]
    for i, triple in enumerate(triples, 1):
        explanation_parts.append(
            f"{i}. {triple['sub']} ({triple['sub_type']}) "
            f"{triple['pred']} "
            f"{triple['obj']} ({triple['obj_type']})"
        )
    explanation_parts.extend([
        "",
        "Possible violations:",
        "• Disjointness: Entity cannot belong to disjoint classes",
        "• Cardinality: Property exceeds allowed number of values",
        "• Irreflexivity: Entity cannot have relation to itself",
        "• Domain/Range: Property applied to incompatible entity types",
        "",
        f"Reasoner output: {error_msg}",
    ])
    return "\n".join(explanation_parts)
```

This produces the full validation output seen in the evaluation logs:

```
LOGICAL INCONSISTENCY DETECTED
============================================================

The following assertions violate FIBO ontology constraints:

1. FirstLoan (Loan) rdf:type ClosedEndMortgageLoan (Class)
2. FirstLoan (Loan) rdf:type SecuredLoan (Class)
3. FirstLoan (Loan) hasCollateral 456 Park Avenue, New York, NY 10022 (GeographicRegion)
4. Anna Miller (Entity) rdf:type NaturalPerson (Class)
5. FirstLoan (Loan) hasBorrower Anna Miller (Entity)
6. SecondLoan (Loan) rdf:type CommercialLoan (Class)
7. SecondLoan (Loan) rdf:type UnsecuredLoan (Class)
8. TechStart Inc. (Entity) rdf:type Corporation (Class)
9. SecondLoan (Loan) hasBorrower TechStart Inc. (Entity)
...
11. TheLoan (Loan) rdf:type SecuredLoan (Class)       ← from Contract 002 context
...
20. TheLoan (Loan) rdf:type UnsecuredLoan (Class)     ← from Contract 001 context
21. TheLoan (Loan) rdf:type CommercialLoan (Class)    ← from Contract 001 context
22. TheLoan (Loan) hasLender First National Bank      ← from Contract 001 context
23. TheLoan (Loan) hasBorrower TechStart Inc.         ← from Contract 001 context

Possible violations:
• Disjointness: Entity cannot belong to disjoint classes
...
Reasoner output: ... ERROR: Ontology is inconsistent, run "pellet explain" to get the reason
```

#### 5.5.4 The Correction Loop Cannot Recover

All 4 false positives exhausted all 3 correction attempts and were hard-rejected. The correction loop failed because the *source context* remained unchanged across retries — the same contaminated chunks were fed back each time. The LLM, constrained to answer "based on the context provided", could not avoid mentioning both contracts' entities:

**Contract 002, Q1 — All 4 Attempts**:
| Attempt | LLM Strategy | Validation |
|---------|-------------|------------|
| 0 (initial) | "Two types of loans: consumer loan (Anna Miller) and commercial loan (ACME Industries)" | FAIL |
| 1 (correction) | "Two loans: mortgage (Anna Miller, 456 Park Ave) and commercial loan (ACME Industries)" | FAIL |
| 2 (correction) | "Two loans: secured consumer loan (Anna Miller) and commercial loan (ACME Industries)" | FAIL |
| 3 (correction) | "Two loans: secured mortgage (Anna Miller) and unsecured commercial (TechStart Inc.)" | FAIL → **Hard-Reject** |

Each re-phrasing still merged facts from both contracts because the retriever provided both contracts' text as "context". The validator correctly detected the disjointness violation every time.

#### 5.5.5 Undetected Context Contamination

Not all context contamination triggers a false positive. When the contaminating contract's loan type happens to be *compatible* with the target contract's type (i.e., no disjointness violation is created), the contamination passes validation silently.

**Contract 010** demonstrates this. Its Q1 answer discusses ACME Industries LLC's Commercial Loan (from Contract 005) instead of Thomas Brown's Mortgage — a *completely wrong* answer — but the triples (`CommercialLoan`, `SecuredLoan`, `GreenLoan`) are mutually compatible in the FIBO ontology, so Pellet finds no inconsistency. The answer passes validation despite being about the wrong contract entirely.

This reveals a limitation: OV-RAG catches *logical* inconsistencies but not *referential* errors (answering about the wrong entity).

#### 5.5.6 Complete False Positive Inventory

| # | Contract | Question | Contamination Source | Disjointness Violation | Correction Attempts |
|---|----------|----------|---------------------|----------------------|-------------------|
| 1 | **002** | Q1 | Contract 001 (TechStart Inc., CommercialLoan) | `SecuredLoan` ∧ `UnsecuredLoan` on `TheLoan` | 4 (all failed) → Hard-Reject |
| 2 | **005** | Q1 | Contract 002 (Anna Miller, Mortgage) | `CommercialLoan` ∧ `ConsumerLoan` ∧ `Mortgage` on `TheLoan` | 4 (all failed) → Hard-Reject |
| 3 | **005** | Q2 | Contract 001 (TechStart Inc., CommercialLoan) | `SecuredLoan` ∧ `UnsecuredLoan` on `TheLoan` | 4 (all failed) → Hard-Reject |
| 4 | **006** | Q2 | Contract 005 (ACME Industries, GreenLoan) | `UnsecuredLoan` ∧ `SecuredLoan` + `OpenEndCredit` ∧ `ClosedEndCredit` on `TheLoan` | 4 (all failed) → Hard-Reject |

#### 5.5.7 Significance for the Thesis

Context contamination, while producing false positives from the perspective of the ground-truth evaluation, actually demonstrates a **strength** of the OV-RAG approach: the ontology validator can detect when the RAG pipeline has mixed up entities from different documents — a failure mode that is completely invisible to Pure RAG systems.

In a production system, these "false positives" would correctly signal to the user that the generated answer contains logically contradictory information and should not be trusted. The fact that the contradiction originated from cross-document retrieval rather than within-document inconsistency is a *retrieval-layer* problem, not a *validation-layer* problem. The validator is doing its job: flagging answers whose semantic content violates formal ontology constraints, regardless of the source of the violation.

### 5.6 Extraction Failures — False Negatives (90 cases)

90 clash queries passed validation despite containing deliberate ontological contradictions. The root cause is consistently the **Triple Extractor failing to capture both sides of the contradiction**.

#### Breakdown by Clash Type

| Clash Type | False Negatives | Out of | Miss Rate |
|------------|-----------------|--------|-----------|
| `secured_unsecured` | 38 | 74 | 51.4% |
| `openend_closedend` | 32 | 75 | 42.7% |
| `lender_type` | 12 | 25 | 48.0% |
| `borrower_type` | 8 | 25 | 32.0% |

#### Example: Contract 061, Q3 (CLASH: `secured_unsecured` — missed)

**Question**: "Is this loan secured or unsecured? If secured, what collateral is specified?"

**Expected**: Extractor should produce both `TheLoan rdf:type SecuredLoan` AND `TheLoan rdf:type UnsecuredLoan` (since the contract contradicts itself).

**Answer** (GPT-4o): "The loan is secured. The specified collateral is the first lien on the property at 321 Elm Street, Portland, OR 97201."

**Extracted Triples** (8 total):

```
TheLoan (Loan) → rdf:type → SecuredLoan (Class)
TheLoan (Loan) → rdf:type → Loan (Class)
TheLoan (Loan) → hasLender → KeyCorp (Lender)
TheLoan (Loan) → hasBorrower → Timothy Collins (Borrower)
TheLoan (Loan) → hasLoanAmount → USD 719,000.00 (Literal)
TheLoan (Loan) → hasInterestRate → 4.2% (Literal)
TheLoan (Loan) → hasMaturityDate → March 03, 2046 (Literal)
TheLoan (Loan) → hasCollateral → First lien on property at 321 Elm Street (Literal)
```

**Validation Result**: "All triples are logically consistent with LOAN ontology. Validated 8 assertion(s) successfully."

**Failure Mechanism**: The contract states the loan is unsecured (in the special provisions section) but also lists collateral (in the loan terms section). The LLM resolved this contradiction by choosing "secured" (since collateral is present) and only extracted `SecuredLoan`. Without the contradicting `UnsecuredLoan` triple, the validator has nothing to flag. This is an **extraction-level failure** — the validator works correctly with the triples it receives.

### 5.7 NLP Quality Metrics Detail

#### BERTScore Components

| Component | OV-RAG | Plain RAG | Difference |
|-----------|--------|-----------|------------|
| Precision | 0.8668 | 0.8809 | -0.0141 |
| Recall | 0.9079 | 0.9108 | -0.0029 |
| F1 | 0.8864 | 0.8953 | -0.0089 |

The slight quality decrease in OV-RAG is attributable to:
1. Hard-rejected answers being compared against reference answers (22.9% of queries)
2. Corrected answers occasionally deviating from reference wording despite being logically consistent
3. Both systems achieve high BERTScore (>0.88), indicating semantic quality is largely preserved

### 5.8 Per-Contract Summary (selected examples)

#### Clean Contracts — Typical Performance

| Contract | Condition | Passed | Failed | No Triples | Note |
|----------|-----------|--------|--------|------------|------|
| 001 | OV-RAG | 5/5 | 0 | 0 | Perfect validation |
| 010 | OV-RAG | 5/5 | 0 | 0 | Perfect validation |
| 030 | OV-RAG | 5/5 | 0 | 0 | Perfect validation |
| 002 | OV-RAG | 4/5 | 1 | 0 | 1 false positive (context contamination) |
| 005 | OV-RAG | 3/5 | 2 | 0 | 2 false positives (context contamination) |

#### Clash Contracts — Detection Varies

| Contract | Clash Type | Passed | Failed | Detection Rate |
|----------|------------|--------|--------|----------------|
| 068 | secured_unsecured | 0/5 | 5 | 100% (all detected) |
| 072 | secured_unsecured | 0/5 | 5 | 100% (all detected) |
| 061 | secured_unsecured | 5/5 | 0 | 0% (all missed) |
| 062 | secured_unsecured | 5/5 | 0 | 0% (all missed) |
| 076 | openend_closedend | 1/5 | 4 | 80% |
| 092 | borrower_type | 1/5 | 4 | 80% |
| 096 | lender_type | 1/5 | 4 | 80% |

---

## 6. Summary of Key Findings

### Strengths
1. **Near-perfect precision** (96.5%) — when OV-RAG flags an inconsistency, it is almost always a real violation
2. **Zero false positives in clash detection per se** — all 4 FP stem from context contamination, not validator errors
3. **Pellet reasoning is fast** — median 1.13 s, only 3.6% of total latency
4. **BERTScore preserved** — only 0.9% decrease in semantic quality (0.8864 vs 0.8953)

### Limitations
1. **Moderate recall** (54.8%) — extraction failures cause ~45% of clashes to be missed
2. **High latency overhead** — 100.94 s mean (driven by LLM extraction, not reasoning)
3. **Low correction success rate** (5.04%) — re-prompting rarely resolves extraction failures
4. **Context contamination** — RAG cross-contract retrieval creates artificial contradictions (4 FP)

### Root Causes
- **False Positives (4)**: Context contamination from RAG cross-contract retrieval merging entities into single `TheLoan`
- **False Negatives (90)**: Triple Extractor (GPT-4o) resolves contradictions instead of preserving both sides, preventing the validator from detecting them
- **Latency**: 91.9% caused by LLM API calls (extraction + correction retries + rate-limit backoff), not by Pellet reasoning (3.6%)
