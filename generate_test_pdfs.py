"""
generate_test_pdfs.py
Generates 10 Test PDFs for OV-RAG Benchmark

PDFs:
- 9 consistent contracts (various loan types)
- 1 error contract (Contract_010_ERROR_CLASH.pdf) with intentional clash

The Clash in Contract 010:
- A natural person (John Smith) is listed as lender for a Commercial Loan
- This violates: NaturalPerson ⊥ LegalEntity (FinancialInstitution is LegalEntity)
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY


@dataclass
class LoanContract:
    """Represents a loan contract."""
    contract_id: str
    loan_type: str
    loan_type_description: str
    borrower_name: str
    borrower_type: str  # "NaturalPerson" or "LegalEntity"
    lender_name: str
    lender_type: str  # "FinancialInstitution" or "NaturalPerson" (for clash)
    principal_amount: float
    currency: str
    interest_rate: float
    term_months: int
    purpose: str
    collateral: Optional[str] = None
    is_secured: bool = False
    special_notes: Optional[str] = None


# Contract data for the 10 test PDFs
CONTRACTS = [
    # 001: Consumer Loan
    LoanContract(
        contract_id="001",
        loan_type="ConsumerLoan",
        loan_type_description="Consumer Loan Agreement",
        borrower_name="Anna Miller",
        borrower_type="NaturalPerson",
        lender_name="First National Bank",
        lender_type="FinancialInstitution",
        principal_amount=15000.00,
        currency="USD",
        interest_rate=5.9,
        term_months=48,
        purpose="Vehicle purchase financing",
        is_secured=False,
    ),
    # 002: Commercial Loan
    LoanContract(
        contract_id="002",
        loan_type="CommercialLoan",
        loan_type_description="Commercial Loan Agreement",
        borrower_name="TechStart Inc.",
        borrower_type="LegalEntity",
        lender_name="Commerce Bank of America",
        lender_type="FinancialInstitution",
        principal_amount=250000.00,
        currency="USD",
        interest_rate=4.5,
        term_months=60,
        purpose="Expansion of production facilities",
        collateral="Business equipment and machinery",
        is_secured=True,
    ),
    # 003: Mortgage
    LoanContract(
        contract_id="003",
        loan_type="Mortgage",
        loan_type_description="Mortgage Loan Agreement",
        borrower_name="The Weber Family",
        borrower_type="NaturalPerson",
        lender_name="Wells Fargo Home Mortgage",
        lender_type="FinancialInstitution",
        principal_amount=450000.00,
        currency="USD",
        interest_rate=3.2,
        term_months=360,
        purpose="Purchase of residential property",
        collateral="First lien on property at 123 Main Street, Springfield, IL 62701",
        is_secured=True,
    ),
    # 004: Student Loan
    LoanContract(
        contract_id="004",
        loan_type="StudentLoan",
        loan_type_description="Student Loan Agreement",
        borrower_name="Emily Johnson",
        borrower_type="NaturalPerson",
        lender_name="Sallie Mae",
        lender_type="FinancialInstitution",
        principal_amount=30000.00,
        currency="USD",
        interest_rate=4.5,
        term_months=120,
        purpose="Financing of Master's degree in Computer Science",
        is_secured=False,
    ),
    # 005: Subsidized Student Loan
    LoanContract(
        contract_id="005",
        loan_type="SubsidizedStudentLoan",
        loan_type_description="Federal Subsidized Student Loan",
        borrower_name="Thomas Brown",
        borrower_type="NaturalPerson",
        lender_name="U.S. Department of Education",
        lender_type="FinancialInstitution",
        principal_amount=25000.00,
        currency="USD",
        interest_rate=0.0,
        term_months=240,
        purpose="Government-subsidized medical school education",
        is_secured=False,
        special_notes="Interest-free loan under Federal Student Aid program. Repayment begins 6 months after graduation.",
    ),
    # 006: Green Loan
    LoanContract(
        contract_id="006",
        loan_type="GreenLoan",
        loan_type_description="Green Loan / Sustainability Financing",
        borrower_name="SolarTech Corporation",
        borrower_type="LegalEntity",
        lender_name="Green Investment Bank",
        lender_type="FinancialInstitution",
        principal_amount=500000.00,
        currency="USD",
        interest_rate=3.0,
        term_months=180,
        purpose="Installation of 500kWp solar photovoltaic system",
        collateral="The solar installation equipment",
        is_secured=True,
        special_notes="Loan meets EU Taxonomy criteria for sustainable investments. Eligible for green bond certification.",
    ),
    # 007: Card Account (Credit Card)
    LoanContract(
        contract_id="007",
        loan_type="CardAccount",
        loan_type_description="Credit Card Account Agreement (Revolving Credit)",
        borrower_name="Michael Davis",
        borrower_type="NaturalPerson",
        lender_name="American Express",
        lender_type="FinancialInstitution",
        principal_amount=10000.00,  # Credit limit
        currency="USD",
        interest_rate=18.9,
        term_months=0,  # Open-ended
        purpose="Revolving credit line for everyday purchases",
        is_secured=False,
        special_notes="Open-End Credit with minimum monthly payment of 2% of outstanding balance. This is an OpenEndCredit facility.",
    ),
    # 008: Complex Commercial Loan (Syndicated)
    LoanContract(
        contract_id="008",
        loan_type="CommercialLoan",
        loan_type_description="Syndicated Commercial Loan Agreement",
        borrower_name="ACME Industries LLC",
        borrower_type="LegalEntity",
        lender_name="Syndicate: JPMorgan Chase (Lead), Bank of America, Citibank",
        lender_type="FinancialInstitution",
        principal_amount=5000000.00,
        currency="USD",
        interest_rate=3.8,
        term_months=84,
        purpose="Acquisition of Competitor Corp. and business integration",
        collateral="Shares in the acquired company",
        is_secured=True,
        special_notes="Syndicated loan facility with JPMorgan Chase as Lead Arranger. Governed by LMA standard terms.",
    ),
    # 009: Mortgage Refinance
    LoanContract(
        contract_id="009",
        loan_type="Mortgage",
        loan_type_description="Mortgage Refinancing Agreement",
        borrower_name="Dr. Sarah Wilson",
        borrower_type="NaturalPerson",
        lender_name="Quicken Loans",
        lender_type="FinancialInstitution",
        principal_amount=320000.00,
        currency="USD",
        interest_rate=2.8,
        term_months=240,
        purpose="Refinancing of existing mortgage loan",
        collateral="First lien on condominium at 456 Park Avenue, New York, NY 10022",
        is_secured=True,
        special_notes="Refinancing of existing loan from Bank of America (remaining balance: $318,500). Cash-out refinance with improved terms.",
    ),
    # 010: ERROR CLASH - Natural Person as Lender for Commercial Loan
    LoanContract(
        contract_id="010_ERROR_CLASH",
        loan_type="CommercialLoan",
        loan_type_description="Commercial Loan Agreement",
        borrower_name="StartupXYZ Inc.",
        borrower_type="LegalEntity",
        lender_name="John Smith",  # CLASH! Natural Person as Lender
        lender_type="NaturalPerson",  # CLASH!
        principal_amount=100000.00,
        currency="USD",
        interest_rate=8.0,
        term_months=36,
        purpose="Seed financing for technology startup",
        is_secured=False,
        special_notes="WARNING: This contract contains a logical error! "
                      "John Smith (natural person, DOB: March 15, 1985) is listed as the lender. "
                      "This violates the ontology rule that lenders for Commercial Loans "
                      "must be Financial Institutions (LegalEntity), not Natural Persons.",
    ),
]


def generate_contract_pdf(contract: LoanContract, output_dir: str = "data") -> str:
    """
    Generates a PDF file for a loan contract.

    Args:
        contract: The loan contract
        output_dir: Output directory

    Returns:
        Path to the generated PDF file
    """
    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Filename
    filename = f"Contract_{contract.contract_id}_{contract.loan_type}.pdf"
    filepath = os.path.join(output_dir, filename)

    # Create PDF
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )

    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='ContractTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=30,
    ))
    styles.add(ParagraphStyle(
        name='ContractSection',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=15,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name='ContractBody',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name='Warning',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.red,
        backColor=colors.lightyellow,
        borderPadding=10,
    ))

    # Content
    content = []

    # Title
    content.append(Paragraph(
        f"LOAN AGREEMENT<br/><br/>{contract.loan_type_description}",
        styles['ContractTitle']
    ))
    content.append(Spacer(1, 20))

    # Contract number and date
    today = datetime.now()
    content.append(Paragraph(
        f"<b>Contract Number:</b> LA-2025-{contract.contract_id}<br/>"
        f"<b>Date:</b> {today.strftime('%B %d, %Y')}",
        styles['ContractBody']
    ))
    content.append(Spacer(1, 20))

    # Parties
    content.append(Paragraph("Section 1: Parties to the Agreement", styles['ContractSection']))

    # Lender
    lender_desc = f"<b>LENDER:</b><br/>{contract.lender_name}"
    if contract.lender_type == "FinancialInstitution":
        lender_desc += "<br/>(Financial Institution)"
    else:
        lender_desc += "<br/>(Natural Person)"  # This is the clash!

    content.append(Paragraph(lender_desc, styles['ContractBody']))
    content.append(Spacer(1, 10))

    # Borrower
    borrower_desc = f"<b>BORROWER:</b><br/>{contract.borrower_name}"
    if contract.borrower_type == "LegalEntity":
        borrower_desc += "<br/>(Legal Entity / Corporation)"
    else:
        borrower_desc += "<br/>(Natural Person / Individual)"

    content.append(Paragraph(borrower_desc, styles['ContractBody']))
    content.append(Spacer(1, 10))

    # Loan Details
    content.append(Paragraph("Section 2: Loan Terms and Conditions", styles['ContractSection']))

    # Table with loan data
    term_display = f"{contract.term_months} months" if contract.term_months > 0 else "Open-ended (revolving)"
    maturity_date = (today + timedelta(days=contract.term_months * 30)).strftime('%B %d, %Y') if contract.term_months > 0 else "N/A (Open-ended)"

    data = [
        ["Loan Type:", contract.loan_type_description],
        ["Ontology Class:", contract.loan_type],
        ["Principal Amount:", f"{contract.currency} {contract.principal_amount:,.2f}"],
        ["Interest Rate (p.a.):", f"{contract.interest_rate}%"],
        ["Term:", term_display],
        ["Maturity Date:", maturity_date],
        ["Purpose:", contract.purpose],
        ["Security:", "Yes (Secured Loan)" if contract.is_secured else "No (Unsecured Loan)"],
    ]

    if contract.collateral:
        data.append(["Collateral:", contract.collateral])

    table = Table(data, colWidths=[4*cm, 12*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    content.append(table)
    content.append(Spacer(1, 20))

    # Repayment Terms
    content.append(Paragraph("Section 3: Repayment Terms", styles['ContractSection']))

    if contract.term_months > 0:
        monthly_payment = (contract.principal_amount * (1 + contract.interest_rate/100 * contract.term_months/12)) / contract.term_months
        content.append(Paragraph(
            f"Repayment shall be made in {contract.term_months} monthly installments. "
            f"The estimated monthly payment is approximately {contract.currency} {monthly_payment:,.2f} "
            f"(including interest). A detailed amortization schedule will be provided separately.",
            styles['ContractBody']
        ))
    else:
        content.append(Paragraph(
            "This is a revolving credit facility (Open-End Credit). "
            "The Borrower may draw upon the credit limit as needed and must make "
            "minimum monthly payments as specified in the account terms.",
            styles['ContractBody']
        ))

    content.append(Spacer(1, 10))

    # Special Provisions
    if contract.special_notes:
        content.append(Paragraph("Section 4: Special Provisions", styles['ContractSection']))

        # Use warning style for clash contract
        if "ERROR" in contract.contract_id or "CLASH" in contract.contract_id:
            content.append(Paragraph(
                f"WARNING: {contract.special_notes}",
                styles['Warning']
            ))
        else:
            content.append(Paragraph(contract.special_notes, styles['ContractBody']))

        content.append(Spacer(1, 10))

    # General Terms
    content.append(Paragraph("Section 5: General Terms", styles['ContractSection']))
    content.append(Paragraph(
        "This Agreement shall be governed by and construed in accordance with the laws "
        "of the State of New York. Any amendments or modifications must be in writing. "
        "If any provision is found to be unenforceable, the remaining provisions shall "
        "continue in full force and effect.",
        styles['ContractBody']
    ))
    content.append(Spacer(1, 30))

    # Signatures
    content.append(Paragraph("Section 6: Signatures", styles['ContractSection']))

    sig_data = [
        ["_" * 30, "_" * 30],
        [contract.lender_name, contract.borrower_name],
        ["(Lender)", "(Borrower)"],
        ["Date: ____________", "Date: ____________"],
    ]

    sig_table = Table(sig_data, colWidths=[8*cm, 8*cm])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
    ]))
    content.append(sig_table)

    # Footer for clash document
    if "ERROR" in contract.contract_id or "CLASH" in contract.contract_id:
        content.append(Spacer(1, 30))
        content.append(Paragraph(
            "=" * 50 + "<br/>"
            "<b>TEST DOCUMENT FOR OV-RAG BENCHMARK</b><br/>"
            "This document intentionally contains a logical inconsistency:<br/>"
            f"- {contract.lender_name} is classified as a Natural Person<br/>"
            "- Commercial Loans require an institutional lender (Financial Institution)<br/>"
            "- Expected result: Ontology validator detects INCONSISTENCY<br/>"
            "- Violated axiom: NaturalPerson disjointWith LegalEntity<br/>"
            "=" * 50,
            styles['Warning']
        ))

    # Generate PDF
    doc.build(content)

    return filepath


def generate_all_pdfs(output_dir: str = "data") -> list:
    """
    Generates all 10 test PDFs.

    Args:
        output_dir: Output directory

    Returns:
        List of generated file paths
    """
    print("=" * 70)
    print("PDF GENERATOR: 10 Test Contracts for OV-RAG Benchmark")
    print("=" * 70)
    print()

    generated_files = []

    for contract in CONTRACTS:
        try:
            filepath = generate_contract_pdf(contract, output_dir)
            generated_files.append(filepath)

            clash_marker = " [CLASH]" if "ERROR" in contract.contract_id else ""
            print(f"  OK  {os.path.basename(filepath)}{clash_marker}")

        except Exception as e:
            print(f"  ERR {contract.contract_id}: {e}")

    print()
    print("=" * 70)
    print(f"COMPLETE: {len(generated_files)}/{len(CONTRACTS)} PDFs generated")
    print(f"Output directory: {output_dir}/")
    print("=" * 70)

    return generated_files


def verify_pdfs(pdf_dir: str = "data") -> dict:
    """
    Verifies the generated PDFs.

    Args:
        pdf_dir: Directory containing the PDFs

    Returns:
        Verification result
    """
    print()
    print("=" * 70)
    print("PDF VERIFICATION")
    print("=" * 70)

    results = {
        "total": 0,
        "valid": 0,
        "errors": [],
        "files": []
    }

    pdf_files = list(Path(pdf_dir).glob("Contract_*.pdf"))
    results["total"] = len(pdf_files)

    for pdf_path in sorted(pdf_files):
        try:
            # Check file size
            size = pdf_path.stat().st_size
            if size < 1000:  # Less than 1KB is suspicious
                raise ValueError(f"File too small: {size} bytes")

            # Check PDF header
            with open(pdf_path, 'rb') as f:
                header = f.read(8)
                if not header.startswith(b'%PDF'):
                    raise ValueError("Invalid PDF header")

            results["valid"] += 1
            results["files"].append({
                "name": pdf_path.name,
                "size": size,
                "valid": True
            })
            print(f"  OK  {pdf_path.name} ({size:,} bytes)")

        except Exception as e:
            results["errors"].append(str(e))
            results["files"].append({
                "name": pdf_path.name,
                "error": str(e),
                "valid": False
            })
            print(f"  ERR {pdf_path.name}: {e}")

    print()
    print(f"Result: {results['valid']}/{results['total']} PDFs valid")

    return results


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    # Generate all PDFs
    generated = generate_all_pdfs()

    # Verify
    verify_pdfs()

    print()
    print("The PDFs can now be used for the OV-RAG benchmark.")
    print("Contract_010_ERROR_CLASH_CommercialLoan.pdf contains the intentional clash.")
