"""
setup_ontologies.py
Downloads the necessary FIBO ontology modules from the OMG specification.

Required FIBO Modules:
1. FND (Foundations): Relations, Agreements & Contracts
2. BE (Business Entities): Legal Persons, Corporations, Corporate Control
"""

import os
import requests
from pathlib import Path
from typing import Dict, List
from tqdm import tqdm


# FIBO Base URL
FIBO_BASE_URL = "https://spec.edmcouncil.org/fibo/ontology"

# Define the specific modules we need
FIBO_MODULES: Dict[str, List[str]] = {
    "FND": [
        "FND/Relations/Relations.rdf",              # fibo-fnd-rel-rel
        "FND/AgreeementsAndContracts/Contracts.rdf" # fibo-fnd-agr-ctr
    ],
    "BE": [
        "BE/LegalEntities/LegalPersons.rdf",        # fibo-be-le-lp
        "BE/Corporations/Corporations.rdf",         # fibo-be-corp-corp
        "BE/OwnershipAndControl/CorporateControl.rdf" # fibo-be-oac-cctl
    ]
}

# Alternative direct URLs (in case the structure above doesn't work)
DIRECT_URLS = {
    "fibo-fnd-rel-rel.rdf": f"{FIBO_BASE_URL}/FND/Relations/Relations.rdf",
    "fibo-fnd-agr-ctr.rdf": f"{FIBO_BASE_URL}/FND/AgreeementsAndContracts/Contracts.rdf",
    "fibo-be-le-lp.rdf": f"{FIBO_BASE_URL}/BE/LegalEntities/LegalPersons.rdf",
    "fibo-be-corp-corp.rdf": f"{FIBO_BASE_URL}/BE/Corporations/Corporations.rdf",
    "fibo-be-oac-cctl.rdf": f"{FIBO_BASE_URL}/BE/OwnershipAndControl/CorporateControl.rdf"
}


def download_file(url: str, destination: Path, timeout: int = 30) -> bool:
    """
    Download a file from a URL to a local destination.

    Args:
        url: The URL to download from
        destination: The local file path to save to
        timeout: Request timeout in seconds

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"Downloading: {url}")
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()

        # Ensure parent directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Write the file
        with open(destination, 'wb') as f:
            f.write(response.content)

        print(f"[OK] Saved to: {destination}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"[X] Failed to download {url}: {e}")
        return False


def setup_ontologies(ontology_dir: str = "ontologies") -> bool:
    """
    Download all required FIBO ontology modules.

    Args:
        ontology_dir: Directory to save ontology files

    Returns:
        bool: True if all downloads successful
    """
    ontology_path = Path(ontology_dir)
    ontology_path.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("FIBO Ontology Setup")
    print("=" * 70)
    print(f"Target directory: {ontology_path.absolute()}")
    print()

    success_count = 0
    total_count = len(DIRECT_URLS)

    # Download each ontology file
    for filename, url in DIRECT_URLS.items():
        destination = ontology_path / filename

        # Skip if already exists
        if destination.exists():
            print(f"[i] Already exists: {filename}")
            success_count += 1
            continue

        # Download the file
        if download_file(url, destination):
            success_count += 1

        print()

    # Summary
    print("=" * 70)
    print(f"Download Summary: {success_count}/{total_count} successful")

    if success_count == total_count:
        print("[OK] All ontology files ready!")
        print()
        print("Next steps:")
        print("1. Set up your OpenAI API key: export OPENAI_API_KEY='your-key'")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Run the system: python main.py")
        return True
    else:
        print("[X] Some downloads failed. Please check your internet connection.")
        print("   You may need to manually download the files from:")
        print(f"   {FIBO_BASE_URL}")
        return False


def verify_ontologies(ontology_dir: str = "ontologies") -> bool:
    """
    Verify that all required ontology files exist.

    Args:
        ontology_dir: Directory containing ontology files

    Returns:
        bool: True if all files exist
    """
    ontology_path = Path(ontology_dir)

    if not ontology_path.exists():
        print(f"[X] Ontology directory not found: {ontology_path}")
        return False

    missing_files = []
    for filename in DIRECT_URLS.keys():
        file_path = ontology_path / filename
        if not file_path.exists():
            missing_files.append(filename)

    if missing_files:
        print(f"[X] Missing {len(missing_files)} ontology file(s):")
        for filename in missing_files:
            print(f"  - {filename}")
        return False

    print(f"[OK] All {len(DIRECT_URLS)} ontology files present")
    return True


if __name__ == "__main__":
    import sys

    # Check for verify flag
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        success = verify_ontologies()
    else:
        success = setup_ontologies()

    sys.exit(0 if success else 1)
