"""
generate_test_pdfs.py
Generiert 10 Test-PDFs für das OV-RAG Benchmark

PDFs:
- 9 konsistente Verträge (verschiedene Darlehenstypen)
- 1 fehlerhafter Vertrag (Vertrag_010_ERROR_CLASH.pdf) mit absichtlichem Clash

Der Clash in Vertrag 010:
- Eine natürliche Person (Max Müller) wird als Kreditgeber für einen Commercial Loan angegeben
- Dies verletzt: NaturalPerson ⊥ LegalEntity (FinancialInstitution ist LegalEntity)
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import random

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY


@dataclass
class LoanContract:
    """Repräsentiert einen Kreditvertrag."""
    contract_id: str
    loan_type: str
    loan_type_specific: str
    borrower_name: str
    borrower_type: str  # "NaturalPerson" oder "LegalEntity"
    lender_name: str
    lender_type: str  # "FinancialInstitution" oder "NaturalPerson" (für Clash)
    principal_amount: float
    interest_rate: float
    term_months: int
    purpose: str
    collateral: Optional[str] = None
    is_secured: bool = False
    special_notes: Optional[str] = None


# Vertragsdaten für die 10 Test-PDFs
CONTRACTS = [
    # 001: Consumer Loan (Verbraucherkredit)
    LoanContract(
        contract_id="001",
        loan_type="ConsumerLoan",
        loan_type_specific="Verbraucherkredit",
        borrower_name="Anna Schmidt",
        borrower_type="NaturalPerson",
        lender_name="Deutsche Kreditbank AG",
        lender_type="FinancialInstitution",
        principal_amount=15000.00,
        interest_rate=5.9,
        term_months=48,
        purpose="Anschaffung eines Fahrzeugs",
        is_secured=False,
    ),
    # 002: Commercial Loan (Gewerbekredit)
    LoanContract(
        contract_id="002",
        loan_type="CommercialLoan",
        loan_type_specific="Gewerbekredit",
        borrower_name="TechStart GmbH",
        borrower_type="LegalEntity",
        lender_name="Commerzbank AG",
        lender_type="FinancialInstitution",
        principal_amount=250000.00,
        interest_rate=4.5,
        term_months=60,
        purpose="Erweiterung der Produktionskapazitäten",
        collateral="Betriebsausstattung",
        is_secured=True,
    ),
    # 003: Mortgage (Hypothek)
    LoanContract(
        contract_id="003",
        loan_type="Mortgage",
        loan_type_specific="Hypothekendarlehen",
        borrower_name="Familie Weber",
        borrower_type="NaturalPerson",
        lender_name="Sparkasse München",
        lender_type="FinancialInstitution",
        principal_amount=450000.00,
        interest_rate=3.2,
        term_months=300,
        purpose="Erwerb einer Immobilie",
        collateral="Grundschuld auf das Objekt Hauptstraße 42, 80331 München",
        is_secured=True,
    ),
    # 004: Student Loan (Studienkredit)
    LoanContract(
        contract_id="004",
        loan_type="StudentLoan",
        loan_type_specific="Studienkredit",
        borrower_name="Lena Hoffmann",
        borrower_type="NaturalPerson",
        lender_name="KfW Bankengruppe",
        lender_type="FinancialInstitution",
        principal_amount=30000.00,
        interest_rate=2.5,
        term_months=120,
        purpose="Finanzierung des Masterstudiums Informatik",
        is_secured=False,
    ),
    # 005: Subsidized Student Loan (Geförderter Studienkredit)
    LoanContract(
        contract_id="005",
        loan_type="SubsidizedStudentLoan",
        loan_type_specific="Geförderter Studienkredit (BAföG-Bankdarlehen)",
        borrower_name="Thomas Bauer",
        borrower_type="NaturalPerson",
        lender_name="KfW Bankengruppe",
        lender_type="FinancialInstitution",
        principal_amount=25000.00,
        interest_rate=0.0,
        term_months=240,
        purpose="Staatlich gefördertes Studium der Medizin",
        is_secured=False,
        special_notes="Zinsfreies Darlehen gemäß BAföG §18c. Rückzahlung beginnt 5 Jahre nach Studienende.",
    ),
    # 006: Green Loan (Grüner Kredit)
    LoanContract(
        contract_id="006",
        loan_type="GreenLoan",
        loan_type_specific="Grüner Kredit / Nachhaltigkeitskredit",
        borrower_name="SolarTech AG",
        borrower_type="LegalEntity",
        lender_name="GLS Bank",
        lender_type="FinancialInstitution",
        principal_amount=500000.00,
        interest_rate=3.0,
        term_months=180,
        purpose="Installation einer Photovoltaikanlage mit 500kWp Leistung",
        collateral="Die zu errichtende Solaranlage",
        is_secured=True,
        special_notes="Kredit erfüllt die EU-Taxonomie-Kriterien für nachhaltige Investitionen.",
    ),
    # 007: Card Account (Kreditkarte)
    LoanContract(
        contract_id="007",
        loan_type="CardAccount",
        loan_type_specific="Kreditkartenkonto (Revolving Credit)",
        borrower_name="Michael Fischer",
        borrower_type="NaturalPerson",
        lender_name="American Express Germany GmbH",
        lender_type="FinancialInstitution",
        principal_amount=10000.00,  # Kreditrahmen
        interest_rate=14.9,
        term_months=0,  # Unbefristet
        purpose="Revolvierende Kreditlinie für alltägliche Ausgaben",
        is_secured=False,
        special_notes="Open-End Credit mit monatlicher Mindestrate von 2% des Saldos.",
    ),
    # 008: Commercial Loan Complex (Komplexer Gewerbekredit)
    LoanContract(
        contract_id="008",
        loan_type="CommercialLoan",
        loan_type_specific="Syndizierter Gewerbekredit",
        borrower_name="ACME Industries GmbH & Co. KG",
        borrower_type="LegalEntity",
        lender_name="Konsortium: Deutsche Bank AG (Lead), BNP Paribas, UniCredit",
        lender_type="FinancialInstitution",
        principal_amount=5000000.00,
        interest_rate=3.8,
        term_months=84,
        purpose="Akquisition der Competitor Corp. und Integration",
        collateral="Anteile an der zu erwerbenden Gesellschaft",
        is_secured=True,
        special_notes="Syndizierter Kredit mit Deutsche Bank AG als Lead Arranger.",
    ),
    # 009: Mortgage Refinance (Umschuldung)
    LoanContract(
        contract_id="009",
        loan_type="Mortgage",
        loan_type_specific="Hypotheken-Umschuldung",
        borrower_name="Dr. Sarah Klein",
        borrower_type="NaturalPerson",
        lender_name="ING-DiBa AG",
        lender_type="FinancialInstitution",
        principal_amount=320000.00,
        interest_rate=2.8,
        term_months=240,
        purpose="Umschuldung eines bestehenden Hypothekendarlehens",
        collateral="Grundschuld auf Eigentumswohnung Berliner Str. 15, 10115 Berlin",
        is_secured=True,
        special_notes="Ablösung des bestehenden Darlehens bei der Volksbank (Restschuld: 318.500 EUR).",
    ),
    # 010: ERROR CLASH - Natural Person als Lender für Commercial Loan
    LoanContract(
        contract_id="010_ERROR_CLASH",
        loan_type="CommercialLoan",
        loan_type_specific="Gewerbekredit",
        borrower_name="StartupXYZ GmbH",
        borrower_type="LegalEntity",
        lender_name="Max Müller",  # CLASH! Natural Person als Lender
        lender_type="NaturalPerson",  # CLASH!
        principal_amount=100000.00,
        interest_rate=8.0,
        term_months=36,
        purpose="Seed-Finanzierung für Technologie-Startup",
        is_secured=False,
        special_notes="ACHTUNG: Dieser Vertrag enthält einen logischen Fehler! "
                      "Max Müller (natürliche Person, geb. 15.03.1985) tritt als Kreditgeber auf. "
                      "Dies widerspricht der Ontologie-Regel, dass Kreditgeber für Commercial Loans "
                      "Finanzinstitute (LegalEntity) sein müssen.",
    ),
]


def generate_contract_pdf(contract: LoanContract, output_dir: str = "data") -> str:
    """
    Generiert eine PDF-Datei für einen Kreditvertrag.

    Args:
        contract: Der Kreditvertrag
        output_dir: Ausgabeverzeichnis

    Returns:
        Pfad zur generierten PDF-Datei
    """
    # Stelle sicher, dass das Ausgabeverzeichnis existiert
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Dateiname
    filename = f"Vertrag_{contract.contract_id}_{contract.loan_type}.pdf"
    filepath = os.path.join(output_dir, filename)

    # PDF erstellen
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

    # Inhalt
    content = []

    # Titel
    content.append(Paragraph(
        f"KREDITVERTRAG<br/><br/>{contract.loan_type_specific}",
        styles['ContractTitle']
    ))
    content.append(Spacer(1, 20))

    # Vertragsnummer und Datum
    today = datetime.now()
    content.append(Paragraph(
        f"<b>Vertragsnummer:</b> KV-2025-{contract.contract_id}<br/>"
        f"<b>Datum:</b> {today.strftime('%d.%m.%Y')}",
        styles['ContractBody']
    ))
    content.append(Spacer(1, 20))

    # Vertragsparteien
    content.append(Paragraph("§1 Vertragsparteien", styles['ContractSection']))

    # Kreditgeber
    lender_desc = f"<b>Kreditgeber:</b><br/>{contract.lender_name}"
    if contract.lender_type == "FinancialInstitution":
        lender_desc += "<br/>(Finanzinstitut im Sinne des KWG)"
    else:
        lender_desc += "<br/>(Natürliche Person)"  # Dies ist der Clash!

    content.append(Paragraph(lender_desc, styles['ContractBody']))
    content.append(Spacer(1, 10))

    # Kreditnehmer
    borrower_desc = f"<b>Kreditnehmer:</b><br/>{contract.borrower_name}"
    if contract.borrower_type == "LegalEntity":
        borrower_desc += "<br/>(Juristische Person / Unternehmen)"
    else:
        borrower_desc += "<br/>(Natürliche Person)"

    content.append(Paragraph(borrower_desc, styles['ContractBody']))
    content.append(Spacer(1, 10))

    # Kreditdetails
    content.append(Paragraph("§2 Kreditdetails", styles['ContractSection']))

    # Tabelle mit Kreditdaten
    term_display = f"{contract.term_months} Monate" if contract.term_months > 0 else "Unbefristet"
    maturity_date = (today + timedelta(days=contract.term_months * 30)).strftime('%d.%m.%Y') if contract.term_months > 0 else "Unbefristet"

    data = [
        ["Kredittyp:", contract.loan_type_specific],
        ["Ontologie-Klasse:", contract.loan_type],
        ["Darlehenssumme:", f"{contract.principal_amount:,.2f} EUR"],
        ["Zinssatz (p.a.):", f"{contract.interest_rate}%"],
        ["Laufzeit:", term_display],
        ["Fälligkeitsdatum:", maturity_date],
        ["Verwendungszweck:", contract.purpose],
        ["Besicherung:", "Ja (Secured Loan)" if contract.is_secured else "Nein (Unsecured Loan)"],
    ]

    if contract.collateral:
        data.append(["Sicherheit:", contract.collateral])

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

    # Rückzahlungsbedingungen
    content.append(Paragraph("§3 Rückzahlungsbedingungen", styles['ContractSection']))

    if contract.term_months > 0:
        monthly_payment = (contract.principal_amount * (1 + contract.interest_rate/100 * contract.term_months/12)) / contract.term_months
        content.append(Paragraph(
            f"Die Rückzahlung erfolgt in {contract.term_months} monatlichen Raten. "
            f"Die geschätzte monatliche Rate beträgt ca. {monthly_payment:,.2f} EUR "
            f"(inkl. Zinsen). Der genaue Tilgungsplan wird dem Kreditnehmer separat übermittelt.",
            styles['ContractBody']
        ))
    else:
        content.append(Paragraph(
            "Es handelt sich um einen revolvierenden Kredit (Open-End Credit). "
            "Der Kreditnehmer kann den Kreditrahmen flexibel nutzen und muss monatlich "
            "mindestens den Mindestbetrag zurückzahlen.",
            styles['ContractBody']
        ))

    content.append(Spacer(1, 10))

    # Besondere Bestimmungen
    if contract.special_notes:
        content.append(Paragraph("§4 Besondere Bestimmungen", styles['ContractSection']))

        # Wenn es der Clash-Vertrag ist, verwende Warnung-Style
        if "ERROR" in contract.contract_id or "CLASH" in contract.contract_id:
            content.append(Paragraph(
                f"⚠️ WARNUNG: {contract.special_notes}",
                styles['Warning']
            ))
        else:
            content.append(Paragraph(contract.special_notes, styles['ContractBody']))

        content.append(Spacer(1, 10))

    # Schlussbestimmungen
    content.append(Paragraph("§5 Schlussbestimmungen", styles['ContractSection']))
    content.append(Paragraph(
        "Dieser Vertrag unterliegt deutschem Recht. Änderungen und Ergänzungen "
        "bedürfen der Schriftform. Sollten einzelne Bestimmungen unwirksam sein, "
        "bleibt die Wirksamkeit der übrigen Bestimmungen unberührt.",
        styles['ContractBody']
    ))
    content.append(Spacer(1, 30))

    # Unterschriften
    content.append(Paragraph("§6 Unterschriften", styles['ContractSection']))

    sig_data = [
        ["_" * 30, "_" * 30],
        [contract.lender_name, contract.borrower_name],
        ["(Kreditgeber)", "(Kreditnehmer)"],
        [f"Ort, Datum: ____________", f"Ort, Datum: ____________"],
    ]

    sig_table = Table(sig_data, colWidths=[8*cm, 8*cm])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
    ]))
    content.append(sig_table)

    # Footer für Clash-Dokument
    if "ERROR" in contract.contract_id or "CLASH" in contract.contract_id:
        content.append(Spacer(1, 30))
        content.append(Paragraph(
            "═" * 50 + "<br/>"
            "<b>TESTDOKUMENT FÜR OV-RAG BENCHMARK</b><br/>"
            "Dieses Dokument enthält absichtlich einen logischen Widerspruch:<br/>"
            f"• {contract.lender_name} ist als natürliche Person klassifiziert<br/>"
            "• Commercial Loans erfordern jedoch einen institutionellen Kreditgeber<br/>"
            "• Erwartetes Ergebnis: Ontologie-Validator erkennt INCONSISTENCY<br/>"
            "═" * 50,
            styles['Warning']
        ))

    # PDF generieren
    doc.build(content)

    return filepath


def generate_all_pdfs(output_dir: str = "data") -> list:
    """
    Generiert alle 10 Test-PDFs.

    Args:
        output_dir: Ausgabeverzeichnis

    Returns:
        Liste der generierten Dateipfade
    """
    print("=" * 70)
    print("PDF-GENERATOR: 10 Test-Verträge für OV-RAG")
    print("=" * 70)
    print()

    generated_files = []

    for contract in CONTRACTS:
        try:
            filepath = generate_contract_pdf(contract, output_dir)
            generated_files.append(filepath)

            clash_marker = " ⚠️  [CLASH]" if "ERROR" in contract.contract_id else ""
            print(f"  ✓ {os.path.basename(filepath)}{clash_marker}")

        except Exception as e:
            print(f"  ✗ Fehler bei {contract.contract_id}: {e}")

    print()
    print("=" * 70)
    print(f"FERTIG: {len(generated_files)}/{len(CONTRACTS)} PDFs generiert")
    print(f"Ausgabeverzeichnis: {output_dir}/")
    print("=" * 70)

    return generated_files


def verify_pdfs(pdf_dir: str = "data") -> dict:
    """
    Verifiziert die generierten PDFs.

    Args:
        pdf_dir: Verzeichnis mit den PDFs

    Returns:
        Verifizierungsergebnis
    """
    print()
    print("=" * 70)
    print("PDF-VERIFIZIERUNG")
    print("=" * 70)

    results = {
        "total": 0,
        "valid": 0,
        "errors": [],
        "files": []
    }

    pdf_files = list(Path(pdf_dir).glob("Vertrag_*.pdf"))
    results["total"] = len(pdf_files)

    for pdf_path in sorted(pdf_files):
        try:
            # Prüfe Dateigröße
            size = pdf_path.stat().st_size
            if size < 1000:  # Weniger als 1KB ist verdächtig
                raise ValueError(f"Datei zu klein: {size} bytes")

            # Prüfe PDF-Header
            with open(pdf_path, 'rb') as f:
                header = f.read(8)
                if not header.startswith(b'%PDF'):
                    raise ValueError("Kein gültiger PDF-Header")

            results["valid"] += 1
            results["files"].append({
                "name": pdf_path.name,
                "size": size,
                "valid": True
            })
            print(f"  ✓ {pdf_path.name} ({size:,} bytes)")

        except Exception as e:
            results["errors"].append(str(e))
            results["files"].append({
                "name": pdf_path.name,
                "error": str(e),
                "valid": False
            })
            print(f"  ✗ {pdf_path.name}: {e}")

    print()
    print(f"Ergebnis: {results['valid']}/{results['total']} PDFs gültig")

    return results


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    # Generiere alle PDFs
    generated = generate_all_pdfs()

    # Verifiziere
    verify_pdfs()

    print()
    print("Die PDFs können jetzt für das OV-RAG Benchmark verwendet werden.")
    print("Vertrag_010_ERROR_CLASH_CommercialLoan.pdf enthält den absichtlichen Clash.")
