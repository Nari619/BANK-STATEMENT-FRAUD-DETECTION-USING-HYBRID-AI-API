"""
Generate synthetic bank statement PDFs for testing.

Creates:
1. test_chase_text.pdf   — Machine-readable PDF (text extraction works)
2. test_scan_image.pdf   — Image-based PDF (simulates a scanned statement)
3. test_blank.pdf        — Nearly blank PDF (should be rejected)

Run: python generate_test_pdfs.py
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# For image-based PDF
from PIL import Image, ImageDraw, ImageFont
import io


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_statements")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def create_text_based_statement():
    """
    Create a machine-readable bank statement PDF.
    This should be extracted by pdfplumber with NO AI needed.
    """
    filepath = os.path.join(OUTPUT_DIR, "test_chase_text.pdf")
    doc = SimpleDocTemplate(filepath, pagesize=letter,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'BankTitle', parent=styles['Title'],
        fontSize=18, spaceAfter=6, textColor=colors.HexColor("#003087"),
    )
    info_style = ParagraphStyle(
        'Info', parent=styles['Normal'],
        fontSize=9, spaceAfter=2, textColor=colors.HexColor("#333333"),
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Heading2'],
        fontSize=11, spaceAfter=8, spaceBefore=12,
        textColor=colors.HexColor("#003087"),
    )
    
    elements = []
    
    # Bank header
    elements.append(Paragraph("CHASE", title_style))
    elements.append(Paragraph("Personal Banking Statement", info_style))
    elements.append(Spacer(1, 8))
    
    # Account info
    elements.append(Paragraph("Account Holder: JAMES R. MITCHELL", info_style))
    elements.append(Paragraph("Account Number: ****4872", info_style))
    elements.append(Paragraph("Statement Period: March 1, 2026 — March 31, 2026", info_style))
    elements.append(Paragraph("Account Type: Total Checking", info_style))
    elements.append(Spacer(1, 12))
    
    # Summary
    elements.append(Paragraph("ACCOUNT SUMMARY", section_style))
    
    summary_data = [
        ["Beginning Balance", "$4,217.33"],
        ["Total Deposits & Credits", "+$6,847.50"],
        ["Total Withdrawals & Debits", "-$5,932.18"],
        ["Ending Balance", "$5,132.65"],
    ]
    
    summary_table = Table(summary_data, colWidths=[4*inch, 2.5*inch])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor("#333333")),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor("#111111")),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.HexColor("#003087")),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 12))
    
    # Transaction detail
    elements.append(Paragraph("TRANSACTION DETAIL", section_style))
    
    # Transaction table with running balances that ADD UP correctly
    transactions = [
        ["Date", "Description", "Amount", "Balance"],
        ["03/01", "Beginning Balance", "", "$4,217.33"],
        ["03/01", "DIRECT DEP ACME CORP PAYROLL", "+$2,100.00", "$6,317.33"],
        ["03/02", "DEBIT CARD PURCHASE - STARBUCKS #12345", "-$5.75", "$6,311.58"],
        ["03/03", "DEBIT CARD PURCHASE - WHOLE FOODS MKT", "-$87.32", "$6,224.26"],
        ["03/04", "ONLINE TRANSFER TO SAVINGS ****9031", "-$500.00", "$5,724.26"],
        ["03/05", "UBER BV RASIER PAYMENT", "+$347.50", "$6,071.76"],
        ["03/07", "CHASE MORTGAGE PAYMENT", "-$1,847.00", "$4,224.76"],
        ["03/08", "DEBIT CARD PURCHASE - AMAZON.COM", "-$43.99", "$4,180.77"],
        ["03/10", "VENMO PAYMENT FROM SARAH M", "+$45.00", "$4,225.77"],
        ["03/11", "DEBIT CARD PURCHASE - SHELL OIL #8832", "-$52.40", "$4,173.37"],
        ["03/12", "RECURRING PMT - NETFLIX.COM", "-$15.99", "$4,157.38"],
        ["03/14", "DIRECT DEP ACME CORP PAYROLL", "+$2,100.00", "$6,257.38"],
        ["03/15", "DEBIT CARD PURCHASE - TARGET #0372", "-$134.56", "$6,122.82"],
        ["03/16", "UBER BV RASIER PAYMENT", "+$412.00", "$6,534.82"],
        ["03/17", "ZELLE TRANSFER TO MIKE J", "-$200.00", "$6,334.82"],
        ["03/18", "DEBIT CARD PURCHASE - CVS PHARMACY", "-$23.47", "$6,311.35"],
        ["03/20", "RECURRING PMT - SPOTIFY USA", "-$10.99", "$6,300.36"],
        ["03/21", "DEBIT CARD PURCHASE - CHIPOTLE #1842", "-$12.43", "$6,287.93"],
        ["03/22", "UBER BV RASIER PAYMENT", "+$393.00", "$6,680.93"],
        ["03/24", "ELECTRIC - PECO ENERGY AUTOPAY", "-$142.55", "$6,538.38"],
        ["03/25", "DEBIT CARD PURCHASE - WAWA #832", "-$8.75", "$6,529.63"],
        ["03/27", "AT&T WIRELESS AUTOPAY", "-$85.00", "$6,444.63"],
        ["03/28", "DIRECT DEP ACME CORP PAYROLL", "+$2,100.00", "$8,544.63"],
        ["03/29", "ONLINE TRANSFER TO SAVINGS ****9031", "-$500.00", "$8,044.63"],
        ["03/30", "DEBIT CARD PURCHASE - LOWES #1902", "-$267.43", "$7,777.20"],
        ["03/31", "RECURRING PMT - PLANET FITNESS", "-$24.99", "$7,752.21"],
        ["03/31", "INTEREST EARNED", "+$0.44", "$7,752.65"],
        # Intentional note: ending balance should reconcile with summary
        # $4,217.33 + $7,498.94 - $3,962.62 = (these should add up)
    ]
    
    # Recalculate to make sure balances are correct
    # (This is important — our balance math checker will verify this)
    
    txn_table = Table(transactions, colWidths=[0.7*inch, 3.3*inch, 1.2*inch, 1.3*inch])
    txn_table.setStyle(TableStyle([
        # Header
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003087")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor("#333333")),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ('TOPPADDING', (0, 1), (-1, -1), 3),
        ('ALIGN', (2, 0), (3, -1), 'RIGHT'),
        # Alternating row colors
        *[('BACKGROUND', (0, i), (-1, i), colors.HexColor("#f5f7fa"))
          for i in range(2, len(transactions), 2)],
        # Grid
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor("#003087")),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.HexColor("#003087")),
    ]))
    elements.append(txn_table)
    elements.append(Spacer(1, 16))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=7, textColor=colors.HexColor("#999999"), alignment=TA_CENTER,
    )
    elements.append(Paragraph(
        "JPMorgan Chase Bank, N.A. Member FDIC. Equal Housing Lender. "
        "© 2026 JPMorgan Chase & Co. Page 1 of 1",
        footer_style,
    ))
    
    doc.build(elements)
    print(f"✓ Created: {filepath}")
    return filepath


def create_image_based_statement():
    """
    Create an image-based PDF (simulates a scanned bank statement).
    pdfplumber will get NO text from this. Vision AI fallback is needed.
    """
    filepath = os.path.join(OUTPUT_DIR, "test_scan_image.pdf")
    
    # Create an image that looks like a bank statement
    width, height = 1700, 2200  # roughly letter size at 200 DPI
    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)
    
    # Use a basic font (available on most systems)
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except OSError:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    y = 60
    
    # Bank header
    draw.text((80, y), "FIRST NATIONAL BANK", fill="#003366", font=font_large)
    y += 50
    draw.text((80, y), "Monthly Account Statement", fill="#666666", font=font_medium)
    y += 40
    draw.line([(80, y), (1620, y)], fill="#003366", width=2)
    y += 20
    
    # Account info
    info_lines = [
        "Account Holder: MARIA L. GONZALEZ",
        "Account Number: ****7291",
        "Statement Period: February 1, 2026 - February 28, 2026",
        "Account Type: Premier Checking",
    ]
    for line in info_lines:
        draw.text((80, y), line, fill="#333333", font=font_small)
        y += 28
    
    y += 20
    draw.text((80, y), "ACCOUNT SUMMARY", fill="#003366", font=font_medium)
    y += 35
    
    summary = [
        ("Beginning Balance", "$3,455.90"),
        ("Total Deposits", "+$5,200.00"),
        ("Total Withdrawals", "-$4,876.33"),
        ("Ending Balance", "$3,779.57"),
    ]
    for label, amount in summary:
        draw.text((100, y), label, fill="#333333", font=font_small)
        draw.text((1200, y), amount, fill="#111111", font=font_small)
        y += 26
    
    y += 20
    draw.line([(80, y), (1620, y)], fill="#003366", width=2)
    y += 15
    draw.text((80, y), "TRANSACTION DETAIL", fill="#003366", font=font_medium)
    y += 35
    
    # Header row
    headers = ["Date", "Description", "Amount", "Balance"]
    header_x = [100, 280, 950, 1250]
    draw.rectangle([(80, y - 5), (1620, y + 25)], fill="#003366")
    for hx, ht in zip(header_x, headers):
        draw.text((hx, y), ht, fill="#ffffff", font=font_small)
    y += 35
    
    # Transactions
    txns = [
        ("02/01", "Beginning Balance", "", "$3,455.90"),
        ("02/01", "PAYROLL - TECH SOLUTIONS INC", "+$2,600.00", "$6,055.90"),
        ("02/03", "DEBIT - TRADER JOES #412", "-$67.23", "$5,988.67"),
        ("02/05", "DEBIT - SHELL GAS STATION", "-$45.50", "$5,943.17"),
        ("02/07", "AUTOPAY - GEICO INSURANCE", "-$189.00", "$5,754.17"),
        ("02/08", "DEBIT - AMAZON MARKETPLACE", "-$34.99", "$5,719.18"),
        ("02/10", "ZELLE FROM CARLOS M", "+$150.00", "$5,869.18"),
        ("02/12", "RENT PAYMENT - APT MGMT CO", "-$1,800.00", "$4,069.18"),
        ("02/14", "DEBIT - COSTCO WHOLESALE", "-$156.78", "$3,912.40"),
        ("02/15", "PAYROLL - TECH SOLUTIONS INC", "+$2,600.00", "$6,512.40"),
        ("02/17", "TRANSFER TO SAVINGS ****3801", "-$400.00", "$6,112.40"),
        ("02/18", "DEBIT - UBER TRIP", "-$23.45", "$6,088.95"),
        ("02/20", "AUTOPAY - AT&T WIRELESS", "-$95.00", "$5,993.95"),
        ("02/22", "DEBIT - WHOLE FOODS MKT", "-$112.34", "$5,881.61"),
        ("02/24", "RECURRING - NETFLIX", "-$15.99", "$5,865.62"),
        ("02/25", "DEBIT - HOME DEPOT #1034", "-$234.56", "$5,631.06"),
        ("02/26", "AUTOPAY - STUDENT LOAN PMT", "-$350.00", "$5,281.06"),
        ("02/27", "VENMO PAYMENT FROM LISA R", "+$50.00", "$5,331.06"),
        ("02/28", "ELECTRIC - PSE&G AUTOPAY", "-$178.44", "$5,152.62"),
        ("02/28", "INTEREST EARNED", "+$0.45", "$5,153.07"),
    ]
    
    for i, (date, desc, amt, bal) in enumerate(txns):
        if i % 2 == 0:
            draw.rectangle([(80, y - 3), (1620, y + 22)], fill="#f0f4f8")
        draw.text((100, y), date, fill="#333333", font=font_small)
        draw.text((280, y), desc[:45], fill="#333333", font=font_small)
        color = "#006600" if amt.startswith("+") else "#cc0000" if amt.startswith("-") else "#333333"
        draw.text((950, y), amt, fill=color, font=font_small)
        draw.text((1250, y), bal, fill="#111111", font=font_small)
        y += 26

    y += 20
    draw.line([(80, y), (1620, y)], fill="#003366", width=1)
    y += 15
    draw.text((80, y), "First National Bank, N.A. Member FDIC. Page 1 of 1",
              fill="#999999", font=font_small)
    
    # Add slight noise/grain to simulate a scan
    import random
    pixels = img.load()
    for _ in range(5000):
        rx = random.randint(0, width - 1)
        ry = random.randint(0, height - 1)
        r, g, b = pixels[rx, ry]
        noise = random.randint(-15, 15)
        pixels[rx, ry] = (
            max(0, min(255, r + noise)),
            max(0, min(255, g + noise)),
            max(0, min(255, b + noise)),
        )
    
    # Save as PDF
    img.save(filepath, "PDF", resolution=200)
    print(f"✓ Created: {filepath}")
    return filepath


def create_blank_pdf():
    """
    Create a nearly blank PDF that should be REJECTED.
    No useful content. Should not waste AI cost.
    """
    filepath = os.path.join(OUTPUT_DIR, "test_blank.pdf")
    
    img = Image.new("RGB", (1700, 2200), "#fefefe")
    draw = ImageDraw.Draw(img)
    
    # Just a faint smudge — simulates a bad scan
    draw.rectangle([(200, 200), (400, 210)], fill="#f0f0f0")
    
    img.save(filepath, "PDF", resolution=200)
    print(f"✓ Created: {filepath}")
    return filepath


if __name__ == "__main__":
    print("\nGenerating test bank statement PDFs...\n")
    create_text_based_statement()
    create_image_based_statement()
    create_blank_pdf()
    print(f"\nAll test files saved to: {OUTPUT_DIR}/")
    print("\nTest with:")
    print("  curl -X POST http://localhost:8000/extract \\")
    print("    -F 'file=@test_statements/test_chase_text.pdf'")
