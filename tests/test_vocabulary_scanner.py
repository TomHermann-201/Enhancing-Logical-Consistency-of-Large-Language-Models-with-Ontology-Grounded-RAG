"""
test_vocabulary_scanner.py
Tests für den Vocabulary Scanner
"""

import os
import json
import tempfile
from pathlib import Path

from vocabulary_scanner import (
    VocabularyScanner,
    scan_and_cache,
    load_cached_prompt,
    OntologyClass,
    OntologyProperty,
)


SEPARATOR = "=" * 70


def test_scanner_finds_all_rdf_files():
    """Test: Scanner findet alle 7 RDF-Dateien."""
    print(f"\n{SEPARATOR}")
    print("TEST: Scanner findet alle RDF-Dateien")
    print(SEPARATOR)

    scanner = VocabularyScanner("ontologies")

    rdf_files = list(scanner.ontology_dir.glob("**/*.rdf"))
    print(f"  Gefundene Dateien: {len(rdf_files)}")

    for f in rdf_files:
        print(f"    - {f.name}")

    assert len(rdf_files) == 7, f"Erwartet: 7 RDF-Dateien, gefunden: {len(rdf_files)}"
    print("\n  ✅ TEST BESTANDEN")
    return True


def test_scanner_extracts_loan_classes():
    """Test: Scanner extrahiert LOAN-relevante Klassen."""
    print(f"\n{SEPARATOR}")
    print("TEST: Scanner extrahiert LOAN-Klassen")
    print(SEPARATOR)

    scanner = VocabularyScanner("ontologies")
    scanner.scan_all()

    # Prüfe dass wichtige Klassen gefunden wurden
    expected_classes = [
        'Loan',
        'SecuredLoan',
        'UnsecuredLoan',
        'CollateralizedLoan',
        'ClosedEndCredit',
        'OpenEndCredit',
        'CommercialLoan',
        'StudentLoan',
        'Mortgage',
    ]

    found_classes = list(scanner.classes.keys())
    print(f"  Gefundene Klassen: {len(found_classes)}")

    missing = []
    for cls_name in expected_classes:
        if cls_name in found_classes:
            print(f"    ✓ {cls_name}")
        else:
            print(f"    ✗ {cls_name} (FEHLT)")
            missing.append(cls_name)

    # Mindestens 50% der erwarteten Klassen sollten gefunden werden
    found_count = len(expected_classes) - len(missing)
    success_rate = found_count / len(expected_classes)

    print(f"\n  Erfolgsrate: {found_count}/{len(expected_classes)} ({success_rate*100:.0f}%)")

    assert success_rate >= 0.5, f"Zu wenige Klassen gefunden: {success_rate*100:.0f}%"
    print("\n  ✅ TEST BESTANDEN")
    return True


def test_scanner_extracts_properties():
    """Test: Scanner extrahiert Properties."""
    print(f"\n{SEPARATOR}")
    print("TEST: Scanner extrahiert Properties")
    print(SEPARATOR)

    scanner = VocabularyScanner("ontologies")
    scanner.scan_all()

    found_properties = list(scanner.properties.keys())
    print(f"  Gefundene Properties: {len(found_properties)}")

    # Zeige einige gefundene Properties
    for prop_name in found_properties[:10]:
        prop = scanner.properties[prop_name]
        print(f"    - {prop_name} ({prop.property_type})")

    assert len(found_properties) > 0, "Keine Properties gefunden"
    print("\n  ✅ TEST BESTANDEN")
    return True


def test_scanner_extracts_disjointness():
    """Test: Scanner extrahiert Disjointness-Axiome."""
    print(f"\n{SEPARATOR}")
    print("TEST: Scanner extrahiert Disjointness-Axiome")
    print(SEPARATOR)

    scanner = VocabularyScanner("ontologies")
    scanner.scan_all()

    print(f"  Gefundene Disjointness-Axiome: {len(scanner.disjointness_axioms)}")

    for axiom in scanner.disjointness_axioms:
        print(f"    - {' ⊥ '.join(axiom.classes)}")

    # Es sollte mindestens 1 Axiom geben (SecuredLoan ⊥ UnsecuredLoan)
    assert len(scanner.disjointness_axioms) >= 1, "Keine Disjointness-Axiome gefunden"
    print("\n  ✅ TEST BESTANDEN")
    return True


def test_cache_save_and_load():
    """Test: Cache-Datei wird korrekt geschrieben und gelesen."""
    print(f"\n{SEPARATOR}")
    print("TEST: Cache speichern und laden")
    print(SEPARATOR)

    # Temporäre Cache-Datei
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        cache_path = f.name

    try:
        # Scanne und speichere
        vocabulary = scan_and_cache("ontologies", cache_path)

        # Prüfe dass Datei existiert
        assert os.path.exists(cache_path), "Cache-Datei wurde nicht erstellt"
        print(f"  ✓ Cache-Datei erstellt: {cache_path}")

        # Lade Cache
        with open(cache_path, 'r') as f:
            loaded = json.load(f)

        # Prüfe Struktur
        assert 'classes' in loaded, "Fehlend: 'classes'"
        assert 'properties' in loaded, "Fehlend: 'properties'"
        assert 'generated_prompt' in loaded, "Fehlend: 'generated_prompt'"
        assert 'statistics' in loaded, "Fehlend: 'statistics'"

        print(f"  ✓ Cache enthält {loaded['statistics']['total_classes']} Klassen")
        print(f"  ✓ Cache enthält {loaded['statistics']['total_properties']} Properties")
        print(f"  ✓ Generierter Prompt: {len(loaded['generated_prompt'])} Zeichen")

        # Teste load_cached_prompt
        prompt = load_cached_prompt(cache_path)
        assert prompt is not None, "load_cached_prompt gab None zurück"
        assert "LOAN" in prompt or "Loan" in prompt, "Prompt enthält kein LOAN"

        print("\n  ✅ TEST BESTANDEN")
        return True

    finally:
        # Aufräumen
        if os.path.exists(cache_path):
            os.remove(cache_path)


def test_generated_prompt_contains_concepts():
    """Test: Generierter Prompt enthält wichtige Konzepte."""
    print(f"\n{SEPARATOR}")
    print("TEST: Generierter Prompt enthält wichtige Konzepte")
    print(SEPARATOR)

    scanner = VocabularyScanner("ontologies")
    scanner.scan_all()
    prompt = scanner.generate_extractor_prompt()

    # Prüfe dass wichtige Konzepte im Prompt sind
    required_concepts = [
        'Loan',
        'Classes',
        'Properties',
        'rdf:type',
        'triples',
    ]

    print(f"  Prompt-Länge: {len(prompt)} Zeichen")

    missing = []
    for concept in required_concepts:
        if concept in prompt:
            print(f"    ✓ '{concept}' gefunden")
        else:
            print(f"    ✗ '{concept}' FEHLT")
            missing.append(concept)

    assert len(missing) == 0, f"Fehlende Konzepte im Prompt: {missing}"
    print("\n  ✅ TEST BESTANDEN")
    return True


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    print(SEPARATOR)
    print("VOCABULARY SCANNER - TEST SUITE")
    print(SEPARATOR)

    results = []

    # Führe alle Tests aus
    results.append(("RDF-Dateien finden", test_scanner_finds_all_rdf_files()))
    results.append(("LOAN-Klassen extrahieren", test_scanner_extracts_loan_classes()))
    results.append(("Properties extrahieren", test_scanner_extracts_properties()))
    results.append(("Disjointness extrahieren", test_scanner_extracts_disjointness()))
    results.append(("Cache speichern/laden", test_cache_save_and_load()))
    results.append(("Prompt-Konzepte", test_generated_prompt_contains_concepts()))

    # Zusammenfassung
    print(f"\n{SEPARATOR}")
    print("ZUSAMMENFASSUNG")
    print(SEPARATOR)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}  {name}")

    print(f"\nErgebnis: {passed}/{total} Tests bestanden")

    if passed == total:
        print("\n🎉 ALLE TESTS BESTANDEN!")
    else:
        print("\n⚠️  NICHT ALLE TESTS BESTANDEN")
        exit(1)
