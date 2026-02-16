# Projekt Memory: OV-RAG Prototyp

## 1. Aktueller Status
- **Phase:** Phase 1: ABGESCHLOSSEN ✅ → Bereit für Phase 2
- **Letzter Git-Commit:** a1c69ca (Remove ontology hints from test PDFs)
- **Datum:** 2026-02-13

## 2. Erledigte Aufgaben (Done)
- [x] Grundgerüst des OV-RAG Systems implementiert (main.py, extractor.py, validator.py, rag_pipeline.py)
- [x] LOAN Ontologie-Module integriert (7 RDF-Dateien)
- [x] HermiT Reasoner mit Pellet-Fallback implementiert
- [x] Language-Tag Cleaning für Reasoner-Kompatibilität
- [x] Test für HermiT-Fix erstellt (test_hermit_fix.py)
- [x] REQUIREMENTS.md und Memory.md angelegt
- [x] **Manueller Clash-Test** (`test_manual_clash.py`) - 4/4 Tests bestanden
- [x] **Vokabular-Scanner** (`vocabulary_scanner.py`) - 6/6 Tests bestanden
- [x] **10 Test-PDFs generiert** (`generate_test_pdfs.py`) - 10/10 PDFs (English, neutral filenames, NO ontology hints):
  | Nr. | File | Type | Status |
  |-----|------|------|--------|
  | 001 | Contract_001.pdf | ConsumerLoan | ✅ Consistent |
  | 002 | Contract_002.pdf | CommercialLoan | ✅ Consistent |
  | 003 | Contract_003.pdf | Mortgage | ✅ Consistent |
  | 004 | Contract_004.pdf | StudentLoan | ✅ Consistent |
  | 005 | Contract_005.pdf | SubsidizedStudentLoan | ✅ Consistent |
  | 006 | Contract_006.pdf | GreenLoan | ✅ Consistent |
  | 007 | Contract_007.pdf | CardAccount (OpenEnd) | ✅ Consistent |
  | 008 | Contract_008.pdf | CommercialLoan (Syndicated) | ✅ Consistent |
  | 009 | Contract_009.pdf | Mortgage (Refinance) | ✅ Consistent |
  | **010** | **Contract_010.pdf** | **CommercialLoan** | ⚠️ **HIDDEN CLASH (no hints in PDF)** |

## 3. Aktuelle TODO (Next Step)
- [ ] **Phase 2: Validation Loop mit Hard-Reject**
  - Implementierung der Korrekturschleife (max. 3 Versuche)
  - Hard-Reject Logik bei 3 fehlgeschlagenen Korrekturen
  - Integration in `main.py`

## 4. Vorhandene Komponenten
| Komponente | Datei | Status |
|------------|-------|--------|
| RAG Pipeline | `rag_pipeline.py` | ✅ Implementiert |
| Triple Extractor | `extractor.py` | ✅ Dynamischer Prompt |
| Ontology Validator | `validator.py` | ✅ Implementiert |
| CLI Interface | `main.py` | ✅ Implementiert |
| Manueller Clash-Test | `test_manual_clash.py` | ✅ 4/4 Tests |
| Vokabular-Scanner | `vocabulary_scanner.py` | ✅ 6/6 Tests |
| Vokabular-Cache | `vocabulary_cache.json` | ✅ 86 Klassen |
| **PDF-Generator** | `generate_test_pdfs.py` | ✅ 10/10 PDFs |
| Korrekturschleife | in `main.py` | ❌ Phase 2 |
| Benchmark Engine | `benchmark.py` | ❌ Phase 3 |
| Streamlit Dashboard | `app.py` | ❌ Phase 4 |

## 5. Test Data Status
- **Available:** 11 PDFs (1 original + 10 generated, all in English)
- **Consistent:** 9 contracts (Contract_001.pdf - Contract_009.pdf)
- **With Hidden Clash:** 1 contract (Contract_010.pdf)
- **Clash Type:** NaturalPerson (John Smith) as Lender for CommercialLoan
- **Benchmark Fairness:** No ontology hints in PDFs - OV-RAG must detect clashes from context

## 6. Bekannte Probleme / Blockaden
- HermiT Reasoner hat Probleme mit `langString` Datatype → Pellet-Fallback implementiert
- Java-Memory muss auf 4GB gesetzt werden für komplexe Ontologien 

## 7. Nächste Schritte (Reihenfolge)
1. ~~`vocabulary_scanner.py` implementieren~~ ✅
2. ~~Test für Scanner schreiben und ausführen~~ ✅
3. ~~10 Test-PDFs generieren~~ ✅
4. ~~Memory.md aktualisieren~~ ✅
5. ~~Git commit & push~~ (nach diesem Update)
6. **Phase 2: Validation Loop implementieren** ← NÄCHSTER SCHRITT

## 8. Detaillierter Entwicklungsplan
Siehe: `docs/PHASE_1_PLAN.md`
- Sprint 1.1: RDF-Vokabular-Scanner ✅ ABGESCHLOSSEN
- Sprint 1.2: PDF Test-Daten-Generierung ✅ ABGESCHLOSSEN

**PHASE 1 KOMPLETT!** Bereit für Phase 2.

---
*Zuletzt aktualisiert: 2026-02-13 - PDFs ohne Ontology-Hints für fairen RAG vs OV-RAG Vergleich*
