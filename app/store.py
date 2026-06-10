"""Persistence + human-review queue operations over the invoices table."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Invoice
from app.schemas import InvoiceStatus, ProcessedInvoice


def _num(field) -> float | None:
    """Coerce a FieldConfidence value to float for the flat column, or None."""
    if field is None or field.value is None:
        return None
    try:
        return float(field.value)
    except (TypeError, ValueError):
        return None


def _str(field) -> str | None:
    if field is None or field.value is None:
        return None
    return str(field.value)


def store_invoice(processed: ProcessedInvoice, db: Session) -> Invoice:
    """Insert a processed invoice. Flat columns for querying + JSON blobs for detail."""
    ex = processed.extracted
    row = Invoice(
        vendor_name=_str(ex.vendor_name),
        invoice_number=_str(ex.invoice_number),
        invoice_date=_str(ex.invoice_date),
        total=_num(ex.total),
        currency=_str(ex.currency),
        status=processed.status.value,
        overall_confidence=processed.overall_confidence,
        agent_reasoning=processed.agent_reasoning,
        extracted_json=ex.model_dump(mode="json"),
        issues_json=[i.model_dump() for i in processed.issues],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_invoices(db: Session, status: str | None = None) -> list[Invoice]:
    """List invoices, optionally filtered by status (e.g. the review queue)."""
    stmt = select(Invoice).order_by(Invoice.created_at.desc())
    if status:
        stmt = stmt.where(Invoice.status == status)
    return list(db.execute(stmt).scalars().all())


def get_invoice(invoice_id: int, db: Session) -> Invoice | None:
    return db.get(Invoice, invoice_id)


def resolve_review(invoice_id: int, approve: bool, db: Session) -> Invoice | None:
    """Human decision on a flagged invoice: approve it or reject it."""
    row = db.get(Invoice, invoice_id)
    if row is None:
        return None
    row.status = InvoiceStatus.approved.value if approve else InvoiceStatus.rejected.value
    db.commit()
    db.refresh(row)
    return row