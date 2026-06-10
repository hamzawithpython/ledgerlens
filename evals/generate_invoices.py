"""Generate synthetic invoice PDFs + exact ground-truth JSON for eval.

Run: python evals/generate_invoices.py
All vendors/data are fictional — safe for a public repo.
"""
import json
import random
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

SAMPLES_DIR = Path(__file__).parent / "samples"
GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"

VENDORS = [
    "Northwind Supplies Ltd", "Acme Office Co", "BlueRiver Logistics",
    "Pinecrest Hardware", "Lumen Cloud Services", "Harbor Print Works",
    "Summit Catering Group", "Vertex Stationery",
]
ITEMS = [
    ("A4 Paper Ream", Decimal("4.50")), ("Toner Cartridge", Decimal("78.00")),
    ("USB-C Cable", Decimal("9.99")), ("Desk Lamp", Decimal("32.00")),
    ("Cloud Storage 1TB", Decimal("15.00")), ("Courier Service", Decimal("25.50")),
    ("Notebook Pack", Decimal("12.75")), ("Wireless Mouse", Decimal("21.00")),
]
CURRENCY = "USD"
TAX_RATE = Decimal("0.10")


def money(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def make_invoice(idx: int, seed: int) -> dict:
    random.seed(seed)
    vendor = VENDORS[idx % len(VENDORS)]
    inv_no = f"INV-2026-{1000 + idx}"
    inv_date = f"2026-0{random.randint(1, 6)}-{random.randint(10, 28)}"

    chosen = random.sample(ITEMS, k=random.randint(2, 4))
    line_items = []
    subtotal = Decimal("0.00")
    for desc, price in chosen:
        qty = random.randint(1, 5)
        amount = money(price * qty)
        subtotal += amount
        line_items.append({
            "description": desc, "quantity": float(qty),
            "unit_price": float(price), "amount": float(amount),
        })
    subtotal = money(subtotal)
    tax = money(subtotal * TAX_RATE)
    total = money(subtotal + tax)

    return {
        "file": f"invoice_{idx:02d}.pdf",
        "vendor_name": vendor,
        "invoice_number": inv_no,
        "invoice_date": inv_date,
        "currency": CURRENCY,
        "line_items": line_items,
        "subtotal": float(subtotal),
        "tax": float(tax),
        "total": float(total),
    }


def render_pdf(inv: dict, path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    w, h = letter
    y = h - inch

    c.setFont("Helvetica-Bold", 20)
    c.drawString(inch, y, inv["vendor_name"])
    c.setFont("Helvetica", 10)
    y -= 0.5 * inch
    c.drawString(inch, y, "INVOICE")
    c.drawRightString(w - inch, y, f"Invoice #: {inv['invoice_number']}")
    y -= 0.25 * inch
    c.drawRightString(w - inch, y, f"Date: {inv['invoice_date']}")

    y -= 0.6 * inch
    c.setFont("Helvetica-Bold", 10)
    c.drawString(inch, y, "Description")
    c.drawString(4 * inch, y, "Qty")
    c.drawString(5 * inch, y, "Unit Price")
    c.drawRightString(w - inch, y, "Amount")
    c.line(inch, y - 4, w - inch, y - 4)

    c.setFont("Helvetica", 10)
    for li in inv["line_items"]:
        y -= 0.3 * inch
        c.drawString(inch, y, li["description"])
        c.drawString(4 * inch, y, str(int(li["quantity"])))
        c.drawString(5 * inch, y, f"{inv['currency']} {li['unit_price']:.2f}")
        c.drawRightString(w - inch, y, f"{inv['currency']} {li['amount']:.2f}")

    y -= 0.5 * inch
    c.line(3.5 * inch, y + 10, w - inch, y + 10)
    c.drawRightString(5.5 * inch, y, "Subtotal:")
    c.drawRightString(w - inch, y, f"{inv['currency']} {inv['subtotal']:.2f}")
    y -= 0.25 * inch
    c.drawRightString(5.5 * inch, y, "Tax (10%):")
    c.drawRightString(w - inch, y, f"{inv['currency']} {inv['tax']:.2f}")
    y -= 0.25 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(5.5 * inch, y, "TOTAL:")
    c.drawRightString(w - inch, y, f"{inv['currency']} {inv['total']:.2f}")

    c.showPage()
    c.save()


def main() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    truth = []
    for idx in range(8):
        inv = make_invoice(idx, seed=42 + idx)
        render_pdf(inv, SAMPLES_DIR / inv["file"])
        truth.append(inv)
    GROUND_TRUTH.write_text(json.dumps(truth, indent=2), encoding="utf-8")
    print(f"Generated {len(truth)} invoices in {SAMPLES_DIR}")
    print(f"Ground truth written to {GROUND_TRUTH}")


if __name__ == "__main__":
    main()