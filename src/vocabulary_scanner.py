"""
vocabulary_scanner.py
Automatisches RDF-Vokabular-Mapping für OV-RAG

Scannt alle .rdf Dateien im ontologies/ Verzeichnis und extrahiert:
- owl:Class Definitionen mit Labels und Descriptions
- owl:ObjectProperty und owl:DatatypeProperty
- Disjointness-Axiome
- Domain/Range Constraints

Generiert einen dynamischen Extractor-Prompt basierend auf dem gefundenen Vokabular.
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from xml.etree import ElementTree as ET


# XML Namespaces für RDF/OWL Parsing
NAMESPACES = {
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
    'owl': 'http://www.w3.org/2002/07/owl#',
    'skos': 'http://www.w3.org/2004/02/skos/core#',
    'cmns-av': 'https://www.omg.org/spec/Commons/AnnotationVocabulary/',
    'dcterms': 'http://purl.org/dc/terms/',
}


@dataclass
class OntologyClass:
    """Repräsentiert eine OWL-Klasse aus der Ontologie."""
    uri: str
    name: str
    label: str
    definition: str
    synonyms: List[str]
    source_file: str
    parent_classes: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OntologyProperty:
    """Repräsentiert eine OWL-Property aus der Ontologie."""
    uri: str
    name: str
    label: str
    definition: str
    property_type: str  # 'ObjectProperty' oder 'DatatypeProperty'
    domain: Optional[str]
    range: Optional[str]
    source_file: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DisjointnessAxiom:
    """Repräsentiert ein Disjointness-Axiom."""
    classes: List[str]
    source_file: str

    def to_dict(self) -> dict:
        return asdict(self)


class VocabularyScanner:
    """
    Scannt LOAN-Ontologie RDF-Dateien und extrahiert das Vokabular.
    """

    def __init__(self, ontology_dir: str = "ontologies"):
        """
        Initialisiert den Scanner.

        Args:
            ontology_dir: Verzeichnis mit den RDF-Dateien
        """
        self.ontology_dir = Path(ontology_dir)
        self.classes: Dict[str, OntologyClass] = {}
        self.properties: Dict[str, OntologyProperty] = {}
        self.disjointness_axioms: List[DisjointnessAxiom] = []

    def scan_all(self) -> dict:
        """
        Scannt alle RDF-Dateien im Ontologie-Verzeichnis.

        Returns:
            Dictionary mit allen extrahierten Vokabular-Elementen
        """
        print("="*70)
        print("VOCABULARY SCANNER - LOAN Ontologie")
        print("="*70)

        # Finde alle RDF-Dateien
        rdf_files = list(self.ontology_dir.glob("**/*.rdf"))
        print(f"Gefunden: {len(rdf_files)} RDF-Dateien\n")

        for rdf_file in rdf_files:
            self._scan_file(rdf_file)

        # Zusammenfassung
        print("\n" + "="*70)
        print("ZUSAMMENFASSUNG")
        print("="*70)
        print(f"Klassen:              {len(self.classes)}")
        print(f"Properties:           {len(self.properties)}")
        print(f"Disjointness-Axiome:  {len(self.disjointness_axioms)}")

        return self._build_vocabulary_dict()

    def _scan_file(self, rdf_file: Path):
        """Scannt eine einzelne RDF-Datei."""
        print(f"Scanning: {rdf_file.name}")

        try:
            tree = ET.parse(rdf_file)
            root = tree.getroot()

            # Extrahiere Klassen
            classes_found = self._extract_classes(root, rdf_file.name)

            # Extrahiere Properties
            props_found = self._extract_properties(root, rdf_file.name)

            # Extrahiere Disjointness-Axiome
            disjoints_found = self._extract_disjointness(root, rdf_file.name)

            print(f"  → {classes_found} Klassen, {props_found} Properties, {disjoints_found} Disjoint-Axiome")

        except ET.ParseError as e:
            print(f"  [!] Parse-Fehler: {e}")
        except Exception as e:
            print(f"  [!] Fehler: {type(e).__name__}: {e}")

    def _extract_classes(self, root: ET.Element, source_file: str) -> int:
        """Extrahiert owl:Class Definitionen."""
        count = 0

        # Suche nach owl:Class Elementen
        for cls_elem in root.findall('.//owl:Class', NAMESPACES):
            uri = cls_elem.get(f"{{{NAMESPACES['rdf']}}}about")
            if not uri:
                continue

            # Extrahiere Name aus URI
            name = self._extract_name_from_uri(uri)
            if not name:
                continue

            # Extrahiere Label
            label = self._get_text(cls_elem, 'rdfs:label') or name

            # Extrahiere Definition
            definition = self._get_text(cls_elem, 'skos:definition') or ""

            # Extrahiere Synonyme
            synonyms = []
            for syn_elem in cls_elem.findall('cmns-av:synonym', NAMESPACES):
                if syn_elem.text:
                    synonyms.append(syn_elem.text.strip())

            # Extrahiere Parent-Klassen (rdfs:subClassOf)
            parent_classes = []
            for parent_elem in cls_elem.findall('rdfs:subClassOf', NAMESPACES):
                parent_ref = parent_elem.get(f"{{{NAMESPACES['rdf']}}}resource")
                if parent_ref:
                    parent_name = self._extract_name_from_uri(parent_ref)
                    if parent_name:
                        parent_classes.append(parent_name)

            # Speichere nur wenn es eine LOAN-relevante Klasse ist
            if self._is_loan_relevant(uri, name):
                self.classes[name] = OntologyClass(
                    uri=uri,
                    name=name,
                    label=label,
                    definition=definition,
                    synonyms=synonyms,
                    source_file=source_file,
                    parent_classes=parent_classes
                )
                count += 1

        return count

    def _extract_properties(self, root: ET.Element, source_file: str) -> int:
        """Extrahiert owl:ObjectProperty und owl:DatatypeProperty."""
        count = 0

        # Object Properties
        for prop_elem in root.findall('.//owl:ObjectProperty', NAMESPACES):
            if self._process_property(prop_elem, 'ObjectProperty', source_file):
                count += 1

        # Datatype Properties
        for prop_elem in root.findall('.//owl:DatatypeProperty', NAMESPACES):
            if self._process_property(prop_elem, 'DatatypeProperty', source_file):
                count += 1

        return count

    def _process_property(self, prop_elem: ET.Element, prop_type: str, source_file: str) -> bool:
        """Verarbeitet ein einzelnes Property-Element."""
        uri = prop_elem.get(f"{{{NAMESPACES['rdf']}}}about")
        if not uri:
            return False

        name = self._extract_name_from_uri(uri)
        if not name:
            return False

        # Extrahiere Label
        label = self._get_text(prop_elem, 'rdfs:label') or name

        # Extrahiere Definition
        definition = self._get_text(prop_elem, 'skos:definition') or ""

        # Extrahiere Domain
        domain_elem = prop_elem.find('rdfs:domain', NAMESPACES)
        domain = None
        if domain_elem is not None:
            domain_ref = domain_elem.get(f"{{{NAMESPACES['rdf']}}}resource")
            if domain_ref:
                domain = self._extract_name_from_uri(domain_ref)

        # Extrahiere Range
        range_elem = prop_elem.find('rdfs:range', NAMESPACES)
        range_val = None
        if range_elem is not None:
            range_ref = range_elem.get(f"{{{NAMESPACES['rdf']}}}resource")
            if range_ref:
                range_val = self._extract_name_from_uri(range_ref)

        # Speichere nur LOAN-relevante Properties
        if self._is_loan_relevant(uri, name):
            self.properties[name] = OntologyProperty(
                uri=uri,
                name=name,
                label=label,
                definition=definition,
                property_type=prop_type,
                domain=domain,
                range=range_val,
                source_file=source_file
            )
            return True

        return False

    def _extract_disjointness(self, root: ET.Element, source_file: str) -> int:
        """Extrahiert Disjointness-Axiome."""
        count = 0

        # Suche nach owl:AllDisjoint
        for disjoint_elem in root.findall('.//owl:AllDisjointClasses', NAMESPACES):
            classes = []
            # Suche nach owl:members
            members = disjoint_elem.find('owl:members', NAMESPACES)
            if members is not None:
                for member in members:
                    ref = member.get(f"{{{NAMESPACES['rdf']}}}resource")
                    if ref:
                        name = self._extract_name_from_uri(ref)
                        if name:
                            classes.append(name)

            if len(classes) >= 2:
                self.disjointness_axioms.append(DisjointnessAxiom(
                    classes=classes,
                    source_file=source_file
                ))
                count += 1

        # Suche nach owl:disjointWith
        for cls_elem in root.findall('.//owl:Class', NAMESPACES):
            cls_uri = cls_elem.get(f"{{{NAMESPACES['rdf']}}}about")
            if not cls_uri:
                continue

            cls_name = self._extract_name_from_uri(cls_uri)

            for disjoint in cls_elem.findall('owl:disjointWith', NAMESPACES):
                disjoint_ref = disjoint.get(f"{{{NAMESPACES['rdf']}}}resource")
                if disjoint_ref:
                    disjoint_name = self._extract_name_from_uri(disjoint_ref)
                    if cls_name and disjoint_name:
                        self.disjointness_axioms.append(DisjointnessAxiom(
                            classes=[cls_name, disjoint_name],
                            source_file=source_file
                        ))
                        count += 1

        return count

    def _extract_name_from_uri(self, uri: str) -> Optional[str]:
        """Extrahiert den lokalen Namen aus einer URI."""
        if not uri:
            return None

        # Versuche # oder / als Separator
        if '#' in uri:
            return uri.split('#')[-1]
        elif '/' in uri:
            return uri.split('/')[-1]

        return None

    def _get_text(self, elem: ET.Element, tag: str) -> Optional[str]:
        """Holt den Text eines Child-Elements."""
        child = elem.find(tag, NAMESPACES)
        if child is not None and child.text:
            return child.text.strip()
        return None

    def _is_loan_relevant(self, uri: str, name: str) -> bool:
        """
        Prüft ob eine Klasse/Property relevant für LOAN ist.
        Filtert Commons/FND Dependencies heraus.
        """
        # Nur LOAN-Namespace oder explizit relevante Konzepte
        loan_patterns = [
            'LOAN/',
            'loan-',
            'fibo-loan',
        ]

        # Bekannte relevante Konzepte (auch wenn sie aus anderen Namespaces kommen)
        relevant_names = {
            'Loan', 'Lender', 'Borrower', 'Collateral', 'Guarantor',
            'SecuredLoan', 'UnsecuredLoan', 'CollateralizedLoan',
            'ClosedEndCredit', 'OpenEndCredit', 'CreditAgreement',
            'CommercialLoan', 'ConsumerLoan', 'StudentLoan', 'Mortgage',
            'GreenLoan', 'CardAccount', 'CreditCard',
            'FinancialInstitution', 'LegalEntity', 'NaturalPerson',
            'hasBorrower', 'hasLender', 'hasCollateral', 'hasGuarantor',
            'hasPrincipalAmount', 'hasInterestRate', 'hasMaturityDate',
        }

        # Prüfe URI-Patterns
        for pattern in loan_patterns:
            if pattern in uri:
                return True

        # Prüfe bekannte Namen
        if name in relevant_names:
            return True

        return False

    def _build_vocabulary_dict(self) -> dict:
        """Erstellt das finale Vokabular-Dictionary."""
        return {
            'classes': [cls.to_dict() for cls in self.classes.values()],
            'properties': [prop.to_dict() for prop in self.properties.values()],
            'disjointness_axioms': [ax.to_dict() for ax in self.disjointness_axioms],
            'statistics': {
                'total_classes': len(self.classes),
                'total_properties': len(self.properties),
                'total_disjointness_axioms': len(self.disjointness_axioms),
            }
        }

    def generate_extractor_prompt(self) -> str:
        """
        Generiert einen dynamischen Extractor-Prompt basierend auf dem
        gescannten Vokabular.
        """
        # Sammle Klassen mit Labels
        class_lines = []
        for cls in sorted(self.classes.values(), key=lambda x: x.name):
            desc = f" - {cls.definition[:80]}..." if len(cls.definition) > 80 else f" - {cls.definition}" if cls.definition else ""
            synonyms = f" (also: {', '.join(cls.synonyms)})" if cls.synonyms else ""
            class_lines.append(f"- {cls.name}{synonyms}{desc}")

        # Sammle Properties mit Domain/Range
        property_lines = []
        for prop in sorted(self.properties.values(), key=lambda x: x.name):
            domain_range = ""
            if prop.domain or prop.range:
                domain_range = f" [{prop.domain or '?'} → {prop.range or '?'}]"
            desc = f" - {prop.definition[:60]}..." if len(prop.definition) > 60 else f" - {prop.definition}" if prop.definition else ""
            property_lines.append(f"- {prop.name}{domain_range}{desc}")

        # Sammle Disjointness-Axiome
        disjoint_lines = []
        seen_pairs = set()
        for axiom in self.disjointness_axioms:
            pair = tuple(sorted(axiom.classes))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                disjoint_lines.append(f"- {' ⊥ '.join(axiom.classes)}")

        prompt = f"""You are a Semantic Translator for financial loan documents. Extract facts from the text and map them to these LOAN ontology concepts:

## Classes (Loan Types & Entities)
{chr(10).join(class_lines[:30])}

## Properties (Relations)
{chr(10).join(property_lines[:20])}

## Disjointness Axioms (CRITICAL - These cause CLASHES if violated!)
{chr(10).join(disjoint_lines[:15])}

## Extraction Guidelines:
1. Extract factual assertions including TYPE CLASSIFICATIONS (e.g., "X is a StudentLoan")
2. For unnamed entities (like "the loan"), use descriptive subjects like "TheLoan"
3. IMPORTANT: Type assertions should use "rdf:type" as predicate
   Example: {{"sub": "TheLoan", "pred": "rdf:type", "obj": "StudentLoan", "sub_type": "Loan", "obj_type": "Class"}}
4. Map entities to the MOST SPECIFIC class that applies
5. Include relationships between lenders, borrowers, and loans
6. Include loan characteristics (amount, rate, type) when mentioned
7. Each triple must have: sub, pred, obj, sub_type, obj_type

## Output Format:
Return JSON: {{"triples": [{{"sub": "...", "pred": "...", "obj": "...", "sub_type": "...", "obj_type": "..."}}]}}

If no triples can be extracted, return: {{"triples": []}}
"""
        return prompt

    def save_cache(self, output_path: str = "vocabulary_cache.json"):
        """
        Speichert das Vokabular als JSON-Cache.

        Args:
            output_path: Pfad zur Cache-Datei
        """
        vocabulary = self._build_vocabulary_dict()
        vocabulary['generated_prompt'] = self.generate_extractor_prompt()

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(vocabulary, f, indent=2, ensure_ascii=False)

        print(f"\n[OK] Cache gespeichert: {output_path}")
        return output_path


def scan_and_cache(ontology_dir: str = "ontologies", cache_path: str = "vocabulary_cache.json") -> dict:
    """
    Convenience-Funktion: Scannt Ontologien und speichert Cache.

    Args:
        ontology_dir: Verzeichnis mit RDF-Dateien
        cache_path: Pfad für die Cache-Datei

    Returns:
        Das gescannte Vokabular als Dictionary
    """
    scanner = VocabularyScanner(ontology_dir)
    vocabulary = scanner.scan_all()
    scanner.save_cache(cache_path)
    return vocabulary


def load_cached_prompt(cache_path: str = "vocabulary_cache.json") -> Optional[str]:
    """
    Lädt den generierten Prompt aus dem Cache.

    Args:
        cache_path: Pfad zur Cache-Datei

    Returns:
        Der generierte Prompt oder None wenn Cache nicht existiert
    """
    if not os.path.exists(cache_path):
        return None

    with open(cache_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('generated_prompt')


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    print("="*70)
    print("OV-RAG VOCABULARY SCANNER")
    print("="*70)
    print()

    # Scanne Ontologien
    scanner = VocabularyScanner("ontologies")
    vocabulary = scanner.scan_all()

    # Generiere und zeige Prompt
    print("\n" + "="*70)
    print("GENERIERTER EXTRACTOR-PROMPT")
    print("="*70)
    prompt = scanner.generate_extractor_prompt()
    print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)

    # Speichere Cache
    scanner.save_cache()

    print("\n" + "="*70)
    print("FERTIG")
    print("="*70)
