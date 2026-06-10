"""Orchestrates the full processing pipeline for an uploaded invoice PDF."""
from pathlib import Path

from sqlalchemy.orm import Session

from app.extraction import extract_invoice
from app.models import Invoice
from app.reasoning import narrate
from app.store import store_invoice
from app.validation_agent import validate


def process_pdf(pdf_path: str | Path, db: Session) -> Invoice:
    """Run extract -> validate -> narrate -> store; return the persisted row."""
    extracted = extract_invoice(pdf_path)
    processed = validate(extracted, db)
    processed.agent_reasoning = narrate(processed)
    return store_invoice(processed, db)