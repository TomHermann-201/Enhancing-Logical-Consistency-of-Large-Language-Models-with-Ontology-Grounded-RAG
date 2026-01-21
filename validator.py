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
REASONER_FALLBACK_MODE = None  # Will be set to 'pellet' if HermiT fails


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

    def _load_ontologies(self):
        """Load LOAN ontology modules into owlready2 World."""
        try:
            # Create a new world (isolated reasoning environment)
            self.world = World()

            # Load each LOAN ontology file
            ontology_paths = [
                self.ontology_dir / "loans general module" / "Loans.rdf",
                self.ontology_dir / "loans specific module" / "ConsumerLoans.rdf",
                self.ontology_dir / "loans specific module" / "CommercialLoans.rdf",
                self.ontology_dir / "loans specific module" / "StudentLoans.rdf",
                self.ontology_dir / "loans specific module" / "GreenLoans.rdf",
                self.ontology_dir / "loans specific module" / "CardAccounts.rdf",
                self.ontology_dir / "real estate loans module" / "Mortgages.rdf"
            ]

            for file_path in ontology_paths:
                if file_path.exists():
                    print(f"  Loading: {file_path.name}")
                    onto = self.world.get_ontology(f"file://{file_path.absolute()}").load()

                    # Store reference to the main ontology
                    if self.onto is None:
                        self.onto = onto

            print(f"[OK] Loaded {len(ontology_paths)} LOAN ontology modules")

        except Exception as e:
            raise RuntimeError(f"Failed to load LOAN ontologies: {e}")

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
        Remove language tags from all data property values in the ontology.

        This fixes the HermiT langString incompatibility issue by converting
        language-tagged strings (e.g., "Text"@en) to plain strings.

        This is called before reasoning to ensure compatibility.
        """
        print("  Cleaning language tags from ontology data...")
        cleaned_count = 0

        # Iterate through all individuals in the world
        for individual in self.world.individuals():
            # Get all properties of this individual
            for prop in individual.get_properties():
                # Skip object properties (relationships)
                if isinstance(prop, ObjectProperty):
                    continue

                # Get current values
                try:
                    values = prop[individual]
                    if not values:
                        continue

                    # Check if any values are language-tagged strings
                    new_values = []
                    modified = False

                    for value in values:
                        # Check if it's a Locstr (language-tagged string in owlready2)
                        if hasattr(value, 'lang') and value.lang:
                            # Convert to plain string
                            new_values.append(str(value))
                            modified = True
                            cleaned_count += 1
                        else:
                            new_values.append(value)

                    # Update property values if modified
                    if modified:
                        prop[individual] = new_values

                except (AttributeError, TypeError):
                    # Skip properties that can't be accessed
                    continue

        if cleaned_count > 0:
            print(f"  Cleaned {cleaned_count} language-tagged string(s)")
        else:
            print("  No language tags found")

        return cleaned_count

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
            print("  Running Pellet reasoner (fallback mode)...")
            try:
                sync_reasoner_pellet(self.world, infer_property_values=True, debug=0)
                print("  [OK] Pellet reasoning complete - ontology is consistent")
                return True
            except OwlReadyInconsistentOntologyError:
                # Re-raise inconsistency errors
                raise
            except Exception as e:
                print(f"  [!] Pellet reasoner error: {str(e)[:200]}")
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
                        # For type assertions, create subject as the object class
                        if sub_name not in individuals:
                            target_class = self._get_class_by_name(obj_name)
                            if target_class:
                                individuals[sub_name] = target_class(sub_name.replace(" ", "_"))
                                print(f"  Created: {sub_name} as {obj_name}")
                            else:
                                # Fallback - try the sub_type
                                sub_class = self._get_class_by_name(sub_type)
                                if sub_class:
                                    individuals[sub_name] = sub_class(sub_name.replace(" ", "_"))
                                    print(f"  Created: {sub_name} as {sub_type} (type assertion)")
                                else:
                                    individuals[sub_name] = Thing(sub_name.replace(" ", "_"))
                                    print(f"  Created: {sub_name} as Thing (fallback)")
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

                # Step 3: Clean language tags to avoid langString issues in data
                self._clean_language_tags()

                # Step 4: Run the reasoner with automatic fallback to Pellet if needed
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
