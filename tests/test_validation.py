"""Unit tests for the deterministic validation rules. No LLM, no DB needed for math/missing."""
from unittest.mock import MagicMock

from app.schemas import ExtractedInvoice, FieldConfidence, LineItem
from app.validation_agent import check_math, check_missing_fields, validate


def _fc(value, conf=1.0):
    return FieldConfidence(value=value, confidence=conf)


def _line(desc, qty, price, amount):
    return LineItem(
        description=_fc(desc), quantity=_fc(qty),
        unit_price=_fc(price), amount=_fc(amount),
    )


def _good_invoice() -> ExtractedInvoice:
    return ExtractedInvoice(
        vendor_name=_fc("Acme Co"),
        invoice_number=_fc("INV-001"),
        invoice_date=_fc("2026-01-15"),
        line_items=[_line("Widget", 2, 10.0, 20.0), _line("Gadget", 1, 30.0, 30.0)],
        subtotal=_fc(50.0),
        tax=_fc(5.0),
        other_charges=_fc(0.0),
        total=_fc(55.0),
        currency=_fc("USD"),
    )


def test_clean_invoice_has_no_math_issues():
    assert check_math(_good_invoice()) == []


def test_bad_subtotal_flagged():
    inv = _good_invoice()
    inv.subtotal = _fc(999.0)
    issues = check_math(inv)
    assert any(i.rule == "math_check" for i in issues)


def test_bad_total_flagged():
    inv = _good_invoice()
    inv.total = _fc(999.0)
    issues = check_math(inv)
    assert any(i.rule == "reconciliation" for i in issues)


def test_missing_vendor_flagged():
    inv = _good_invoice()
    inv.vendor_name = _fc(None, conf=0.0)
    issues = check_missing_fields(inv)
    assert any("vendor_name" in i.message for i in issues)


def test_clean_invoice_approved():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.first.return_value = None  # no dup
    result = validate(_good_invoice(), db)
    assert result.status.value == "approved"
    assert result.overall_confidence == 1.0


def test_math_error_routes_to_review():
    db = MagicMock()
    db.execute.return_value.scalars.return_value.first.return_value = None
    inv = _good_invoice()
    inv.total = _fc(999.0)
    result = validate(inv, db)
    assert result.status.value == "needs_review"

def test_reconciles_with_other_charges():
    """subtotal 50 + tax 5 + shipping 10 = total 65 should pass."""
    inv = _good_invoice()
    inv.other_charges = _fc(10.0)
    inv.total = _fc(65.0)
    issues = check_math(inv)
    assert not any(i.rule == "reconciliation" for i in issues)


def test_unaccounted_gap_flagged():
    """If total exceeds subtotal+tax+other, an unextracted charge is flagged."""
    inv = _good_invoice()
    inv.other_charges = _fc(0.0)
    inv.total = _fc(75.0)   # 50 + 5 + 0 = 55, but total says 75 -> 20 unaccounted
    issues = check_math(inv)
    assert any(i.rule == "reconciliation" for i in issues)