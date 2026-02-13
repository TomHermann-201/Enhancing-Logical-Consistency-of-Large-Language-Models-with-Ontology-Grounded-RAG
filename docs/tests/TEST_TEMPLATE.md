# Testprotokoll: [Feature Name / Sprint]
**Datum:** YYYY-MM-DD
**Test-ID:** [z.B. TEST-001]
**Status:** [PASSED / FAILED / REJECTED]

## 1. Test-Konfiguration
- **Modell (RAG):** gpt-4o
- **Modell (Extractor):** gpt-4o
- **Eingabedaten:** [z.B. Vertrag_010_ERROR_CLASH.pdf]
- **Ontologie-Module:** Loans.rdf, CommercialLoans.rdf

## 2. Ablauf & Ergebnisse
### Schritt 1: Standard RAG (Baseline)
- **Generierte Antwort:** [Volltext der ersten Antwort]
- **Status:** Potenzielle Halluzination vermutet.

### Schritt 2: Triple Extraction & Validation
- **Extrahierte Triples:**
  - (Subjekt, Prädikat, Objekt)
- **Reasoner-Status:** [Consistent / Inconsistent]
- **Verletztes Axiom:** [z.B. Disjointness: NaturalPerson disjointWith Corporation]

### Schritt 3: Korrekturschleife (Re-Validation Loop)
- **Iteration 1:** [Ergebnis & neuer Reasoner-Status]
- **Iteration 2:** [Falls nötig]
- **Iteration 3 (Final):** [Falls nötig]

## 3. Metriken & Evaluation
- **LCR (Logical Clash Rate):** [War ein Clash vorhanden? Ja/Nein]
- **CSR (Correction Success Rate):** [Wurde der Fehler geheilt? Ja/Nein]
- **Latenz:** [Zeit in Sekunden für den gesamten Prozess]
- **Hard-Reject ausgelöst?** [Ja/Nein]

## 4. Fazit & Nächste Schritte
- [Zusammenfassung des Agenten]
