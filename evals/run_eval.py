"""Evaluate extraction accuracy + routing accuracy against ground truth.

Run: python evals/run_eval.py

Reports:
  - Field-level accuracy: fraction of scalar fields extracted correctly.
  - Routing accuracy: fraction of invoices routed to the expected status.
All numbers are on synthetic test invoices with known-correct values.
"""
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.db import SessionLocal
from app.extraction import extract_invoice
from app.validation_agent import validate

GROUND_TRUTH = Path(__file__).parent / "ground_truth.json"
SAMPLES_DIR = Path(__file__).parent / "samples"
MONEY_TOL = Decimal("0.01")


def _num_eq(a, b) -> bool:
    """Numeric equality within a cent."""
    try:
        return abs(Decimal(str(a)) - Decimal(str(b))) <= MONEY_TOL
    except (InvalidOperation, ValueError, TypeError):
        return False


def _str_eq(a, b) -> bool:
    if a is None or b is None:
        return a == b
    return str(a).strip().lower() == str(b).strip().lower()


def _field_value(fc):
    """Pull .value from a FieldConfidence-like dict, or None."""
    if fc is None:
        return None
    return fc.get("value") if isinstance(fc, dict) else getattr(fc, "value", None)


def score_invoice(extracted, truth: dict) -> tuple[int, int, list[str]]:
    """Compare extracted scalar fields to ground truth. Returns (correct, total, misses)."""
    ex = extracted.model_dump(mode="json")
    correct = 0
    total = 0
    misses = []

    # Scalar string fields.
    for field in ("vendor_name", "invoice_number", "invoice_date", "currency"):
        total += 1
        got = _field_value(ex.get(field))
        want = truth.get(field)
        if _str_eq(got, want):
            correct += 1
        else:
            misses.append(f"{field}: got {got!r}, want {want!r}")

    # Scalar numeric fields.
    for field in ("subtotal", "tax", "other_charges", "total"):
        total += 1
        got = _field_value(ex.get(field))
        want = truth.get(field)
        if _num_eq(got, want):
            correct += 1
        else:
            misses.append(f"{field}: got {got!r}, want {want!r}")

    # Line-item count (a proxy for line-item extraction completeness).
    total += 1
    got_n = len(ex.get("line_items") or [])
    want_n = len(truth.get("line_items") or [])
    if got_n == want_n:
        correct += 1
    else:
        misses.append(f"line_item_count: got {got_n}, want {want_n}")

    return correct, total, misses


def main() -> None:
    truth_data = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    db = SessionLocal()

    # Clean slate so the duplicate rule doesn't flag invoices against stale rows
    # from prior runs — the eval measures invoice-intrinsic routing, not DB history.
    from app.models import Invoice
    db.query(Invoice).delete()
    db.commit()

    total_correct = 0
    total_fields = 0
    routing_correct = 0
    n = len(truth_data)

    print(f"Evaluating {n} synthetic invoices\n" + "=" * 60)

    try:
        for truth in truth_data:
            pdf = SAMPLES_DIR / truth["file"]
            extracted = extract_invoice(pdf)                 # cached after first run
            processed = validate(extracted, db)

            c, t, misses = score_invoice(extracted, truth)
            total_correct += c
            total_fields += t

            expected_status = truth.get("expect_status", "approved")
            got_status = processed.status.value
            routed_ok = (got_status == expected_status)
            if routed_ok:
                routing_correct += 1

            flag = "OK " if routed_ok else "XX "
            print(f"{flag}{truth['file']}: fields {c}/{t} | "
                  f"routed={got_status} (expected {expected_status})")
            for m in misses:
                print(f"      miss: {m}")
    finally:
        db.close()

    field_acc = 100 * total_correct / total_fields if total_fields else 0
    routing_acc = 100 * routing_correct / n if n else 0

    print("=" * 60)
    print(f"Field-level accuracy: {field_acc:.1f}%  ({total_correct}/{total_fields} fields)")
    print(f"Routing accuracy:     {routing_acc:.1f}%  ({routing_correct}/{n} invoices)")
    print("\n(All metrics on synthetic test invoices with known-correct values.)")


if __name__ == "__main__":
    main()