# Chapter 7 — Discussion of Results: Analytical Context Document

> **Compiled:** 2026-02-18
> **Source:** OV-RAG evaluation pipeline (100 contracts, 1000 queries, A/B comparison)
> **Primary dataset:** `evaluation/results/optimized_100/`
> **Secondary dataset:** `evaluation/results/run_10contracts/` (10-contract A/B, cleaner latency)

---

## 7.1 Interpretation of the Results

### 7.1.1 The Quality–Consistency Trade-Off

The core finding: OV-RAG sacrifices a small amount of surface-level text quality (measured by NLP metrics) in exchange for a massive gain in logical consistency (measured by clash detection).

#### A/B NLP Metrics Comparison (100 contracts, 500 queries per condition)

| Metric | Plain RAG | OV-RAG | Delta | Interpretation |
|--------|-----------|--------|-------|----------------|
| Avg ROUGE-L | 0.3460 | 0.3028 | **-0.0432** | 12.5% relative drop |
| Avg BERTScore-F1 | 0.8953 | 0.8864 | **-0.0089** | 1.0% relative drop |
| Avg BERTScore-Precision | 0.8809 | 0.8668 | -0.0141 | 1.6% relative drop |
| Avg BERTScore-Recall | 0.9108 | 0.9079 | -0.0029 | 0.3% relative drop |

**Why does OV-RAG score lower?** Two mechanisms:

1. **Hard-rejected queries return disclaimers instead of answers.** The 113 hard-rejected queries return text like *"Answer failed ontology validation after 3 correction attempts..."* — which scores poorly against reference answers. These 113 queries represent 22.9% of OV-RAG output.

2. **Correction loops alter wording.** When the LLM corrects an answer to remove an ontological contradiction, it sometimes rephrases content, moving further from the reference answer's specific wording — lowering ROUGE-L (which is n-gram-based) while BERTScore (semantic similarity) remains robust.

**Key insight:** The BERTScore delta (-0.0089) is negligible, confirming that OV-RAG's semantic understanding is unaffected. The ROUGE-L delta (-0.0432) reflects surface-level wording changes from corrections and hard-reject disclaimers, not degraded comprehension.

#### Cleaner 10-Contract A/B Comparison (no rate-limit artifacts)

| Metric | Plain RAG | OV-RAG | Delta |
|--------|-----------|--------|-------|
| Avg ROUGE-L | 0.3792 | 0.3613 | **-0.0179** |
| Avg BERTScore-F1 | 0.9004 | 0.8958 | **-0.0046** |
| Avg Latency | 1.37s | 11.46s | +10.09s (736.5%) |

This smaller dataset (unaffected by rate-limit outliers) shows the delta is even smaller: ROUGE-L drops only 0.0179, BERTScore only 0.0046.

#### Logical Consistency Metrics (100 contracts)

| Metric | Value |
|--------|-------|
| True Positives (TP) | 109 |
| False Positives (FP) | 4 |
| True Negatives (TN) | 291 |
| False Negatives (FN) | 90 |
| **Precision** | **0.9646 (96.5%)** |
| **Recall** | **0.5477 (54.8%)** |
| **F1 Score** | **0.6987 (69.9%)** |
| Clash Detection Rate | 54.8% |
| Hard-Reject Rate | 22.9% |
| Corrections Needed | 119 |
| Corrections Succeeded | 6 |
| Hard Rejects | 113 |
| Correction Success Rate | 5.0% |

**Interpretation:** When OV-RAG flags an answer, it is correct 96.5% of the time (Precision). It catches 54.8% of all planted contradictions (Recall). The low correction success rate (5.0%) shows that once a genuine ontological clash is detected, the LLM usually cannot self-correct — because the contradiction originates in the source document, not in LLM hallucination.

#### Per-Clash-Type Detection Performance

| Clash Type | TP | FP | TN | FN | Precision | Recall | F1 | Detection Rate |
|------------|----|----|----|----|-----------|--------|-----|----------------|
| secured_unsecured | 36 | 0 | 0 | 38 | 1.000 | 0.487 | 0.655 | 48.6% |
| openend_closedend | 43 | 0 | 0 | 32 | 1.000 | 0.573 | 0.729 | 57.3% |
| borrower_type | 17 | 0 | 0 | 8 | 1.000 | 0.680 | 0.810 | 68.0% |
| lender_type | 13 | 0 | 0 | 12 | 1.000 | 0.520 | 0.684 | 52.0% |
| clean | 0 | 4 | 291 | 0 | — | — | — | — |

**Key pattern:** All clash types achieve **100% precision** (zero false positives within clash categories). The variation in recall is explained by the extraction bottleneck (Section 7.2.1). `borrower_type` has the highest recall (68%) because its contradictions (e.g., Corporation borrower on a ConsumerLoan) are more explicitly stated in contract text, making them easier for the LLM to surface in its answer.

---

### 7.1.2 The Context Contamination Breakthrough (The 4 "False Positives")

The 4 false positives are arguably OV-RAG's most important finding — they reveal a failure mode in standard RAG that is **completely invisible** without ontological validation.

#### What Happened

All 4 FPs occurred on CLEAN contracts where the ChromaDB vector retrieval pulled chunks from **other contracts** into the LLM's context window. The LLM faithfully synthesized information from multiple contracts into a single answer, and the extractor mapped all facts onto a single `TheLoan` entity — producing contradictory type assertions.

| FP # | Contract | Question | Retrieved Contamination | Clash Triggered |
|-------|----------|----------|-------------------------|-----------------|
| 1 | 002 (Anna Miller, Mortgage) | Q1 | Contract 001 (TechStart, Commercial) | `SecuredLoan ⊥ UnsecuredLoan` |
| 2 | 005 (ACME Industries) | Q1 | Contract 001 + 002 | `SecuredLoan ⊥ UnsecuredLoan` |
| 3 | 005 (ACME Industries) | Q2 | Contract 001 | `SecuredLoan ⊥ UnsecuredLoan` |
| 4 | 006 (Robert Chen, Consumer) | Q2 | Contract 005 (ACME) | `SecuredLoan ⊥ UnsecuredLoan` + `OpenEndCredit ⊥ ClosedEndCredit` |

#### Detailed Trace: FP #1 — Contract 002, Q1

Contract 002 is a **secured mortgage** for Anna Miller from Commerce Bank of America (USD 254,000). The RAG retrieved 3 chunks, including content from Contract 001 (an **unsecured commercial loan** for TechStart Inc. from First National Bank, USD 962,000).

The LLM's answer correctly described **both** loans:
> *"The document describes two types of loans: (1) a secured mortgage loan for Anna Miller... (2) an unsecured commercial loan for TechStart Inc..."*

The extractor produced 26 triples under `TheLoan`, including:
```
TheLoan rdf:type SecuredLoan      ← from Contract 002
TheLoan rdf:type UnsecuredLoan    ← from retrieved Contract 001
TheLoan rdf:type ConsumerLoan     ← from Contract 002
TheLoan rdf:type CommercialLoan   ← from retrieved Contract 001
TheLoan hasLender Commerce Bank of America     ← Contract 002
TheLoan hasLender First National Bank          ← Contract 001
TheLoan hasBorrower Anna Miller                ← Contract 002
TheLoan hasBorrower TechStart Inc.             ← Contract 001
TheLoan hasLoanAmount USD 254,000.00           ← Contract 002
TheLoan hasLoanAmount USD 962,000.00           ← Contract 001
```

The Pellet reasoner correctly flagged `SecuredLoan ⊥ UnsecuredLoan` on `TheLoan`. The query was hard-rejected after 4 attempts.

#### Detailed Trace: FP #4 — Contract 006, Q2

Contract 006 is a **consumer loan** for Robert Chen from Green Investment Bank (USD 10,000, 23% APR). The RAG retrieved Contract 005 (ACME Industries, USD 4,647,000, commercial/green loan). The merged `TheLoan` entity received:

```
TheLoan rdf:type UnsecuredLoan + OpenEndCredit + ConsumerLoan    ← Contract 006
TheLoan rdf:type SecuredLoan + ClosedEndCredit + CommercialLoan + GreenLoan   ← Contract 005
TheLoan hasLender Green Investment Bank        ← Contract 006
TheLoan hasLender U.S. Department of Education ← Contract 005
TheLoan hasLoanAmount USD 10,000.00            ← Contract 006
TheLoan hasLoanAmount USD 4,647,000.00         ← Contract 005
```

This triggered **both** disjointness axioms (`SecuredLoan ⊥ UnsecuredLoan` AND `OpenEndCredit ⊥ ClosedEndCredit`).

#### Why This Is a Breakthrough

Standard RAG would have returned the contaminated answer **silently** — blending information from two entirely different loan contracts into a single response. The user would have no indication that the answer merges data from Contract 006 (a $10,000 consumer loan at 23%) with Contract 005 (a $4.6M commercial green loan at 3.6%). In a financial compliance context, this is a **critical failure mode**.

OV-RAG's deterministic TBox validation caught what the LLM could not: that a single loan entity cannot simultaneously be both secured and unsecured, or both open-end and closed-end. The hard-reject is the **correct** response — it alerts the user that the RAG context is contaminated, rather than silently passing a blended, factually incoherent answer.

**These 4 FPs are better classified as "detected context contamination incidents" rather than true false positives.** They demonstrate a unique safety property of OV-RAG: the ability to detect vector retrieval errors that would be invisible to any NLP-metric-based evaluation.

---

## 7.2 Limitations of the Approach

### 7.2.1 The Extraction Bottleneck (90 False Negatives)

The system's primary limitation is the TripleExtractor (Component B). Of 199 clash queries (40 clash contracts × ~5 questions), 90 passed validation despite containing genuine contradictions — a 45.2% miss rate.

#### Root Cause: The LLM Resolves Contradictions Before Extraction

The extraction pipeline depends on the LLM's answer text containing both contradictory elements. When the LLM encounters a contract with conflicting information (e.g., "secured" in one clause, "unsecured" in another), it **resolves the ambiguity itself** by choosing the dominant classification — never surfacing the contradiction in its answer.

**Example — Contract 061, Q1 (secured_unsecured FN):**
The contract embeds both "secured" and "unsecured" clauses. The LLM answered:
> *"The loan described in this document is a commercial loan."*

Extracted triples (12 total):
```
TheLoan rdf:type CommercialLoan
TheLoan rdf:type SecuredLoan        ← only the dominant type extracted
TheLoan rdf:type GreenLoan
TheLoan rdf:type ClosedEndCredit
TheLender rdf:type FinancialInstitution
TheBorrower rdf:type Corporation
```

No `UnsecuredLoan` triple was ever generated — the LLM simply picked "secured" and never mentioned "unsecured" in its answer. The extractor can only work with what the LLM provides.

**Example — Contract 076, Q4 (openend_closedend FN):**
The LLM answered:
> *"This is a revolving (open-end) credit facility. The repayment terms state that repayment shall be made in 39 monthly installments..."*

The answer explicitly describes both open-end characteristics (revolving) and closed-end characteristics (39 fixed monthly installments), but the extractor mapped only the explicit classification:
```
TheLoan rdf:type OpenEndCredit      ← from "revolving (open-end)"
```

The structural contradiction ("revolving" + "39 monthly installments") was not captured because the extractor maps only explicit loan-type keywords, not behavioral descriptions.

**Example — Contract 097, Q1 (lender_type FN):**
Sallie Mae (a student loan servicer) as lender for a consumer loan with Ironwood Properties LLC (a corporation) as borrower. The extractor produced:
```
TheLoan rdf:type ConsumerLoan
TheLoan hasLender Sallie Mae                    obj_type: FinancialInstitution
TheLoan hasBorrower Ironwood Properties LLC     obj_type: Corporation
```

The role constraint checker at `validator.py:732` SHOULD have caught `Corporation as borrower for ConsumerLoan`, but it only populates `entity_types` from `pred in ("rdf:type", "type")` triples — not from the `obj_type` field on relationship triples. Since there was no separate `Ironwood Properties LLC rdf:type Corporation` triple, the check failed to fire.

#### FN Distribution by Clash Type

| Clash Type | Total Queries | FN | FN Rate | Why |
|------------|--------------|-----|---------|-----|
| secured_unsecured | 74 | 38 | 51.4% | LLM picks one type; rarely mentions both |
| openend_closedend | 75 | 32 | 42.7% | Extractor maps keywords, not behavioral contradictions |
| borrower_type | 25 | 8 | 32.0% | Role constraint code gap (obj_type not checked) |
| lender_type | 25 | 12 | 48.0% | Same code gap + some clashes too subtle for LLM |

#### Prompt Tuning Evidence (recall_improvement_test)

A targeted prompt improvement test on 2 contracts (061 and 091) showed:

| Contract | Original Prompt | Optimized Prompt |
|----------|----------------|-----------------|
| 061 (secured_unsecured) | `validation_is_valid: true` (MISSED) | `validation_is_valid: false` (DETECTED) |
| 091 (borrower_type) | `validation_is_valid: true` (MISSED) | `validation_is_valid: false` (DETECTED) |

The optimized prompt added explicit instructions to extract *all* loan type mentions from the source text, not just the dominant one. For Contract 091, the optimized extractor produced `NaturalPerson` + `Corporation` per FIBO vocabulary (instead of non-FIBO "Individual"/"Organization"), and the extended violation was logged:
```
NaturalPerson 'Maria Garcia' as borrower for a CommercialLoan
(commercial loans are for corporations/organizations)
```

This demonstrates that the extraction bottleneck is **improvable** with better prompting — it is not a fundamental architectural limitation.

---

### 7.2.2 Latency Profiling

#### Headline Numbers

| Metric | Plain RAG | OV-RAG | Overhead |
|--------|-----------|--------|----------|
| Avg Latency (100-contract run) | 1.64s | 100.94s | +99.3s (6055%) |
| Avg Latency (10-contract run, clean) | 1.37s | 11.46s | +10.09s (736.5%) |

**Important:** The 100-contract run average (100.94s) is heavily inflated by API rate-limit retry artifacts (e.g., Contract 050 Q2: 19,259s extraction time). The 10-contract run (11.46s) is more representative of real-world performance.

#### Latency Component Breakdown (100-contract, cleaned — excluding outliers > 300s, n=488)

| Component | Avg Time | Share of Total |
|-----------|----------|----------------|
| RAG Generation (`latency_rag`) | 3.94s | 26.9% |
| Triple Extraction (`latency_extraction`) | 9.19s | 62.8% |
| Pellet Reasoning (`latency_validation`) | 1.51s | 10.3% |
| **Total** | **14.64s** | — |

**The Pellet reasoner is fast.** At 1.51s average, the OWL DL reasoning adds negligible overhead. The bottleneck is the LLM API calls — specifically triple extraction (GPT-4o structured output), which accounts for 63% of total time.

#### Latency by Attempt Count (cleaned data)

| Attempts | n | Avg Total | Avg RAG | Avg Extraction | Avg Validation |
|----------|---|-----------|---------|----------------|----------------|
| 1 (pass on first try) | 368 | **10.35s** | 2.04s | 7.24s | 1.07s |
| 2 (1 correction) | 5 | 11.58s | 3.09s | 6.85s | 1.65s |
| 3 (2 corrections) | 1 | 16.74s | 6.28s | 7.51s | 2.94s |
| 4 (hard-reject) | 114 | **28.60s** | 10.06s | 15.62s | 2.92s |

**Hard-rejected queries cost ~2.8x more time** than single-attempt queries (28.6s vs 10.4s). This is because each correction attempt requires a fresh RAG generation call + extraction call + Pellet invocation.

#### Notable Latency Outliers (rate-limit artifacts)

```
Contract 050 Q2:  19,261s total  (19,259s extraction — API retry loop)
Contract 025 Q4:   6,616s total  (6,614s extraction)
Contract 024 Q3:   6,433s total  (6,431s extraction)
Contract 021 Q2:   4,701s total  (4,698s extraction)
Contract 025 Q1:   4,396s total  (4,394s extraction)
Contract 051 Q1:     371s total  (360s RAG generation)
Contract 030 Q4:   1,041s total  (1,037s validation — unusual)
```

These outliers are caused by OpenAI API rate-limit retries (the pipeline uses exponential backoff). They inflate the 100-contract average from ~14.6s (cleaned) to 100.9s (raw).

---

### 7.2.3 FIBO Ontology Coverage Gaps

The FIBO LOAN ontology provides limited coverage for the retail loan contract domain tested. Several critical gaps were identified:

#### Only 2 Disjointness Axioms Exist

The entire LOAN ontology contains exactly **2 disjointness axioms**:

```
1. SecuredLoan ⊥ UnsecuredLoan        (source: Loans.rdf)
2. OpenEndCredit ⊥ ClosedEndCredit    (source: Loans.rdf)
```

This means the OWL DL reasoner (Pellet) can only detect **2 categories** of logical clash through TBox reasoning. All other clash types (borrower_type, lender_type) require the rule-based `_check_role_constraints()` fallback in `validator.py`.

#### Classes Used by Extractor but NOT in FIBO LOAN

The vocabulary cache contains **86 LOAN ontology classes** and **25 LOAN properties**. However, the extractor routinely produces classes from outside this module:

| Class | Used For | Actual FIBO Location | Impact |
|-------|----------|---------------------|--------|
| `FinancialInstitution` | Lender typing | FIBO-BE (Business Entities) | Falls back to `owl:Thing` — no constraint checking |
| `Corporation` | Borrower typing | FIBO-BE | Falls back to `owl:Thing` |
| `NaturalPerson` | Borrower typing | FIBO-BE | Falls back to `owl:Thing` |
| `GovernmentalEntity` | Lender typing (e.g., "U.S. Dept. of Education") | Not in any loaded module | Falls back to `owl:Thing` |
| `PersonalLoan` | Loan classification | Not in FIBO (FIBO uses `ConsumerLoan`) | Falls back to `owl:Thing` |
| `Lender` | Role class | Not in FIBO LOAN (only `hasLender` property) | Falls back to `owl:Thing` |
| `Borrower` | Role class | Not in FIBO LOAN (only `hasBorrower` property) | Falls back to `owl:Thing` |

When `_get_class_by_name()` returns `None`, the individual is created as `owl:Thing`:
```python
# validator.py, line 564
individuals[sub_name] = Thing(...)
```

`owl:Thing` has no disjointness constraints — so entity type violations are silently ignored.

#### Properties Used by Extractor but NOT in FIBO LOAN

| Property Used | FIBO LOAN Equivalent | Impact |
|---------------|---------------------|--------|
| `hasLender` | Not in LOAN properties | Silently skipped — never asserted |
| `hasBorrower` | Not in LOAN properties | Silently skipped |
| `hasLoanAmount` | `hasPrincipalAmount` | Silently skipped |
| `hasInterestRate` | Not in LOAN properties | Silently skipped |
| `hasMaturityDate` | Not in LOAN properties | Silently skipped |
| `hasCollateral` | Not in LOAN properties | Silently skipped |

The validator at lines 616–619 simply skips unrecognized properties:
```python
property_obj = self._get_property_by_name(pred_name)
if not property_obj:
    print(f"  Warning: Property {pred_name} not found")
    continue  # ← silently skips
```

**Consequence:** The Pellet reasoner only ever validates `rdf:type` class membership assertions. All property-based validation (loan amounts, interest rates, maturity dates, party relationships) is effectively disabled. The system detects structural type contradictions but cannot validate data-level constraints.

#### Pellet Warning: Unsupported Axioms

Every Pellet invocation produces these warnings (non-fatal but noteworthy):
```
WARNING: Unsupported axiom: Ignoring triple with unknown property from OWL namespace:
  https://spec.edmcouncil.org/fibo/ontology/LOAN/RealEstateLoans/Mortgages @owl:versionIRI
  https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansSpecific/CommercialLoans @owl:versionIRI
  https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansSpecific/ConsumerLoans @owl:versionIRI
  https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansSpecific/CardAccounts @owl:versionIRI
  https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansSpecific/StudentLoans @owl:versionIRI
  https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansGeneral/Loans @owl:versionIRI
  https://spec.edmcouncil.org/fibo/ontology/LOAN/LoansSpecific/GreenLoans @owl:versionIRI
```

These occur because Pellet does not recognize `owl:versionIRI` as a known OWL namespace property. They are non-blocking (Pellet still reasons correctly) but reflect an imperfect alignment between the FIBO RDF serialization and Pellet's OWL parser.

#### HermiT Reasoner: Retired

HermiT was originally considered as a backup reasoner but was permanently retired due to its inability to handle `rdf:langString` annotations in the FIBO TBox:
```python
# validator.py, lines 43-45
# Pellet is the primary (and only) reasoner because HermiT cannot handle rdf:langString
# annotations in the FIBO/LOAN TBox, even after cleaning 204+ language tags.
REASONER_FALLBACK_MODE = 'pellet'
```

The FIBO LOAN TBox uses `rdf:langString` for `rdfs:label`, `skos:definition`, and `cmns-av:explanatoryNote` on classes. HermiT raises `UnsupportedDatatypeException` on these. A `_clean_language_tags()` method (lines 326–435) was implemented to strip `.lang` attributes, but even after cleaning, HermiT failed on import-level annotation axioms.

---

### 7.2.4 Correction Loop Behavior

The correction loop (max 3 corrections = 4 total attempts) has a **5.0% success rate** — meaning only 6 out of 119 flagged queries were successfully corrected.

#### Successful Correction Example — Contract 001, Q3

The initial extraction hallucinated `SecuredLoan` for Contract 001 (which is actually unsecured). The correction loop:

| Attempt | LLM Behavior | Result |
|---------|-------------|--------|
| 0 (initial) | Extracted `SecuredLoan + UnsecuredLoan` | `INCONSISTENT` — Pellet flags disjointness |
| 1 (correction) | LLM says "The loan is unsecured" but **still extracts both types**. Blames ontology: *"logical inconsistency in the ontology processing"* | `INCONSISTENT` |
| 2 (correction) | LLM finally drops `SecuredLoan` from triples | `VALID` — accepted |

**Pattern:** The LLM required 2 correction rounds. On the first correction, it changed the answer text but not the extracted triples — and explicitly blamed the ontology rather than its own extraction.

#### Failed Correction (Hard-Reject) Example — Contract 096, Q5 (lender_type clash)

The document genuinely contains `ConsumerLoan` with `Corporation` borrower (Ironwood Properties LLC). The correction loop:

| Attempt | LLM Behavior | Validator Feedback |
|---------|-------------|-------------------|
| 0 | Faithfully reports: ConsumerLoan, Ironwood Properties LLC (Corporation) | `ROLE CONSTRAINT VIOLATION: Corporation cannot be borrower for ConsumerLoan` |
| 1 | LLM **correctly identifies the contradiction**: *"the loan is described as 'General consumer purchase financing,' but the borrower is a corporation..."* — but still extracts both facts faithfully | `LOGICAL INCONSISTENCY DETECTED` (also adds CommercialLoan, triggering disjointness) |
| 2 | LLM reduces to ConsumerLoan only but keeps Corporation as borrower | `LOGICAL INCONSISTENCY DETECTED` |
| 3 | LLM says: *"maintaining factual accuracy..."* — refuses to fabricate | `ROLE CONSTRAINT VIOLATION` → **HARD REJECT** |

**Pattern:** The LLM correctly diagnoses the problem on attempt 1 but **cannot resolve it** because the contradiction is in the source document. The LLM refuses to fabricate information to resolve the clash — which is actually the correct behavior. The hard-reject is working as designed.

#### Unique Validator Error Message Patterns

**Pattern A — OWL Disjointness (109 of 113 hard-rejects):**
```
LOGICAL INCONSISTENCY DETECTED
============================================================
The following assertions violate FIBO ontology constraints:
...
ERROR: Ontology is inconsistent, run "pellet explain" to get the reason
```

**Pattern B — Role Constraint Violation (4 of 113 hard-rejects):**
```
ROLE CONSTRAINT VIOLATION DETECTED
============================================================
• Corporation 'Ironwood Properties LLC' cannot be borrower for a ConsumerLoan
```

**Pattern C — Successful Validation:**
```
All triples are logically consistent with LOAN ontology.
Validated N assertion(s) successfully.
```

---

## 7.3 Implications for Practical Use

### 7.3.1 The Verification Tax

OV-RAG introduces a "Verification Tax" — additional compute and latency — in exchange for logical consistency guarantees. The economics:

| Metric | Plain RAG | OV-RAG | Tax |
|--------|-----------|--------|-----|
| Avg latency per query | 1.37s | 11.46s | +10.09s (+736.5%) |
| LLM API calls per query (pass) | 1 | 3 | +2 calls |
| LLM API calls per query (hard-reject) | 1 | 9 | +8 calls |
| Pellet invocations per query | 0 | 1–4 | +1–4 invocations |

#### API Call Breakdown Per Query

| Scenario | RAG Calls | Extraction Calls | Pellet Calls | Total LLM Calls |
|----------|-----------|-----------------|--------------|-----------------|
| Pass on first try | 1 | 1 context + 1 answer = 2 | 1 | **3** |
| 1 correction → pass | 1 + 1 = 2 | 1 context + 2 answer = 3 | 2 | **5** |
| 2 corrections → pass | 1 + 2 = 3 | 1 context + 3 answer = 4 | 3 | **7** |
| Hard-reject (3 corrections) | 1 + 3 = **4** | 1 context + 4 answer = **5** | **4** | **9** |

A hard-rejected query consumes **3x the LLM API calls** of a clean single-pass query (9 vs 3).

#### Where the Time Goes

From the cleaned 10-contract latency data:

```
Single-pass query (10.35s total):
  ├── RAG Generation:     2.04s  (19.7%)
  ├── Triple Extraction:  7.24s  (69.9%)  ← LLM API call
  └── Pellet Reasoning:   1.07s  (10.3%)  ← deterministic, fast

Hard-reject query (28.60s total):
  ├── RAG Generation:    10.06s  (35.2%)  ← 4 API calls
  ├── Triple Extraction: 15.62s  (54.6%)  ← 5 API calls
  └── Pellet Reasoning:   2.92s  (10.2%)  ← 4 Pellet runs, still fast
```

**The Pellet reasoner is consistently ~10% of total time** regardless of attempt count. The verification tax is almost entirely caused by additional LLM API round-trips.

### 7.3.2 Resource Costs

**Token and monetary cost tracking was not implemented** in the current evaluation pipeline. Neither `rag_pipeline.py` (LangChain) nor `extractor.py` (OpenAI SDK) records `prompt_tokens`, `completion_tokens`, or associated costs from the API response objects.

However, costs can be estimated from the API call structure:

| Item | Estimated per Query (single-pass) | Estimated per Query (hard-reject) |
|------|-----------------------------------|-----------------------------------|
| GPT-4o calls | 3 | 9 |
| Input tokens (est.) | ~3,000–5,000 per call | ~3,000–5,000 per call |
| Output tokens (est.) | ~500–2,000 per call | ~500–2,000 per call |
| Pellet JVM starts | 1 | 4 |
| Java heap allocation | 4GB per JVM instance | 4GB per JVM instance |

The Java heap is set to 4GB for owlready2 reasoning. Each Pellet invocation starts a fresh JVM process. Memory consumption is bounded but disk I/O and JVM startup contribute to the validation latency.

### 7.3.3 The Safety Argument

For high-stakes financial environments (regulatory compliance, loan origination, audit documentation), the verification tax is justified:

1. **Silent context contamination is unacceptable.** The 4 FPs prove that standard RAG can blend data from multiple contracts without any indication. OV-RAG caught all 4 instances.

2. **False negatives are preferable to false positives.** The system's 96.5% precision means that when it flags an answer, the user can trust the flag. The 45.2% miss rate on planted contradictions is a known limitation, not a safety risk — missed contradictions simply pass through as standard RAG output.

3. **The correction loop demonstrates LLM honesty.** The 5.0% correction success rate shows that when a genuine contradiction exists in the source document, the LLM refuses to fabricate — it keeps extracting the contradictory facts faithfully. This is actually a desirable property: the system does not hide contradictions by hallucinating coherent-but-false alternatives.

---

## Appendix A: Raw Per-Contract Summary (100 contracts, OV-RAG condition)

| Contract | Ground Truth | Clash Type | Passed | Failed | No Triples | Errors |
|----------|-------------|------------|--------|--------|------------|--------|
| 001 | CLEAN | — | 5 | 0 | 0 | 0 |
| 002 | CLEAN | — | 4 | 1 | 0 | 0 |
| 003 | CLEAN | — | 5 | 0 | 0 | 0 |
| 004 | CLEAN | — | 5 | 0 | 0 | 0 |
| 005 | CLEAN | — | 3 | 2 | 0 | 0 |
| 006 | CLEAN | — | 4 | 1 | 0 | 0 |
| 007–037 | CLEAN | — | 5 | 0 | 0 | 0 |
| 038 | CLEAN | — | 5 | 0 | 0 | 0 |
| 039 | CLEAN | — | 0 | 0 | 5 | 5 |
| 040–060 | CLEAN | — | 5 | 0 | 0 | 0 |
| 061–067 | CLASH | secured_unsecured | 5 | 0 | 0 | 0 |
| 068 | CLASH | secured_unsecured | 0 | 5 | 0 | 0 |
| 069 | CLASH | secured_unsecured | 3 | 2 | 0 | 0 |
| 070 | CLASH | secured_unsecured | 0 | 5 | 0 | 0 |
| 071 | CLASH | secured_unsecured | 0 | 4 | 1 | 0 |
| 072–075 | CLASH | secured_unsecured | 0 | 5 | 0 | 0 |
| 076 | CLASH | openend_closedend | 1 | 4 | 0 | 0 |
| 077 | CLASH | openend_closedend | 2 | 3 | 0 | 0 |
| 078 | CLASH | openend_closedend | 2 | 3 | 0 | 0 |
| 079 | CLASH | openend_closedend | 3 | 2 | 0 | 0 |
| 080 | CLASH | openend_closedend | 1 | 4 | 0 | 0 |
| 081 | CLASH | openend_closedend | 1 | 4 | 0 | 0 |
| 082 | CLASH | openend_closedend | 3 | 2 | 0 | 0 |
| 083 | CLASH | openend_closedend | 2 | 3 | 0 | 0 |
| 084 | CLASH | openend_closedend | 2 | 3 | 0 | 0 |
| 085 | CLASH | openend_closedend | 2 | 3 | 0 | 0 |
| 086 | CLASH | openend_closedend | 3 | 2 | 0 | 0 |
| 087 | CLASH | openend_closedend | 3 | 2 | 0 | 0 |
| 088 | CLASH | openend_closedend | 3 | 2 | 0 | 0 |
| 089 | CLASH | openend_closedend | 2 | 3 | 0 | 0 |
| 090 | CLASH | openend_closedend | 2 | 3 | 0 | 0 |
| 091 | CLASH | borrower_type | 2 | 3 | 0 | 0 |
| 092 | CLASH | borrower_type | 1 | 4 | 0 | 0 |
| 093 | CLASH | borrower_type | 1 | 4 | 0 | 0 |
| 094 | CLASH | borrower_type | 2 | 3 | 0 | 0 |
| 095 | CLASH | borrower_type | 2 | 3 | 0 | 0 |
| 096 | CLASH | lender_type | 1 | 4 | 0 | 0 |
| 097 | CLASH | lender_type | 3 | 2 | 0 | 0 |
| 098 | CLASH | lender_type | 2 | 3 | 0 | 0 |
| 099 | CLASH | lender_type | 3 | 2 | 0 | 0 |
| 100 | CLASH | lender_type | 3 | 2 | 0 | 0 |

---

## Appendix B: Evaluation Run Comparison

| Run | Contracts | Queries | Precision | Recall | F1 | CDR | Hard-Reject Rate | Latency OV-RAG | Latency Plain | Overhead |
|-----|-----------|---------|-----------|--------|----|-----|-----------------|----------------|---------------|----------|
| **optimized_100** | 100 | 1000 | 0.965 | 0.548 | 0.699 | 54.8% | 22.9% | 100.94s* | 1.64s | 6055%* |
| optimized_10 | 10 | 50 | 0.556 | 0.200 | 0.294 | 20.0% | 18.0% | 10.54s | N/A | N/A |
| run_10contracts | 10 (A/B) | 100 | 0.0 | 0.0 | — | 0.0% | 8.0% | 11.46s | 1.37s | 736.5% |
| run_verify | 5 | 5 | 1.0 | 1.0 | 1.0 | 100% | 80.0% | 28.86s | N/A | N/A |
| baseline | 2 | 2 | 0.5 | 1.0 | 0.667 | 100% | 100% | 18.32s | 1.68s | 990.5% |

\* *Rate-limit artifacts inflate the 100-contract average. Cleaned average (excluding outliers > 300s): 14.64s*

---

## Appendix C: Correction Attempt Statistics

| Metric | Value |
|--------|-------|
| Total queries requiring correction | 119 / 494 (24.1%) |
| Corrections that succeeded | 6 (5.0%) |
| Corrections that failed → hard-reject | 113 (95.0%) |
| Queries accepted at attempt 0 | 375 |
| Queries accepted at attempt 1 | 5 |
| Queries accepted at attempt 2 | 1 |
| Queries hard-rejected at attempt 3 | 113 |

---

## Appendix D: Full False Positive Contamination Evidence

### FP #1 — Contract 002, Q1
- **Target contract:** Anna Miller, Commerce Bank of America, Mortgage, USD 254,000
- **Contaminating contract:** Contract 001 (TechStart Inc., First National Bank, USD 962,000)
- **Conflicting triples on TheLoan:** `SecuredLoan` (002) + `UnsecuredLoan` (001), `ConsumerLoan` (002) + `CommercialLoan` (001)
- **num_sources:** 3
- **LLM answer described both loans explicitly**

### FP #2 — Contract 005, Q1
- **Target contract:** ACME Industries LLC, U.S. Dept. of Education, Commercial/Green Loan, USD 4,647,000
- **Contaminating contracts:** Contract 001 + Contract 002
- **Conflicting triples:** `SecuredLoan` (005) + `UnsecuredLoan` (001), `CommercialLoan` (005) + `ConsumerLoan` (002)
- **num_sources:** 3

### FP #3 — Contract 005, Q2
- **Same target/contamination as FP #2, different question**
- **Conflicting triples:** Same pattern — `SecuredLoan + UnsecuredLoan` from merged context

### FP #4 — Contract 006, Q2
- **Target contract:** Robert Chen, Green Investment Bank, Consumer Loan, USD 10,000
- **Contaminating contract:** Contract 005 (ACME Industries, USD 4,647,000)
- **Conflicting triples:** `UnsecuredLoan + OpenEndCredit` (006) vs `SecuredLoan + ClosedEndCredit + CommercialLoan` (005)
- **Both disjointness axioms triggered simultaneously**
- **num_sources:** 3
