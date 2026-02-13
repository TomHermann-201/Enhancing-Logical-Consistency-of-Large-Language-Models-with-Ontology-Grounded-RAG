# Projekt Memory: OV-RAG Prototyp

## 1. Aktueller Status
- **Phase:** Phase 1: PDF-Generierung & RDF-Vokabular-Scanner
- **Letzter Git-Commit:** cfccdee (Implement vocabulary scanner with dynamic prompt generation)
- **Datum:** 2025-02-13

## 2. Erledigte Aufgaben (Done)
- [x] Grundgerüst des OV-RAG Systems implementiert (main.py, extractor.py, validator.py, rag_pipeline.py)
- [x] LOAN Ontologie-Module integriert (Loans.rdf, CommercialLoans.rdf, ConsumerLoans.rdf, StudentLoans.rdf, GreenLoans.rdf, CardAccounts.rdf, Mortgages.rdf)
- [x] HermiT Reasoner mit Pellet-Fallback implementiert
- [x] Language-Tag Cleaning für Reasoner-Kompatibilität
- [x] Test für HermiT-Fix erstellt (test_hermit_fix.py)
- [x] REQUIREMENTS.md und Memory.md angelegt
- [x] **Manueller Clash-Test** (`test_manual_clash.py`) - 4/4 Tests bestanden
- [x] **Vokabular-Scanner** (`vocabulary_scanner.py`) - 6/6 Tests bestanden:
  - ✅ 7 RDF-Dateien gefunden
  - ✅ 86 Klassen extrahiert (Loan, SecuredLoan, CommercialLoan, Mortgage, etc.)
  - ✅ 25 Properties extrahiert (hasBorrower, hasLender, etc.)
  - ✅ 2 Disjointness-Axiome (SecuredLoan ⊥ UnsecuredLoan, OpenEndCredit ⊥ ClosedEndCredit)
  - ✅ Cache gespeichert als `vocabulary_cache.json`
  - ✅ Dynamischer Prompt integriert in `extractor.py`

## 3. Aktuelle TODO (Next Step)
- [ ] **10 Test-PDFs generieren** (`generate_test_pdfs.py`)
  - 9 konsistente Verträge (Consumer, Commercial, Mortgage, Student, Green, etc.)
  - 1 fehlerhafter Vertrag (`Vertrag_010_ERROR_CLASH.pdf`) mit absichtlichem Clash

## 4. Vorhandene Komponenten
| Komponente | Datei | Status |
|------------|-------|--------|
| RAG Pipeline | `rag_pipeline.py` | ✅ Implementiert |
| Triple Extractor | `extractor.py` | ✅ Implementiert (dynamischer Prompt) |
| Ontology Validator | `validator.py` | ✅ Implementiert |
| CLI Interface | `main.py` | ✅ Implementiert |
| **Manueller Clash-Test** | `test_manual_clash.py` | ✅ 4/4 Tests bestanden |
| **Vokabular-Scanner** | `vocabulary_scanner.py` | ✅ 6/6 Tests bestanden |
| **Vokabular-Cache** | `vocabulary_cache.json` | ✅ 86 Klassen, 25 Properties |
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
1. ~~`vocabulary_scanner.py` implementieren~~ ✅
2. ~~Test für Scanner schreiben und ausführen~~ ✅
3. 10 Test-PDFs generieren (`generate_test_pdfs.py`) ← **NÄCHSTER SCHRITT**
4. Memory.md aktualisieren
5. Git commit & push

## 8. Detaillierter Entwicklungsplan
Siehe: `docs/PHASE_1_PLAN.md` für den vollständigen Plan mit:
- Sprint 1.1: RDF-Vokabular-Scanner ✅ ABGESCHLOSSEN
- Sprint 1.2: PDF Test-Daten-Generierung ← AKTUELL
- Akzeptanzkriterien und Testfälle

---
*Zuletzt aktualisiert: 2025-02-13 - Nach Implementierung des Vokabular-Scanners (6/6 Tests bestanden)*
