"""Validation agent: deterministic rules produce issues; routing combines them
with confidence to decide approve vs. human review.

Design: rules are the PRIMARY gate (trustworthy, testable, free). Confidence is
a secondary backstop. The LLM (see reasoning.py) only narrates the outcome.
"""
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.confidence import overall_confidence
from app.config import get_settings
from app.models import Invoice
from app.schemas import (
    ExtractedInvoice,
    InvoiceStatus,
    ProcessedInvoice,
    ValidationIssue,
)

settings = get_settings()

# Tolerance for floating-point money comparisons (1 cent).
MONEY_TOL = Decimal("0.01")


def _to_decimal(value) -> Decimal | None:
    """Best-effort numeric coercion; None if not parseable."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def check_missing_fields(inv: ExtractedInvoice) -> list[ValidationIssue]:
    """Critical fields must have a non-empty value."""
    issues = []
    required = {
        "vendor_name": inv.vendor_name,
        "invoice_number": inv.invoice_number,
        "total": inv.total,
        "invoice_date": inv.invoice_date,
    }
    for name, field in required.items():
        if field is None or field.value is None or field.value == "":
            issues.append(ValidationIssue(
                rule="missing_field", severity="error",
                message=f"Required field '{name}' is missing.",
            ))
    return issues


def check_math(inv: ExtractedInvoice) -> list[ValidationIssue]:
    """Line items sum to subtotal; subtotal + tax = total."""
    issues = []

    # Line items sum to subtotal.
    line_sum = Decimal("0")
    line_ok = True
    for li in inv.line_items:
        amt = _to_decimal(li.amount.value)
        if amt is None:
            line_ok = False
            break
        line_sum += amt

    subtotal = _to_decimal(inv.subtotal.value)
    if line_ok and subtotal is not None and inv.line_items:
        if abs(line_sum - subtotal) > MONEY_TOL:
            issues.append(ValidationIssue(
                rule="math_check", severity="error",
                message=f"Line items sum to {line_sum}, but subtotal is {subtotal}.",
            ))

    # Reconciliation: subtotal + tax + other_charges must equal total.
    # If it doesn't, SOMETHING affecting the total wasn't captured (a fee, a
    # discount, a field we don't model) — flag for human review rather than
    # trying to guess what was missed.
    tax = _to_decimal(inv.tax.value) if inv.tax else Decimal("0")
    other = _to_decimal(inv.other_charges.value) if inv.other_charges else Decimal("0")
    if tax is None:
        tax = Decimal("0")
    if other is None:
        other = Decimal("0")
    total = _to_decimal(inv.total.value)
    if subtotal is not None and total is not None:
        expected = subtotal + tax + other
        if abs(expected - total) > MONEY_TOL:
            issues.append(ValidationIssue(
                rule="reconciliation", severity="error",
                message=f"Totals do not reconcile: subtotal {subtotal} + tax {tax} "
                        f"+ other_charges {other} = {expected}, but total is {total}. "
                        f"An unaccounted charge may not have been extracted.",
            ))
    return issues


def check_duplicate(inv: ExtractedInvoice, db: Session) -> list[ValidationIssue]:
    """Flag if an invoice with the same number + vendor already exists."""
    issues = []
    inv_no = inv.invoice_number.value if inv.invoice_number else None
    vendor = inv.vendor_name.value if inv.vendor_name else None
    if not inv_no:
        return issues
    stmt = select(Invoice).where(Invoice.invoice_number == str(inv_no))
    existing = db.execute(stmt).scalars().first()
    if existing is not None:
        issues.append(ValidationIssue(
            rule="duplicate", severity="error",
            message=f"Invoice '{inv_no}' from '{vendor}' already exists "
                    f"(id={existing.id}).",
        ))
    return issues


def validate(inv: ExtractedInvoice, db: Session) -> ProcessedInvoice:
    """Run all rules, compute confidence, decide routing."""
    issues: list[ValidationIssue] = []
    issues += check_missing_fields(inv)
    issues += check_math(inv)
    issues += check_duplicate(inv, db)

    conf = overall_confidence(inv)
    has_errors = any(i.severity == "error" for i in issues)
    below_threshold = conf < settings.confidence_threshold

    # Routing: approve only if NO errors AND confidence clears the bar.
    if has_errors or below_threshold:
        status = InvoiceStatus.needs_review
    else:
        status = InvoiceStatus.approved

    return ProcessedInvoice(
        extracted=inv,
        overall_confidence=conf,
        issues=issues,
        status=status,
        agent_reasoning="",  # filled by the LLM narrator (reasoning.py)
    )