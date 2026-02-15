"""
generate_test_pdfs.py
Generates 100 Test PDFs for OV-RAG Benchmark

Creates realistic loan contracts WITHOUT ontology hints (for fair RAG vs OV-RAG comparison):
- No "Ontology Class" or "Loan Type" fields
- No type labels like "(Financial Institution)" or "(Natural Person)"
- No warning markers or clash indicators
- Neutral filenames: Contract_001.pdf ... Contract_100.pdf

Distribution (60 clean + 40 clash):
  001-060: Clean — diverse loan types (no ontological inconsistencies)
  061-075: Clash — Secured vs Unsecured (e.g., mortgage listed as "unsecured" with collateral)
  076-090: Clash — OpenEnd vs ClosedEnd (e.g., credit card with fixed term)
  091-095: Clash — Borrower type (e.g., ConsumerLoan to a Corporation)
  096-100: Clash — Lender type (e.g., CommercialLoan from a NaturalPerson)

Also exports contract_ground_truth.json for evaluate.py.
"""

import json
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Seed for reproducibility
random.seed(42)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class LoanContract:
    """Represents a loan contract."""
    contract_id: str
    loan_type: str
    loan_type_description: str
    borrower_name: str
    borrower_type: str  # "NaturalPerson" or "LegalEntity"
    lender_name: str
    lender_type: str  # "FinancialInstitution" or "NaturalPerson"
    principal_amount: float
    currency: str
    interest_rate: float
    term_months: int
    purpose: str
    collateral: Optional[str] = None
    is_secured: bool = False
    special_notes: Optional[str] = None
    # Ground truth
    label: str = "CLEAN"
    clash_type: Optional[str] = None
    clash_description: Optional[str] = None


# ---------------------------------------------------------------------------
# Name pools
# ---------------------------------------------------------------------------
PERSON_NAMES = [
    "Anna Miller", "James Wilson", "Maria Garcia", "Robert Chen", "Emily Johnson",
    "Thomas Brown", "Sarah Davis", "Michael Lee", "Jennifer Martinez", "David Taylor",
    "Lisa Anderson", "Christopher White", "Amanda Harris", "Daniel Thompson", "Jessica Moore",
    "Andrew Clark", "Megan Lewis", "Ryan Hall", "Laura Young", "Kevin Allen",
    "Sophia King", "Brian Wright", "Rachel Scott", "Patrick Green", "Olivia Adams",
    "Nathan Baker", "Victoria Nelson", "Steven Hill", "Katherine Campbell", "Gregory Mitchell",
    "Diana Roberts", "Mark Turner", "Elizabeth Phillips", "Jason Evans", "Samantha Edwards",
    "Timothy Collins", "Rebecca Stewart", "Benjamin Sanchez", "Nicole Morris", "Joshua Rogers",
    "Stephanie Reed", "Matthew Cook", "Ashley Morgan", "Jonathan Bell", "Christina Murphy",
    "Brandon Bailey", "Michelle Rivera", "Alexander Cooper", "Lauren Richardson", "Tyler Cox",
    "Hannah Howard", "Austin Ward", "Heather Torres", "Dylan Peterson", "Amber Gray",
    "Zachary Ramirez", "Kayla James", "Ethan Watson", "Danielle Brooks", "Logan Kelly",
]

COMPANY_NAMES = [
    "TechStart Inc.", "ACME Industries LLC", "SolarTech Corporation", "GreenField Enterprises",
    "Pinnacle Solutions Ltd.", "Meridian Holdings Corp.", "Nexus Digital Inc.", "Atlas Manufacturing",
    "Quantum Analytics LLC", "Horizon Energy Corp.", "Summit Capital Partners", "Pacific Trading Co.",
    "Sterling Construction LLC", "Vertex Pharmaceuticals Inc.", "Catalyst Innovation Corp.",
    "Eagle Transport Ltd.", "Ironwood Properties LLC", "Spectrum Communications Inc.",
    "Frontier Agriculture Co.", "Cardinal Health Systems", "Apex Retail Group", "Coastal Logistics LLC",
    "Sapphire Technologies Inc.", "Redstone Mining Corp.", "BrightPath Education Ltd.",
    "OceanView Hospitality Inc.", "MetroLink Development Corp.", "Sierra Manufacturing LLC",
    "Crestview Financial Group", "Vanguard Defense Systems Inc.",
]

BANK_NAMES = [
    "First National Bank", "Commerce Bank of America", "Wells Fargo Home Mortgage",
    "Sallie Mae", "U.S. Department of Education", "Green Investment Bank",
    "American Express", "JPMorgan Chase", "Bank of America", "Citibank",
    "Quicken Loans", "Goldman Sachs", "Morgan Stanley", "Deutsche Bank",
    "HSBC Holdings", "Barclays", "Credit Suisse", "UBS Group",
    "TD Bank", "PNC Financial Services", "US Bancorp", "Truist Financial",
    "Capital One Financial", "State Street Corporation", "Charles Schwab",
    "Fifth Third Bancorp", "Citizens Financial Group", "KeyCorp",
    "Regions Financial", "Huntington Bancshares",
]

ADDRESSES = [
    "123 Main Street, Springfield, IL 62701",
    "456 Park Avenue, New York, NY 10022",
    "789 Oak Lane, Austin, TX 78701",
    "321 Elm Street, Portland, OR 97201",
    "654 Maple Drive, Denver, CO 80201",
    "987 Cedar Road, Seattle, WA 98101",
    "147 Pine Court, Miami, FL 33101",
    "258 Birch Boulevard, Chicago, IL 60601",
    "369 Walnut Way, Boston, MA 02101",
    "741 Spruce Avenue, San Francisco, CA 94101",
    "852 Willow Lane, Atlanta, GA 30301",
    "963 Ash Street, Phoenix, AZ 85001",
    "159 Hickory Drive, Nashville, TN 37201",
    "357 Poplar Place, Charlotte, NC 28201",
    "468 Magnolia Circle, Dallas, TX 75201",
]

PURPOSES_CONSUMER = [
    "Vehicle purchase financing",
    "Home improvement and renovation",
    "Medical expenses coverage",
    "Debt consolidation",
    "Vacation travel financing",
    "Wedding expenses",
    "Personal emergency fund",
    "Appliance and furniture purchase",
    "Moving and relocation costs",
    "Technology equipment purchase",
]

PURPOSES_COMMERCIAL = [
    "Expansion of production facilities",
    "Acquisition of Competitor Corp. and business integration",
    "Working capital for seasonal operations",
    "Equipment modernization program",
    "New market entry and expansion",
    "Supply chain optimization",
    "Research and development funding",
    "Commercial real estate acquisition",
    "Fleet vehicle purchase",
    "IT infrastructure upgrade",
]

COLLATERAL_ITEMS = [
    "Business equipment and machinery",
    "Shares in the acquired company",
    "Commercial real estate at {addr}",
    "Fleet vehicles (15 commercial trucks)",
    "Inventory and accounts receivable",
    "Intellectual property portfolio",
    "The solar installation equipment",
    "Manufacturing plant at {addr}",
    "Office building at {addr}",
    "Agricultural land and equipment",
]


def _pick(lst, exclude=None):
    """Pick a random item, optionally excluding some."""
    pool = [x for x in lst if x != exclude] if exclude else lst
    return random.choice(pool)


# ---------------------------------------------------------------------------
# Contract generators per category
# ---------------------------------------------------------------------------

def _gen_clean_contracts() -> List[LoanContract]:
    """Generate 60 clean contracts (IDs 001-060)."""
    contracts = []
    # Distribute loan types roughly evenly
    loan_specs = [
        # (type, description, is_consumer, can_be_secured, term_range)
        ("ConsumerLoan", "Consumer Loan Agreement", True, False, (12, 72)),
        ("CommercialLoan", "Commercial Loan Agreement", False, True, (24, 120)),
        ("Mortgage", "Mortgage Loan Agreement", True, True, (120, 360)),
        ("StudentLoan", "Student Loan Agreement", True, False, (60, 240)),
        ("SubsidizedStudentLoan", "Federal Subsidized Student Loan", True, False, (120, 240)),
        ("GreenLoan", "Green Loan / Sustainability Financing", False, True, (60, 180)),
        ("CardAccount", "Credit Card Account Agreement (Revolving Credit)", True, False, (0, 0)),
        ("CommercialLoan", "Syndicated Commercial Loan Agreement", False, True, (36, 120)),
    ]

    person_idx = 0
    company_idx = 0
    bank_idx = 0

    for i in range(1, 61):
        cid = f"{i:03d}"
        spec = loan_specs[i % len(loan_specs)]
        ltype, ldesc, is_consumer, can_secure, term_range = spec

        # Pick borrower
        if is_consumer:
            borrower = PERSON_NAMES[person_idx % len(PERSON_NAMES)]
            borrower_type = "NaturalPerson"
            person_idx += 1
        else:
            borrower = COMPANY_NAMES[company_idx % len(COMPANY_NAMES)]
            borrower_type = "LegalEntity"
            company_idx += 1

        lender = BANK_NAMES[bank_idx % len(BANK_NAMES)]
        bank_idx += 1

        # Amounts
        if ltype == "Mortgage":
            amount = random.randint(150, 800) * 1000
            rate = round(random.uniform(2.5, 5.0), 1)
        elif ltype == "CardAccount":
            amount = random.randint(2, 25) * 1000
            rate = round(random.uniform(15.0, 24.9), 1)
        elif ltype in ("StudentLoan", "SubsidizedStudentLoan"):
            amount = random.randint(5, 60) * 1000
            rate = round(random.uniform(0.0, 6.0), 1)
        elif ltype == "ConsumerLoan":
            amount = random.randint(3, 50) * 1000
            rate = round(random.uniform(3.0, 12.0), 1)
        else:
            amount = random.randint(50, 5000) * 1000
            rate = round(random.uniform(2.5, 8.0), 1)

        term = random.randint(*term_range) if term_range[1] > 0 else 0
        purpose = _pick(PURPOSES_CONSUMER) if is_consumer else _pick(PURPOSES_COMMERCIAL)

        collateral = None
        is_secured = False
        if ltype == "Mortgage":
            addr = _pick(ADDRESSES)
            collateral = f"First lien on property at {addr}"
            is_secured = True
        elif can_secure and random.random() > 0.3:
            coll_template = _pick(COLLATERAL_ITEMS)
            collateral = coll_template.format(addr=_pick(ADDRESSES))
            is_secured = True

        special = None
        if ltype == "SubsidizedStudentLoan":
            special = "Interest-free loan under Federal Student Aid program. Repayment begins 6 months after graduation."
        elif ltype == "CardAccount":
            special = "Open-End Credit with minimum monthly payment of 2% of outstanding balance. This is an OpenEndCredit facility."
        elif ltype == "GreenLoan":
            special = "Loan meets EU Taxonomy criteria for sustainable investments. Eligible for green bond certification."

        contracts.append(LoanContract(
            contract_id=cid, loan_type=ltype, loan_type_description=ldesc,
            borrower_name=borrower, borrower_type=borrower_type,
            lender_name=lender, lender_type="FinancialInstitution",
            principal_amount=float(amount), currency="USD",
            interest_rate=rate, term_months=term, purpose=purpose,
            collateral=collateral, is_secured=is_secured, special_notes=special,
            label="CLEAN", clash_type=None, clash_description=None,
        ))

    return contracts


def _gen_secured_unsecured_clash() -> List[LoanContract]:
    """
    Generate 15 Secured-vs-Unsecured clash contracts (IDs 061-075).

    The clash: a loan is described as secured (with collateral listed) but
    the text simultaneously states it is unsecured, or vice versa.
    For example: a mortgage labelled "unsecured" yet with a property lien.
    """
    contracts = []
    for i in range(61, 76):
        cid = f"{i:03d}"
        variant = i % 3  # 3 sub-variants

        if variant == 0:
            # Mortgage listed as "unsecured" but with collateral
            borrower = _pick(PERSON_NAMES)
            lender = _pick(BANK_NAMES)
            addr = _pick(ADDRESSES)
            contracts.append(LoanContract(
                contract_id=cid,
                loan_type="Mortgage",
                loan_type_description="Mortgage Loan Agreement",
                borrower_name=borrower, borrower_type="NaturalPerson",
                lender_name=lender, lender_type="FinancialInstitution",
                principal_amount=float(random.randint(200, 600) * 1000),
                currency="USD",
                interest_rate=round(random.uniform(2.5, 5.0), 1),
                term_months=random.choice([180, 240, 360]),
                purpose="Purchase of residential property",
                collateral=f"First lien on property at {addr}",
                is_secured=False,  # CLASH: says unsecured despite collateral
                special_notes=(
                    "This is an unsecured loan. No collateral is pledged for this "
                    "obligation. The property lien mentioned above is for reference only."
                ),
                label="CLASH", clash_type="secured_unsecured",
                clash_description="Mortgage with collateral listed but explicitly stated as unsecured loan",
            ))
        elif variant == 1:
            # Commercial loan listed as "secured" but with no collateral
            borrower = _pick(COMPANY_NAMES)
            lender = _pick(BANK_NAMES)
            contracts.append(LoanContract(
                contract_id=cid,
                loan_type="CommercialLoan",
                loan_type_description="Commercial Loan Agreement",
                borrower_name=borrower, borrower_type="LegalEntity",
                lender_name=lender, lender_type="FinancialInstitution",
                principal_amount=float(random.randint(100, 2000) * 1000),
                currency="USD",
                interest_rate=round(random.uniform(3.0, 8.0), 1),
                term_months=random.randint(24, 84),
                purpose=_pick(PURPOSES_COMMERCIAL),
                collateral=None,
                is_secured=True,  # CLASH: says secured but no collateral
                special_notes=(
                    "This is a secured loan facility. The borrower pledges collateral "
                    "as security for this loan. No specific assets have been designated "
                    "as collateral at this time."
                ),
                label="CLASH", clash_type="secured_unsecured",
                clash_description="Commercial loan stated as secured but no collateral specified",
            ))
        else:
            # Consumer loan with collateral but explicitly called "unsecured personal loan"
            borrower = _pick(PERSON_NAMES)
            lender = _pick(BANK_NAMES)
            contracts.append(LoanContract(
                contract_id=cid,
                loan_type="ConsumerLoan",
                loan_type_description="Unsecured Personal Loan Agreement",
                borrower_name=borrower, borrower_type="NaturalPerson",
                lender_name=lender, lender_type="FinancialInstitution",
                principal_amount=float(random.randint(5, 50) * 1000),
                currency="USD",
                interest_rate=round(random.uniform(4.0, 15.0), 1),
                term_months=random.randint(12, 60),
                purpose=_pick(PURPOSES_CONSUMER),
                collateral="Vehicle title and personal savings account",
                is_secured=False,  # CLASH: says unsecured but collateral listed
                special_notes=(
                    "This unsecured personal loan requires no collateral. The vehicle "
                    "title and savings account referenced above serve as additional "
                    "security for this unsecured obligation."
                ),
                label="CLASH", clash_type="secured_unsecured",
                clash_description="Consumer loan with collateral but described as unsecured",
            ))

    return contracts


def _gen_openend_closedend_clash() -> List[LoanContract]:
    """
    Generate 15 OpenEnd-vs-ClosedEnd clash contracts (IDs 076-090).

    The clash: a credit card (open-end) has a fixed maturity date, or
    a term loan (closed-end) is described as revolving.
    """
    contracts = []
    for i in range(76, 91):
        cid = f"{i:03d}"
        variant = i % 3

        if variant == 0:
            # Credit card with fixed term (should be open-end)
            borrower = _pick(PERSON_NAMES)
            lender = _pick(BANK_NAMES)
            contracts.append(LoanContract(
                contract_id=cid,
                loan_type="CardAccount",
                loan_type_description="Credit Card Account Agreement",
                borrower_name=borrower, borrower_type="NaturalPerson",
                lender_name=lender, lender_type="FinancialInstitution",
                principal_amount=float(random.randint(3, 25) * 1000),
                currency="USD",
                interest_rate=round(random.uniform(15.0, 24.9), 1),
                term_months=random.choice([24, 36, 48]),  # CLASH: fixed term on credit card
                purpose="Credit card for everyday purchases",
                is_secured=False,
                special_notes=(
                    "This is a closed-end credit card account. The full balance must "
                    "be repaid by the maturity date. No revolving credit is permitted."
                ),
                label="CLASH", clash_type="openend_closedend",
                clash_description="Credit card (open-end) with fixed maturity date described as closed-end",
            ))
        elif variant == 1:
            # Term loan described as revolving (should be closed-end)
            borrower = _pick(COMPANY_NAMES)
            lender = _pick(BANK_NAMES)
            contracts.append(LoanContract(
                contract_id=cid,
                loan_type="CommercialLoan",
                loan_type_description="Revolving Commercial Loan Agreement",
                borrower_name=borrower, borrower_type="LegalEntity",
                lender_name=lender, lender_type="FinancialInstitution",
                principal_amount=float(random.randint(100, 3000) * 1000),
                currency="USD",
                interest_rate=round(random.uniform(3.0, 8.0), 1),
                term_months=random.randint(36, 84),
                purpose=_pick(PURPOSES_COMMERCIAL),
                collateral=_pick(COLLATERAL_ITEMS).format(addr=_pick(ADDRESSES)),
                is_secured=True,
                special_notes=(
                    "This is a revolving credit facility (Open-End Credit). The borrower "
                    "may draw upon and repay the facility as needed within the credit limit. "
                    "This is an OpenEndCredit facility with a fixed maturity date and "
                    "mandatory repayment schedule."
                ),
                label="CLASH", clash_type="openend_closedend",
                clash_description="Term loan (closed-end) described as revolving open-end credit",
            ))
        else:
            # Consumer loan described as both revolving and fixed-term
            borrower = _pick(PERSON_NAMES)
            lender = _pick(BANK_NAMES)
            contracts.append(LoanContract(
                contract_id=cid,
                loan_type="ConsumerLoan",
                loan_type_description="Personal Revolving Loan Agreement",
                borrower_name=borrower, borrower_type="NaturalPerson",
                lender_name=lender, lender_type="FinancialInstitution",
                principal_amount=float(random.randint(5, 40) * 1000),
                currency="USD",
                interest_rate=round(random.uniform(5.0, 15.0), 1),
                term_months=random.randint(24, 60),
                purpose=_pick(PURPOSES_CONSUMER),
                is_secured=False,
                special_notes=(
                    "This is a revolving personal loan (Open-End Credit). The borrower may "
                    "re-borrow repaid amounts. The loan must be fully repaid in fixed monthly "
                    "installments over the stated term. This is a ClosedEndCredit with a "
                    "definite maturity date."
                ),
                label="CLASH", clash_type="openend_closedend",
                clash_description="Consumer loan described as both revolving and fixed-term simultaneously",
            ))

    return contracts


def _gen_borrower_type_clash() -> List[LoanContract]:
    """
    Generate 5 Borrower-type clash contracts (IDs 091-095).

    The clash: a consumer loan is given to a corporation, or
    a commercial loan is given to a natural person.
    """
    contracts = []
    for i in range(91, 96):
        cid = f"{i:03d}"
        variant = i % 2

        if variant == 0:
            # ConsumerLoan to a Corporation
            borrower = _pick(COMPANY_NAMES)
            lender = _pick(BANK_NAMES)
            contracts.append(LoanContract(
                contract_id=cid,
                loan_type="ConsumerLoan",
                loan_type_description="Consumer Loan Agreement",
                borrower_name=borrower, borrower_type="LegalEntity",  # CLASH
                lender_name=lender, lender_type="FinancialInstitution",
                principal_amount=float(random.randint(10, 50) * 1000),
                currency="USD",
                interest_rate=round(random.uniform(4.0, 12.0), 1),
                term_months=random.randint(12, 60),
                purpose="General consumer purchase financing",
                is_secured=False,
                special_notes=None,
                label="CLASH", clash_type="borrower_type",
                clash_description="Consumer loan issued to a corporation (should be NaturalPerson)",
            ))
        else:
            # CommercialLoan to a NaturalPerson
            borrower = _pick(PERSON_NAMES)
            lender = _pick(BANK_NAMES)
            contracts.append(LoanContract(
                contract_id=cid,
                loan_type="CommercialLoan",
                loan_type_description="Commercial Loan Agreement",
                borrower_name=borrower, borrower_type="NaturalPerson",  # CLASH
                lender_name=lender, lender_type="FinancialInstitution",
                principal_amount=float(random.randint(100, 2000) * 1000),
                currency="USD",
                interest_rate=round(random.uniform(3.0, 8.0), 1),
                term_months=random.randint(24, 84),
                purpose=_pick(PURPOSES_COMMERCIAL),
                collateral=_pick(COLLATERAL_ITEMS).format(addr=_pick(ADDRESSES)),
                is_secured=True,
                special_notes=None,
                label="CLASH", clash_type="borrower_type",
                clash_description="Commercial loan issued to a natural person (should be LegalEntity)",
            ))

    return contracts


def _gen_lender_type_clash() -> List[LoanContract]:
    """
    Generate 5 Lender-type clash contracts (IDs 096-100).

    The clash: a commercial loan or mortgage is issued by a natural person
    instead of a financial institution.
    """
    contracts = []
    for i in range(96, 101):
        cid = f"{i:03d}"
        lender_person = _pick(PERSON_NAMES)
        variant = i % 2

        if variant == 0:
            # CommercialLoan from a NaturalPerson
            borrower = _pick(COMPANY_NAMES)
            contracts.append(LoanContract(
                contract_id=cid,
                loan_type="CommercialLoan",
                loan_type_description="Commercial Loan Agreement",
                borrower_name=borrower, borrower_type="LegalEntity",
                lender_name=lender_person, lender_type="NaturalPerson",  # CLASH
                principal_amount=float(random.randint(50, 500) * 1000),
                currency="USD",
                interest_rate=round(random.uniform(5.0, 12.0), 1),
                term_months=random.randint(24, 60),
                purpose="Seed financing for business operations",
                is_secured=False,
                special_notes=None,
                label="CLASH", clash_type="lender_type",
                clash_description="Commercial loan from a natural person (should be FinancialInstitution)",
            ))
        else:
            # Mortgage from a NaturalPerson
            borrower = _pick(PERSON_NAMES, exclude=lender_person)
            addr = _pick(ADDRESSES)
            contracts.append(LoanContract(
                contract_id=cid,
                loan_type="Mortgage",
                loan_type_description="Mortgage Loan Agreement",
                borrower_name=borrower, borrower_type="NaturalPerson",
                lender_name=lender_person, lender_type="NaturalPerson",  # CLASH
                principal_amount=float(random.randint(150, 500) * 1000),
                currency="USD",
                interest_rate=round(random.uniform(3.0, 7.0), 1),
                term_months=random.choice([180, 240, 360]),
                purpose="Purchase of residential property",
                collateral=f"First lien on property at {addr}",
                is_secured=True,
                special_notes=None,
                label="CLASH", clash_type="lender_type",
                clash_description="Mortgage issued by a natural person (should be FinancialInstitution)",
            ))

    return contracts


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def generate_contract_pdf(contract: LoanContract, output_dir: str = "data") -> str:
    """Generate a PDF file for a loan contract."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    filename = f"Contract_{contract.contract_id}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ContractTitle", parent=styles["Heading1"],
        fontSize=18, alignment=TA_CENTER, spaceAfter=30,
    ))
    styles.add(ParagraphStyle(
        name="ContractSection", parent=styles["Heading2"],
        fontSize=12, spaceBefore=15, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="ContractBody", parent=styles["Normal"],
        fontSize=10, alignment=TA_JUSTIFY, spaceAfter=8,
    ))

    content = []

    # Title
    content.append(Paragraph("LOAN AGREEMENT", styles["ContractTitle"]))
    content.append(Spacer(1, 20))

    today = datetime.now()
    content.append(Paragraph(
        f"<b>Contract Number:</b> LA-2025-{contract.contract_id}<br/>"
        f"<b>Date:</b> {today.strftime('%B %d, %Y')}",
        styles["ContractBody"],
    ))
    content.append(Spacer(1, 20))

    # Section 1: Parties
    content.append(Paragraph("Section 1: Parties to the Agreement", styles["ContractSection"]))
    content.append(Paragraph(f"<b>LENDER:</b><br/>{contract.lender_name}", styles["ContractBody"]))
    content.append(Spacer(1, 10))
    content.append(Paragraph(f"<b>BORROWER:</b><br/>{contract.borrower_name}", styles["ContractBody"]))
    content.append(Spacer(1, 10))

    # Section 2: Loan Terms
    content.append(Paragraph("Section 2: Loan Terms and Conditions", styles["ContractSection"]))

    term_display = f"{contract.term_months} months" if contract.term_months > 0 else "Open-ended (revolving)"
    maturity_date = (
        (today + timedelta(days=contract.term_months * 30)).strftime("%B %d, %Y")
        if contract.term_months > 0
        else "N/A (Open-ended)"
    )

    data = [
        ["Principal Amount:", f"{contract.currency} {contract.principal_amount:,.2f}"],
        ["Interest Rate (p.a.):", f"{contract.interest_rate}%"],
        ["Term:", term_display],
        ["Maturity Date:", maturity_date],
        ["Purpose:", contract.purpose],
        ["Security:", "Yes (Secured Loan)" if contract.is_secured else "No (Unsecured Loan)"],
    ]
    if contract.collateral:
        data.append(["Collateral:", contract.collateral])

    table = Table(data, colWidths=[4 * cm, 12 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    content.append(table)
    content.append(Spacer(1, 20))

    # Section 3: Repayment
    content.append(Paragraph("Section 3: Repayment Terms", styles["ContractSection"]))
    if contract.term_months > 0:
        monthly = (
            contract.principal_amount
            * (1 + contract.interest_rate / 100 * contract.term_months / 12)
            / contract.term_months
        )
        content.append(Paragraph(
            f"Repayment shall be made in {contract.term_months} monthly installments. "
            f"The estimated monthly payment is approximately {contract.currency} {monthly:,.2f} "
            f"(including interest). A detailed amortization schedule will be provided separately.",
            styles["ContractBody"],
        ))
    else:
        content.append(Paragraph(
            "This is a revolving credit facility (Open-End Credit). "
            "The Borrower may draw upon the credit limit as needed and must make "
            "minimum monthly payments as specified in the account terms.",
            styles["ContractBody"],
        ))
    content.append(Spacer(1, 10))

    # Section 4: Special Provisions (optional)
    if contract.special_notes:
        content.append(Paragraph("Section 4: Special Provisions", styles["ContractSection"]))
        content.append(Paragraph(contract.special_notes, styles["ContractBody"]))
        content.append(Spacer(1, 10))

    # Section 5: General Terms
    content.append(Paragraph("Section 5: General Terms", styles["ContractSection"]))
    content.append(Paragraph(
        "This Agreement shall be governed by and construed in accordance with the laws "
        "of the State of New York. Any amendments or modifications must be in writing. "
        "If any provision is found to be unenforceable, the remaining provisions shall "
        "continue in full force and effect.",
        styles["ContractBody"],
    ))
    content.append(Spacer(1, 30))

    # Section 6: Signatures
    content.append(Paragraph("Section 6: Signatures", styles["ContractSection"]))
    sig_data = [
        ["_" * 30, "_" * 30],
        [contract.lender_name, contract.borrower_name],
        ["(Lender)", "(Borrower)"],
        ["Date: ____________", "Date: ____________"],
    ]
    sig_table = Table(sig_data, colWidths=[8 * cm, 8 * cm])
    sig_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
    ]))
    content.append(sig_table)

    doc.build(content)
    return filepath


# ---------------------------------------------------------------------------
# Ground truth export
# ---------------------------------------------------------------------------

def export_ground_truth(contracts: List[LoanContract], output_path: str = "contract_ground_truth.json"):
    """Export ground truth labels as JSON for evaluate.py."""
    gt = {}
    for c in contracts:
        gt[c.contract_id] = {
            "label": c.label,
            "expect_clash": c.label == "CLASH",
            "clash_type": c.clash_type,
            "clash_description": c.clash_description,
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(gt, f, indent=2, ensure_ascii=False)

    print(f"[OK] Ground truth saved to {output_path}")
    return gt


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def generate_all_contracts() -> List[LoanContract]:
    """Build the complete list of 100 contracts."""
    contracts = []
    contracts.extend(_gen_clean_contracts())          # 001-060
    contracts.extend(_gen_secured_unsecured_clash())   # 061-075
    contracts.extend(_gen_openend_closedend_clash())   # 076-090
    contracts.extend(_gen_borrower_type_clash())       # 091-095
    contracts.extend(_gen_lender_type_clash())         # 096-100
    return contracts


def generate_all_pdfs(output_dir: str = "data") -> list:
    """Generate all 100 test PDFs and ground truth JSON."""
    contracts = generate_all_contracts()

    print("=" * 70)
    print("PDF GENERATOR: 100 Test Contracts for OV-RAG Benchmark")
    print("=" * 70)
    print(f"  Clean contracts:   {sum(1 for c in contracts if c.label == 'CLEAN'):>3d}  (001-060)")
    print(f"  Secured/Unsecured: {sum(1 for c in contracts if c.clash_type == 'secured_unsecured'):>3d}  (061-075)")
    print(f"  OpenEnd/ClosedEnd: {sum(1 for c in contracts if c.clash_type == 'openend_closedend'):>3d}  (076-090)")
    print(f"  Borrower type:     {sum(1 for c in contracts if c.clash_type == 'borrower_type'):>3d}  (091-095)")
    print(f"  Lender type:       {sum(1 for c in contracts if c.clash_type == 'lender_type'):>3d}  (096-100)")
    print("=" * 70)
    print()

    generated = []
    for contract in contracts:
        try:
            filepath = generate_contract_pdf(contract, output_dir)
            generated.append(filepath)
            status = "CLEAN" if contract.label == "CLEAN" else f"CLASH ({contract.clash_type})"
            print(f"  OK  {os.path.basename(filepath):>20s}  [{status}]")
        except Exception as e:
            print(f"  ERR {contract.contract_id}: {e}")

    print()
    print("=" * 70)
    print(f"COMPLETE: {len(generated)}/{len(contracts)} PDFs generated in {output_dir}/")
    print("=" * 70)

    # Export ground truth
    gt_path = os.path.join(output_dir, "..", "contract_ground_truth.json")
    # Put ground truth in project root
    export_ground_truth(contracts, "contract_ground_truth.json")

    return generated


def verify_pdfs(pdf_dir: str = "data") -> dict:
    """Verify the generated PDFs."""
    print()
    print("=" * 70)
    print("PDF VERIFICATION")
    print("=" * 70)

    results = {"total": 0, "valid": 0, "errors": [], "files": []}
    pdf_files = sorted(Path(pdf_dir).glob("Contract_*.pdf"))
    results["total"] = len(pdf_files)

    for pdf_path in pdf_files:
        try:
            size = pdf_path.stat().st_size
            if size < 1000:
                raise ValueError(f"File too small: {size} bytes")
            with open(pdf_path, "rb") as f:
                header = f.read(8)
                if not header.startswith(b"%PDF"):
                    raise ValueError("Invalid PDF header")
            results["valid"] += 1
            results["files"].append({"name": pdf_path.name, "size": size, "valid": True})
        except Exception as e:
            results["errors"].append(str(e))
            results["files"].append({"name": pdf_path.name, "error": str(e), "valid": False})

    print(f"Result: {results['valid']}/{results['total']} PDFs valid")
    return results


if __name__ == "__main__":
    generated = generate_all_pdfs()
    verify_pdfs()
    print()
    print("The PDFs can now be used for the OV-RAG benchmark.")
    print("Ground truth: contract_ground_truth.json")
