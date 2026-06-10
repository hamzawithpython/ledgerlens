"""End-to-end check: extract -> validate -> narrate -> store, on a clean and a broken invoice."""
from app.db import SessionLocal
from app.extraction import extract_invoice
from app.reasoning import narrate
from app.store import store_invoice, list_invoices
from app.validation_agent import validate

db = SessionLocal()
try:
    for pdf in ["evals/samples/invoice_00.pdf", "evals/samples/invoice_06.pdf", "evals/samples/invoice_07.pdf"]:
        extracted = extract_invoice(pdf)
        processed = validate(extracted, db)
        processed.agent_reasoning = narrate(processed)
        row = store_invoice(processed, db)
        print(f"{pdf} -> id={row.id} status={row.status} conf={row.overall_confidence:.2f}")
        print(f"   reasoning: {row.agent_reasoning}")

    print("\nReview queue (needs_review):")
    for r in list_invoices(db, status="needs_review"):
        print(f"  id={r.id} {r.vendor_name} {r.invoice_number} total={r.total}")
finally:
    db.close()