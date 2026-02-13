# Phase 1: Entwicklungsplan - PDF-Generierung & RDF-Vokabular-Scanner

## Übersicht
Diese Phase legt das Fundament für das automatische Ontologie-Mapping und erstellt die Testdaten für die Benchmark-Engine.

---

## Sprint 1.1: RDF-Vokabular-Scanner

### Ziel
Automatisches Extrahieren aller Klassen und Properties aus den LOAN-Ontologie-Dateien, um den Extractor-Prompt dynamisch zu generieren.

### Aufgaben

#### 1.1.1 Datei `vocabulary_scanner.py` erstellen
```python
# Funktionen:
- scan_ontology_directory(path: str) -> dict
- extract_classes(rdf_content) -> List[OntologyClass]
- extract_properties(rdf_content) -> List[OntologyProperty]
- generate_extractor_prompt(vocabulary: dict) -> str
- cache_vocabulary(vocabulary: dict, path: str)
```

**Akzeptanzkriterien:**
- [ ] Scannt alle `.rdf` Dateien in `ontologies/` rekursiv
- [ ] Extrahiert `owl:Class` Definitionen mit Labels und Kommentaren
- [ ] Extrahiert `owl:ObjectProperty` und `owl:DatatypeProperty`
- [ ] Speichert Ergebnis als `vocabulary_cache.json`
- [ ] Generiert dynamischen Prompt für `extractor.py`

#### 1.1.2 Test `test_vocabulary_scanner.py` erstellen
**Testfälle:**
- [ ] Scanner findet alle 7 RDF-Dateien
- [ ] Klassen wie `Loan`, `CommercialLoan`, `Mortgage` werden erkannt
- [ ] Properties wie `hasLender`, `hasBorrower` werden erkannt
- [ ] Cache-Datei wird korrekt geschrieben und gelesen
- [ ] Generierter Prompt enthält alle wichtigen Konzepte

#### 1.1.3 Integration in `extractor.py`
- [ ] Extractor lädt Prompt dynamisch aus Cache
- [ ] Fallback auf statischen Prompt wenn Cache fehlt

### Technische Details
```
Eingabe: ontologies/
├── loans general module/Loans.rdf
├── loans specific module/
│   ├── CommercialLoans.rdf
│   ├── ConsumerLoans.rdf
│   ├── StudentLoans.rdf
│   ├── GreenLoans.rdf
│   └── CardAccounts.rdf
└── real estate loans module/Mortgages.rdf

Ausgabe: vocabulary_cache.json
{
  "classes": [
    {"name": "Loan", "label": "Loan", "description": "...", "source": "Loans.rdf"},
    {"name": "CommercialLoan", "label": "Commercial Loan", "description": "...", "source": "CommercialLoans.rdf"},
    ...
  ],
  "properties": [
    {"name": "hasLender", "label": "has lender", "domain": "Loan", "range": "Lender", "source": "Loans.rdf"},
    ...
  ],
  "generated_prompt": "You are a Semantic Translator..."
}
```

---

## Sprint 1.2: PDF Test-Daten-Generierung

### Ziel
Erstellung von 10 realistischen Kredit-/Darlehensverträgen als PDF für das Benchmarking.

### Aufgaben

#### 1.2.1 Datei `generate_test_pdfs.py` erstellen
```python
# Funktionen:
- generate_loan_contract(loan_type: str, params: dict) -> str
- create_pdf_from_text(text: str, filename: str)
- generate_test_suite()
```

**Die 10 Test-PDFs:**

| Nr. | Dateiname | Darlehenstyp | Besonderheit |
|-----|-----------|--------------|--------------|
| 001 | Vertrag_001_ConsumerLoan.pdf | Consumer Loan | Standard |
| 002 | Vertrag_002_CommercialLoan.pdf | Commercial Loan | Firmenkunde |
| 003 | Vertrag_003_Mortgage.pdf | Mortgage | Immobilienkredit |
| 004 | Vertrag_004_StudentLoan.pdf | Student Loan | Bildungskredit |
| 005 | Vertrag_005_SubsidizedStudentLoan.pdf | Subsidized Student Loan | Gefördert |
| 006 | Vertrag_006_GreenLoan.pdf | Green Loan | Nachhaltig |
| 007 | Vertrag_007_CardAccount.pdf | Card Account | Kreditkarte |
| 008 | Vertrag_008_CommercialLoan_Complex.pdf | Commercial Loan | Mehrere Parteien |
| 009 | Vertrag_009_Mortgage_Refinance.pdf | Mortgage | Refinanzierung |
| **010** | **Vertrag_010_ERROR_CLASH.pdf** | **Consumer Loan** | **Absichtlicher Fehler: Natural Person als Lender** |

#### 1.2.2 Clash-Szenario für Vertrag 010
Der absichtliche logische Fehler:
- **Fehler:** Eine natürliche Person (z.B. "Max Müller") wird als Kreditgeber (Lender) für einen Commercial Loan angegeben
- **Erwartung:** Der Validator erkennt einen Disjointness-Clash (NaturalPerson kann nicht gleichzeitig Lender sein, oder Lender für Commercial Loans muss eine FinancialInstitution sein)

```
Beispiel-Text im PDF:
"Der Kreditgeber Max Müller (geb. 15.03.1985) gewährt der ACME GmbH
einen gewerblichen Kredit (Commercial Loan) in Höhe von 500.000 EUR."

Extrahierte Triples:
- (Max_Müller, rdf:type, NaturalPerson)
- (Max_Müller, rdf:type, Lender)  ← CLASH!
- (TheLoan, rdf:type, CommercialLoan)
- (TheLoan, hasLender, Max_Müller)
```

#### 1.2.3 Test `test_pdf_generator.py` erstellen
**Testfälle:**
- [ ] Alle 10 PDFs werden erfolgreich generiert
- [ ] PDFs sind lesbar (PyPDF2/pdfplumber)
- [ ] PDF 010 enthält den Clash-Text

### Abhängigkeiten
- `reportlab` für PDF-Generierung
- `fpdf2` als Alternative

---

## Workflow nach Phase 1

Nach Abschluss von Phase 1 sollte folgendes vorhanden sein:

```
OV-RAG/
├── vocabulary_scanner.py      # NEU
├── generate_test_pdfs.py      # NEU
├── vocabulary_cache.json      # NEU (generiert)
├── data/
│   ├── Vertrag_001_ConsumerLoan.pdf
│   ├── Vertrag_002_CommercialLoan.pdf
│   ├── ...
│   └── Vertrag_010_ERROR_CLASH.pdf
├── docs/tests/
│   ├── TEST_TEMPLATE.md
│   ├── test_report_vocabulary_scanner.md
│   └── test_report_pdf_generator.md
└── Memory.md  # Aktualisiert für Phase 2
```

---

## Zeitplan (Entwicklungsschritte)

1. **Schritt 1:** `vocabulary_scanner.py` implementieren
2. **Schritt 2:** Test für Scanner schreiben und ausführen
3. **Schritt 3:** Scanner-Integration in Extractor
4. **Schritt 4:** Memory.md aktualisieren, Git Push
5. **Schritt 5:** `generate_test_pdfs.py` implementieren
6. **Schritt 6:** Test für PDF-Generator
7. **Schritt 7:** Memory.md aktualisieren, Git Push → **Phase 1 abgeschlossen**

---

*Erstellt: 2025-02-13*
