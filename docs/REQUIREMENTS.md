# REQUIREMENTS.md: OV-RAG Prototype & Development Process

## 1. Projekt-Ziel
Entwicklung eines funktionalen Prototyps für das **OV-RAG Framework** zur Erkennung und Korrektur logischer Halluzinationen in Finanztexten unter Nutzung der FIBO/LOAN Ontologie.

## 2. Der "Autonomous Developer" Workflow (WICHTIG)
Der Agent MUSS nach jedem einzelnen Entwicklungsschritt diesen Zyklus durchlaufen:
1. **Develop:** Implementierung eines Teilfeatures laut TODO-Liste.
2. **Test:** Ausführen der relevanten Tests (z.B. `pytest` oder Komponententests).
3. **Document:** Aktualisierung der `Memory.md` (Was wurde getan? Was ist der nächste Schritt? Welche Probleme gab es?).
4. **Git Push:** Commit und Push der Änderungen in das Repository.

## 3. Context Management (Memory.md)
* Die Datei `Memory.md` dient als das "Langzeitgedächtnis" des Agenten.
* Sie enthält:
    - Aktueller Status des Projekts.
    - Liste der erledigten Aufgaben.
    - Definition des exakt nächsten Schritts.
    - Offene Punkte/Bugs.
* Regel für den User: Ein neuer Task beginnt immer mit dem Befehl: "Lies die Memory.md und mache von dort aus weiter."

## 4. Kern-Features (Technisch)

### 4.1 Automatisches RDF-Vokabular-Mapping
- Automatischer Scan aller `.rdf` Dateien im `ontologies/` Verzeichnis
- Extraktion von Klassen, Properties und deren Labels/Descriptions
- Dynamische Generierung der Extractor-Prompts basierend auf dem gefundenen Vokabular
- Ziel: Keine manuellen Änderungen bei Ontologie-Updates nötig

### 4.2 Test-Daten (10 PDFs)
- **9 konsistente Verträge:** Verschiedene Darlehenstypen (Consumer Loan, Commercial Loan, Mortgage, Student Loan, Green Loan, etc.)
- **1 fehlerhafter Vertrag (Vertrag_010_ERROR_CLASH.pdf):** Enthält einen absichtlichen logischen Widerspruch (z.B. eine natürliche Person als Lender für einen Commercial Loan)
- Alle PDFs im `/data` Verzeichnis

### 4.3 Validation Loop mit Hard-Reject
- Maximal **3 Korrektur-Versuche** bei erkannten logischen Clashes
- Nach 3 fehlgeschlagenen Korrekturen: **Hard-Reject** mit Begründung
- Logging aller Korrekturversuche für Analyse

### 4.4 Benchmark Engine
- Testlauf über alle 10 PDFs
- Messung der **Logical Clash Rate (LCR):** Anteil der Dokumente mit erkannten Clashes
- Messung der **Correction Success Rate (CSR):** Erfolgsrate der Korrekturschleifen
- Automatische Generierung von Testberichten in `docs/tests/`

### 4.5 Streamlit Dashboard
- **Passwortschutz:** Einfache Authentifizierung vor Zugang
- **Triple-Visualisierung:** Grafische Darstellung der extrahierten Triples
- **Reasoner-Output:** Anzeige der Validierungsergebnisse
- **Side-by-Side Vergleich:** Original-Antwort vs. korrigierte Antwort
- **Metriken-Dashboard:** LCR, CSR, Latenz pro Dokument

## 5. Benchmark & Evaluation (Groß-Test)

### 5.1 Datensatz
Skalierung auf **100 Testfragen** basierend auf den generierten Verträgen.

### 5.2 Kategorisierung der Fragen
| Typ | Anzahl | Beschreibung | Beispiele |
|-----|--------|--------------|-----------|
| **Typ A (Fakten)** | 50 | Abfrage von expliziten Daten | Zinsen, Namen, Beträge, Laufzeiten |
| **Typ B (Logik/Axiome)** | 50 | Gezielte Fallen, die Ontologie-Regeln herausfordern | Disjointness, Kardinalität, OWA vs. Integrity Constraints |

### 5.3 Vergleichs-Modus
Systematischer Vergleich zwischen:
- **Standard-RAG:** GPT-4o ohne Validator (Baseline)
- **OV-RAG:** GPT-4o + Ontologie-Validator (unser System)

### 5.4 Automatisierte Fragen-Generierung
- Skript `generate_questions.py` nutzt GPT-4o
- Generiert 100 Fragen passend zur LOAN-Ontologie und den generierten PDFs
- Kategorisiert automatisch in Typ A und Typ B
- Speichert als `data/questions.json`

### 5.5 Ergebnis-Matrix
Speicherung in `results/benchmark_results.json`:
```json
{
  "question_id": "Q001",
  "question_text": "...",
  "question_type": "A|B",
  "source_pdf": "Vertrag_001_ConsumerLoan.pdf",
  "standard_rag_answer": "...",
  "standard_rag_correct": true|false,
  "ov_rag_answer": "...",
  "ov_rag_consistent": true|false,
  "clash_detected": true|false,
  "clash_type": "Disjointness|Cardinality|null",
  "iterations_needed": 0-3,
  "hard_reject": true|false,
  "latency_ms": 1234
}
```

### 5.6 Metriken
- **Accuracy (Typ A):** Korrektheit bei Faktenfragen
- **Consistency Rate (Typ B):** Logische Konsistenz bei Axiom-Fragen
- **Clash Detection Rate:** Wie oft werden echte Clashes erkannt?
- **False Positive Rate:** Wie oft werden valide Antworten fälschlich abgelehnt?
- **Average Iterations:** Durchschnittliche Korrekturversuche

## 6. Definition of Done
Ein Feature gilt erst als fertig, wenn es:
- ✅ Implementiert ist
- ✅ Getestet wurde (mit dokumentiertem Testergebnis)
- ✅ In der `Memory.md` dokumentiert ist
- ✅ Auf Git committed und gepusht wurde

## 7. Technische Anforderungen
- **Python 3.10+**
- **OpenAI API** für RAG und Extraction (GPT-4o)
- **owlready2** für Ontologie-Management
- **HermiT/Pellet Reasoner** für logische Inferenz
- **Streamlit** für das Dashboard
- **Java 11+** für den Reasoner (min. 4GB Heap Memory)

## 8. Projekt-Phasen

### Phase 1: PDF-Generierung & RDF-Scanner (Aktuell)
- [ ] Vokabular-Scanner für automatisches Mapping
- [ ] Generierung von 10 Test-PDFs

### Phase 2: Validation Loop & Hard-Reject
- [ ] Implementierung der Korrekturschleife (max. 3 Versuche)
- [ ] Hard-Reject Logik

### Phase 3: Benchmark Engine (Klein)
- [ ] Batch-Processing aller 10 PDFs
- [ ] Metriken-Berechnung (LCR, CSR)

### Phase 4: Streamlit Dashboard
- [ ] UI-Entwicklung
- [ ] Passwortschutz
- [ ] Visualisierungen

### Phase 5: Groß-Benchmark (100 Fragen)
- [ ] Automatisierte Fragen-Generierung (`generate_questions.py`)
- [ ] Standard-RAG vs. OV-RAG Vergleich
- [ ] Ergebnis-Matrix und Analyse
- [ ] Finale Metriken-Auswertung
