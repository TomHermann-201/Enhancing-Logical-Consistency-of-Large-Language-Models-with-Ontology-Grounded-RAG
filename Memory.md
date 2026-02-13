# Projekt Memory: OV-RAG Prototyp

## 1. Aktueller Status
- **Phase:** Phase 1: PDF-Generierung & RDF-Vokabular-Scanner
- **Letzter Git-Commit:** b234251 (Add manual clash test proving OWL-DL reasoning detects hallucinations)
- **Datum:** 2025-02-13

## 2. Erledigte Aufgaben (Done)
- [x] Grundgerüst des OV-RAG Systems implementiert (main.py, extractor.py, validator.py, rag_pipeline.py)
- [x] LOAN Ontologie-Module integriert (Loans.rdf, CommercialLoans.rdf, ConsumerLoans.rdf, StudentLoans.rdf, GreenLoans.rdf, CardAccounts.rdf, Mortgages.rdf)
- [x] HermiT Reasoner mit Pellet-Fallback implementiert
- [x] Language-Tag Cleaning für Reasoner-Kompatibilität
- [x] Test für HermiT-Fix erstellt (test_hermit_fix.py)
- [x] REQUIREMENTS.md und Memory.md angelegt
- [x] **Manueller Clash-Test** (`test_manual_clash.py`) - 4/4 Tests bestanden:
  - ✅ Szenario 1: Gültige Aussage → CONSISTENT
  - ✅ Szenario 2: SecuredLoan ⊥ UnsecuredLoan → INCONSISTENT erkannt
  - ✅ Szenario 3: NaturalPerson ⊥ LegalEntity → INCONSISTENT erkannt
  - ✅ Szenario 4: OpenEndCredit ⊥ ClosedEndCredit → INCONSISTENT erkannt

## 3. Aktuelle TODO (Next Step)
- [ ] **RDF-Vokabular-Scanner implementieren**
  - Automatisches Parsen aller .rdf Dateien in `ontologies/`
  - Extraktion von Klassen (owl:Class) und Properties (owl:ObjectProperty, owl:DatatypeProperty)
  - Generierung eines dynamischen Extractor-Prompts basierend auf dem Vokabular
  - Speichern als `vocabulary_cache.json`

## 4. Vorhandene Komponenten
| Komponente | Datei | Status |
|------------|-------|--------|
| RAG Pipeline | `rag_pipeline.py` | ✅ Implementiert |
| Triple Extractor | `extractor.py` | ✅ Implementiert (statischer Prompt) |
| Ontology Validator | `validator.py` | ✅ Implementiert |
| CLI Interface | `main.py` | ✅ Implementiert |
| **Manueller Clash-Test** | `test_manual_clash.py` | ✅ 4/4 Tests bestanden |
| Vokabular-Scanner | `vocabulary_scanner.py` | ❌ Noch zu erstellen |
| PDF-Generator | `generate_test_pdfs.py` | ❌ Noch zu erstellen |
| Korrekturschleife | in `main.py` | ❌ Noch zu erweitern |
| Benchmark Engine | `benchmark.py` | ❌ Noch zu erstellen |
| Streamlit Dashboard | `app.py` | ❌ Noch zu erstellen |

## 5. Test-Daten Status
- **Vorhanden:** 1 PDF (`facility_agreement_loan.pdf`)
- **Benötigt:** 10 PDFs (9 konsistente + 1 mit Clash)

## 6. Bekannte Probleme / Blockaden
- HermiT Reasoner hat Probleme mit `langString` Datatype → Pellet-Fallback implementiert
- Java-Memory muss auf 4GB gesetzt werden für komplexe Ontologien

## 7. Nächste Schritte (Reihenfolge)
1. `vocabulary_scanner.py` implementieren
2. Test für Scanner schreiben und ausführen
3. 10 Test-PDFs generieren (`generate_test_pdfs.py`)
4. Memory.md aktualisieren
5. Git commit & push

## 8. Detaillierter Entwicklungsplan
Siehe: `docs/PHASE_1_PLAN.md` für den vollständigen Plan mit:
- Sprint 1.1: RDF-Vokabular-Scanner
- Sprint 1.2: PDF Test-Daten-Generierung
- Akzeptanzkriterien und Testfälle

---
*Zuletzt aktualisiert: 2025-02-13 - Nach Erstellung des manuellen Clash-Tests (4/4 bestanden)*
