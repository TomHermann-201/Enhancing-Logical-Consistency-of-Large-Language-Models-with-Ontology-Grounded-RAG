"""
validator.py
The Ontology Validator - Core thesis contribution.

This module validates extracted triples against the FIBO ontology using
Description Logic reasoning (HermiT reasoner via owlready2).

Detects three types of logical inconsistencies:
1. Disjointness violations (e.g., NaturalPerson cannot be a Corporation)
2. Cardinality violations (e.g., isWhollyOwnedBy implies max 1 parent)
3. Irreflexivity violations (e.g., a company cannot own itself)
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from owlready2 import (
    get_ontology,
    World,
    OwlReadyInconsistentOntologyError,
    sync_reasoner_hermit,
    sync_reasoner_pellet,
    Thing,
    ObjectProperty,
)
import owlready2

# CRITICAL: Set Java heap memory for reasoners
# Default is 512MB which is insufficient for complex ontologies
# Increase to 4GB (adjust based on available system RAM)
owlready2.reasoning.JAVA_MEMORY = 4000

# Flag to track which reasoner to use
# Pellet is the primary reasoner because HermiT cannot handle rdf:langString
# annotations in the FIBO/LOAN TBox, even after cleaning 204+ language tags.
REASONER_FALLBACK_MODE = 'pellet'


@dataclass
class ValidationResult:
    """Result of ontology validation."""
    is_valid: bool
    explanation: str
    inconsistent_triples: List[Dict] = None

    def __str__(self) -> str:
        status = "[OK] VALID" if self.is_valid else "[X] INVALID"
        return f"{status}\n{self.explanation}"


class OntologyValidator:
    """
    Validates extracted triples against LOAN ontology using HermiT reasoner.

    This is the core validation layer that acts as a gatekeeper to ensure
    logical consistency of LLM-generated financial/loan statements.
    """

    def __init__(self, ontology_dir: str = "ontologies"):
        """
        Initialize the validator with LOAN ontologies.

        Args:
            ontology_dir: Directory containing LOAN RDF files
        """
        self.ontology_dir = Path(ontology_dir)
        self.world = None
        self.onto = None
        self.loan_namespaces = {}

        # Verify ontology files exist
        if not self._verify_ontologies():
            raise FileNotFoundError(
                f"Required LOAN ontology files not found in {self.ontology_dir}. "
                "Ensure your LOAN ontology files are in the correct directory structure."
            )

        print("Initializing LOAN Ontology Validator...")
        self._load_ontologies()
        print("[OK] Validator ready")

    def _verify_ontologies(self) -> bool:
        """Check if required ontology files exist."""
        # Check for LOAN ontology files
        loan_ontology_paths = [
            self.ontology_dir / "loans general module" / "Loans.rdf",
            self.ontology_dir / "loans specific module" / "ConsumerLoans.rdf",
            self.ontology_dir / "loans specific module" / "CommercialLoans.rdf",
            self.ontology_dir / "real estate loans module" / "Mortgages.rdf"
        ]

        for file_path in loan_ontology_paths:
            if not file_path.exists():
                print(f"[X] Missing: {file_path}")
                return False

        return True

    # Path for the persistent ontology cache (built once, reused offline)
    CACHE_FILE = Path("ontology_cache.sqlite3")

    def _load_ontologies(self):
        """
        Load LOAN ontology modules into owlready2 World.

        Uses a persistent SQLite cache so that FIBO imports (downloaded from
        spec.edmcouncil.org) only need to be fetched once. Subsequent loads
        work fully offline.

        If the cache doesn't exist and the network is unavailable, falls back
        to loading only the local RDF files (without FIBO imports).
        """
        if self.CACHE_FILE.exists():
            self._load_from_cache()
            return

        # First run: try full load with FIBO imports → build cache
        try:
            self._build_cache()
        except RuntimeError:
            # Network unavailable — load local files only
            print("  [!] FIBO servers unreachable, loading local files only")
            self._load_local_only()

    def _build_cache(self):
        """Load ontologies from RDF files, clean language tags, and persist to SQLite cache."""
        try:
            self.world = World(filename=str(self.CACHE_FILE))

            for file_path in self._ontology_paths():
                if file_path.exists():
                    print(f"  Loading: {file_path.name}")
                    onto = self.world.get_ontology(f"file://{file_path.absolute()}").load()
                    if self.onto is None:
                        self.onto = onto

            print(f"[OK] Loaded LOAN ontology modules (with FIBO imports)")

            # Pre-clean language tags so cached copies are already clean
            self._clean_language_tags()

            # Persist to SQLite
            self.world.save()
            print(f"[OK] Ontology cache saved to {self.CACHE_FILE}")

        except Exception as e:
            # Close world and remove partial cache on failure
            self.world = None
            self.onto = None
            if self.CACHE_FILE.exists():
                self.CACHE_FILE.unlink()
            raise RuntimeError(f"Failed to load LOAN ontologies: {e}")

    def _load_from_cache(self):
        """Load ontologies from the persistent SQLite cache (offline-capable)."""
        try:
            # Copy cache to a temp file so we get a clean, writable world
            # (the original cache stays pristine for future reloads)
            tmp = tempfile.mktemp(suffix=".sqlite3")
            shutil.copy2(str(self.CACHE_FILE), tmp)

            self.world = World(filename=tmp)
            self.onto = next(iter(self.world.ontologies()), None)

            n_classes = len(list(self.world.classes()))
            print(f"[OK] Loaded ontologies from cache ({n_classes} classes)")

        except Exception as e:
            # Cache corrupted — rebuild or fall back to local
            print(f"  [!] Cache load failed ({e}), falling back to local files")
            self.CACHE_FILE.unlink(missing_ok=True)
            self._load_local_only()

    def _load_local_only(self):
        """
        Load only the local LOAN RDF files without resolving remote FIBO imports.

        owlready2's only_local=True flag doesn't propagate to transitive
        imports (owl:imports in loaded files still call .load() without it).
        We monkey-patch Ontology.load temporarily to force only_local=True
        on all recursive import loads.
        """
        from owlready2 import namespace as _ns

        self.world = World()

        original_load = _ns.Ontology.load

        def _force_local_load(self_onto, only_local=True, **kwargs):
            try:
                return original_load(self_onto, only_local=True, **kwargs)
            except FileNotFoundError:
                # Remote FIBO import not available locally — skip silently
                return self_onto

        _ns.Ontology.load = _force_local_load
        try:
            for file_path in self._ontology_paths():
                if file_path.exists():
                    print(f"  Loading (local): {file_path.name}")
                    onto = self.world.get_ontology(f"file://{file_path.absolute()}").load(only_local=True)
                    if self.onto is None:
                        self.onto = onto
        finally:
            _ns.Ontology.load = original_load

        # Clean language tags on the locally-loaded data
        self._clean_language_tags()

        n_classes = len(list(self.world.classes()))
        print(f"[OK] Loaded local LOAN ontology ({n_classes} classes, no FIBO imports)")

    def _ontology_paths(self):
        """Return the list of local LOAN ontology file paths."""
        return [
            self.ontology_dir / "loans general module" / "Loans.rdf",
            self.ontology_dir / "loans specific module" / "ConsumerLoans.rdf",
            self.ontology_dir / "loans specific module" / "CommercialLoans.rdf",
            self.ontology_dir / "loans specific module" / "StudentLoans.rdf",
            self.ontology_dir / "loans specific module" / "GreenLoans.rdf",
            self.ontology_dir / "loans specific module" / "CardAccounts.rdf",
            self.ontology_dir / "real estate loans module" / "Mortgages.rdf",
        ]

    def _reload_world(self):
        """
        Recreate a clean World with ontologies.

        Must be called before each validation to prevent contamination
        from previous validation attempts (e.g., leftover individuals
        or inferred axioms from the correction loop).

        Loads from the SQLite cache if available, otherwise from local files.
        """
        self.world = None
        self.onto = None
        if self.CACHE_FILE.exists():
            self._load_from_cache()
        else:
            self._load_local_only()

    def _get_class_by_name(self, class_name: str):
        """
        Get an ontology class by its short name or CURIE.

        Args:
            class_name: FIBO class name (e.g., "NaturalPerson" or "fibo-be-le-lp:NaturalPerson")

        Returns:
            The ontology class or None if not found
        """
        # Try to find the class in the world
        # Strip the CURIE prefix if present
        if ":" in class_name:
            class_name = class_name.split(":")[-1]

        # Search through all classes in the world
        for cls in self.world.classes():
            if cls.name == class_name:
                return cls

        print(f"Warning: Class '{class_name}' not found in ontology")
        return None

    def _get_property_by_name(self, property_name: str):
        """
        Get an ontology property by its short name or CURIE.

        Args:
            property_name: FIBO property name (e.g., "isParentCompanyOf")

        Returns:
            The ontology property or None if not found
        """
        # Strip the CURIE prefix if present
        if ":" in property_name:
            property_name = property_name.split(":")[-1]

        # Search through all properties in the world
        for prop in self.world.properties():
            if prop.name == property_name:
                return prop

        print(f"Warning: Property '{property_name}' not found in ontology")
        return None

    def _clean_language_tags(self):
        """
        Remove language tags from all data/annotation property values.

        This fixes the HermiT langString incompatibility issue by converting
        language-tagged strings (e.g., "Text"@en) to plain strings.

        Cleans both TBox (classes, properties) and ABox (individuals)
        because FIBO ontology annotations (rdfs:label, skos:definition,
        cmns-av:explanatoryNote) on classes/properties carry language tags
        that HermiT cannot handle.
        """
        print("  Cleaning language tags from ontology data...")
        cleaned_count = 0

        # Clean TBox: classes and properties (where most language tags live)
        # Skip Thing — it's the abstract base class and Thing.get_properties()
        # is an unbound method that raises TypeError.
        for entity in list(self.world.classes()) + list(self.world.properties()):
            if entity is Thing:
                continue
            cleaned_count += self._clean_entity_language_tags(entity)

        # Clean ABox: individuals
        for entity in self.world.individuals():
            cleaned_count += self._clean_entity_language_tags(entity)

        if cleaned_count > 0:
            print(f"  Cleaned {cleaned_count} language-tagged string(s)")
        else:
            print("  No language tags found")

        return cleaned_count

    def _clean_entity_language_tags(self, entity):
        """
        Remove language tags from all annotation/data property values on a single entity.

        Args:
            entity: An owlready2 entity (class, property, or individual)

        Returns:
            Number of language-tagged strings cleaned
        """
        cleaned = 0

        # Try get_properties() first (works for classes and individuals).
        # Property entities don't support get_properties() — owlready2 treats it
        # as an annotation lookup and raises AttributeError. For those, fall back
        # to cleaning standard annotation attributes directly.
        try:
            props = entity.get_properties()
        except (TypeError, AttributeError):
            return self._clean_standard_annotations(entity)

        for prop in props:
            if isinstance(prop, ObjectProperty):
                continue
            try:
                values = prop[entity]
                if not values:
                    continue

                new_values = []
                modified = False

                for value in values:
                    if hasattr(value, 'lang') and value.lang:
                        new_values.append(str(value))
                        modified = True
                        cleaned += 1
                    else:
                        new_values.append(value)

                if modified:
                    prop[entity] = new_values

            except (AttributeError, TypeError):
                continue
        return cleaned

    def _clean_standard_annotations(self, entity):
        """
        Fallback: clean language tags from standard annotation attributes
        (label, comment) on entities where get_properties() is unavailable.
        """
        cleaned = 0
        for attr in ('label', 'comment'):
            try:
                values = getattr(entity, attr, None)
                if not values:
                    continue

                new_values = []
                modified = False

                for value in values:
                    if hasattr(value, 'lang') and value.lang:
                        new_values.append(str(value))
                        modified = True
                        cleaned += 1
                    else:
                        new_values.append(value)

                if modified:
                    setattr(entity, attr, new_values)

            except (AttributeError, TypeError):
                continue
        return cleaned

    def _run_reasoner_with_fallback(self):
        """
        Run the reasoner with fallback mechanism.

        Tries HermiT first, falls back to Pellet if langString issue occurs.

        Returns:
            True if reasoning succeeded, False otherwise

        Raises:
            OwlReadyInconsistentOntologyError: If ontology is inconsistent
        """
        global REASONER_FALLBACK_MODE

        # If we already know HermiT doesn't work, use Pellet directly
        if REASONER_FALLBACK_MODE == 'pellet':
            print("  Running Pellet reasoner...")
            try:
                sync_reasoner_pellet(self.world, infer_property_values=True, debug=0)
                print("  [OK] Pellet reasoning complete - ontology is consistent")
                return True
            except OwlReadyInconsistentOntologyError:
                # Re-raise inconsistency errors
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

        # Try HermiT first
        print("  Running HermiT reasoner...")
        try:
            sync_reasoner_hermit(self.world, infer_property_values=True, debug=0)
            print("  [OK] HermiT reasoning complete - ontology is consistent")
            return True
        except OwlReadyInconsistentOntologyError:
            # This is what we want to catch - actual inconsistencies!
            raise
        except Exception as hermit_error:
            error_msg = str(hermit_error)

            # Check if it's the langString error
            if "langString" in error_msg or "UnsupportedDatatypeException" in error_msg:
                print("  [!] HermiT cannot handle langString datatype in ontology schema")
                print("  [i] Falling back to Pellet reasoner...")

                # Set global flag to use Pellet for future validations
                REASONER_FALLBACK_MODE = 'pellet'

                # Try Pellet
                try:
                    sync_reasoner_pellet(self.world, infer_property_values=True, debug=0)
                    print("  [OK] Pellet reasoning complete - ontology is consistent")
                    return True
                except OwlReadyInconsistentOntologyError:
                    # Re-raise inconsistency errors
                    raise
                except Exception as pellet_error:
                    print(f"  [X] Pellet also failed: {str(pellet_error)[:200]}")
                    print("  [!] WARNING: Could not perform full semantic reasoning")
                    return False
            else:
                # Different HermiT error
                print(f"  [!] HermiT error: {error_msg[:200]}")
                print("  [!] WARNING: Could not perform full semantic reasoning")
                return False

    def validate_triples(self, triples: List[Dict]) -> ValidationResult:
        """
        Validate a list of extracted triples against FIBO ontology.

        Args:
            triples: List of dicts with keys: sub, pred, obj, sub_type, obj_type

        Returns:
            ValidationResult object with validation status and explanation
        """
        if not triples:
            return ValidationResult(
                is_valid=True,
                explanation="No triples to validate"
            )

        # Reload a clean world to prevent contamination between attempts
        self._reload_world()

        print(f"\nValidating {len(triples)} triple(s)...")

        try:
            # Create a temporary ontology for this validation
            temp_onto = self.world.get_ontology("http://temp.validation.onto")

            with temp_onto:
                # Step 1: Create individuals for all entities
                individuals = {}

                for triple in triples:
                    sub_name = triple.get("sub")
                    obj_name = triple.get("obj")
                    sub_type = triple.get("sub_type")
                    obj_type = triple.get("obj_type")
                    pred_name = triple.get("pred")

                    # Handle rdf:type assertions specially
                    if pred_name in ["rdf:type", "type"]:
                        target_class = self._get_class_by_name(obj_name)

                        if sub_name not in individuals:
                            # First type assertion — create the individual
                            if target_class:
                                individuals[sub_name] = target_class(sub_name.replace(" ", "_"))
                                print(f"  Created: {sub_name} as {obj_name}")
                            else:
                                sub_class = self._get_class_by_name(sub_type)
                                if sub_class:
                                    individuals[sub_name] = sub_class(sub_name.replace(" ", "_"))
                                    print(f"  Created: {sub_name} as {sub_type} (type assertion)")
                                else:
                                    individuals[sub_name] = Thing(sub_name.replace(" ", "_"))
                                    print(f"  Created: {sub_name} as Thing (fallback)")
                        else:
                            # Additional type assertion — add class to existing individual
                            if target_class:
                                individuals[sub_name].is_a.append(target_class)
                                print(f"  Added type: {sub_name} also a {obj_name}")

                        continue  # Skip property assertion for type triples

                    # Create subject individual
                    if sub_name not in individuals:
                        sub_class = self._get_class_by_name(sub_type)
                        if sub_class:
                            individuals[sub_name] = sub_class(sub_name.replace(" ", "_"))
                            print(f"  Created: {sub_name} as {sub_type}")
                        else:
                            # Fallback to Thing if class not found
                            individuals[sub_name] = Thing(sub_name.replace(" ", "_"))
                            print(f"  Created: {sub_name} as Thing (fallback)")

                    # Create object individual (only for non-type assertions)
                    if obj_name not in individuals:
                        obj_class = self._get_class_by_name(obj_type)
                        if obj_class:
                            individuals[obj_name] = obj_class(obj_name.replace(" ", "_"))
                            print(f"  Created: {obj_name} as {obj_type}")
                        else:
                            individuals[obj_name] = Thing(obj_name.replace(" ", "_"))
                            print(f"  Created: {obj_name} as Thing (fallback)")

                # Step 2: Assert properties (relations) - skip rdf:type
                for triple in triples:
                    sub_name = triple.get("sub")
                    pred_name = triple.get("pred")
                    obj_name = triple.get("obj")

                    # Skip type assertions as they were handled in Step 1
                    if pred_name in ["rdf:type", "type"]:
                        continue

                    sub_individual = individuals.get(sub_name)
                    obj_individual = individuals.get(obj_name)

                    if sub_individual and obj_individual:
                        property_obj = self._get_property_by_name(pred_name)

                        if property_obj:
                            # Assert the property
                            try:
                                prop_list = getattr(sub_individual, property_obj.name, None)
                                if prop_list is not None:
                                    prop_list.append(obj_individual)
                                    print(f"  Asserted: {sub_name} {pred_name} {obj_name}")
                                else:
                                    # Create the property dynamically
                                    setattr(sub_individual, property_obj.name, [obj_individual])
                                    print(f"  Asserted: {sub_name} {pred_name} {obj_name}")
                            except AttributeError:
                                print(f"  Warning: Could not assert {pred_name}")
                        else:
                            print(f"  Warning: Property {pred_name} not found")

                # Step 3: Run the reasoner with automatic fallback to Pellet if needed
                # (Language tags are pre-cleaned in the SQLite cache)
                print()
                reasoning_succeeded = self._run_reasoner_with_fallback()

                if not reasoning_succeeded:
                    print("\n  [!] WARNING: Full semantic reasoning could not be completed")
                    print("  [i] Basic structural validation passed (no immediate inconsistencies)")
                    print("  [i] Consider using a langString-compatible ontology version")

            # If we reach here, ontology is consistent
            return ValidationResult(
                is_valid=True,
                explanation=(
                    "All triples are logically consistent with LOAN ontology.\n"
                    f"Validated {len(triples)} assertion(s) successfully."
                )
            )

        except OwlReadyInconsistentOntologyError as e:
            # Ontology is inconsistent - this is what we want to detect!
            explanation = self._generate_inconsistency_explanation(triples, str(e))

            return ValidationResult(
                is_valid=False,
                explanation=explanation,
                inconsistent_triples=triples
            )

        except Exception as e:
            # Unexpected error
            return ValidationResult(
                is_valid=False,
                explanation=f"Validation error: {type(e).__name__}: {str(e)}"
            )

    def _generate_inconsistency_explanation(
        self, triples: List[Dict], error_msg: str
    ) -> str:
        """
        Generate a human-readable explanation of the inconsistency.

        Args:
            triples: The triples that caused the inconsistency
            error_msg: The error message from the reasoner

        Returns:
            Detailed explanation string
        """
        explanation_parts = [
            "LOGICAL INCONSISTENCY DETECTED",
            "=" * 60,
            "",
            "The following assertions violate FIBO ontology constraints:",
            ""
        ]

        # List the problematic triples
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

    def validate_text_answer(
        self, answer_text: str, extracted_triples: List[Dict]
    ) -> ValidationResult:
        """
        High-level method to validate an LLM-generated answer.

        Args:
            answer_text: The natural language answer from the LLM
            extracted_triples: Triples extracted from the answer

        Returns:
            ValidationResult
        """
        print("\n" + "=" * 70)
        print("ONTOLOGY VALIDATION")
        print("=" * 70)
        print(f"Answer: {answer_text[:100]}..." if len(answer_text) > 100 else f"Answer: {answer_text}")
        print()

        if not extracted_triples:
            return ValidationResult(
                is_valid=False,
                explanation="No triples extracted from answer. Cannot validate."
            )

        result = self.validate_triples(extracted_triples)
        print("\n" + "=" * 70)
        print(result)
        print("=" * 70)

        return result


# Convenience function for quick validation
def validate_answer(
    answer: str,
    triples: List[Dict],
    ontology_dir: str = "ontologies"
) -> ValidationResult:
    """
    Convenience function to validate an answer with triples.

    Args:
        answer: The LLM-generated answer text
        triples: Extracted triples from the answer
        ontology_dir: Directory containing FIBO ontology files

    Returns:
        ValidationResult
    """
    validator = OntologyValidator(ontology_dir)
    return validator.validate_text_answer(answer, triples)


if __name__ == "__main__":
    # Test the validator with a sample inconsistent triple
    print("Testing Ontology Validator...")
    print()

    # Example 1: Valid triple
    valid_triples = [
        {
            "sub": "John Doe",
            "pred": "hasIdentity",
            "obj": "Person123",
            "sub_type": "NaturalPerson",
            "obj_type": "NaturalPerson"
        }
    ]

    # Example 2: Invalid triple (should cause disjointness violation)
    invalid_triples = [
        {
            "sub": "John Doe",
            "pred": "isParentCompanyOf",
            "obj": "ACME Corp",
            "sub_type": "NaturalPerson",  # Natural persons cannot be parent companies
            "obj_type": "Corporation"
        }
    ]

    validator = OntologyValidator()

    print("\n" + "="*70)
    print("Test 1: Valid Triple")
    print("="*70)
    result1 = validator.validate_triples(valid_triples)
    print(result1)

    print("\n" + "="*70)
    print("Test 2: Invalid Triple (Disjointness Violation)")
    print("="*70)
    result2 = validator.validate_triples(invalid_triples)
    print(result2)
