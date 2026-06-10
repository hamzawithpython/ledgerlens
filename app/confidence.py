"""Confidence scoring: derive a trustworthy overall score from extracted fields.

Model self-reported confidence is poorly calibrated (Llama 4 Scout returns ~1.0
on nearly everything), so we (a) take the MIN over critical fields rather than a
mean — one weak critical field should sink the score — and (b) force confidence
to 0 for fields whose value is missing/null, regardless of what the model claims.
"""
from app.schemas import ExtractedInvoice, FieldConfidence

# Fields that must be present and correct for an invoice to auto-approve.
CRITICAL_FIELDS = ("vendor_name", "invoice_number", "total")


def _effective_confidence(field: FieldConfidence | None) -> float:
    """Confidence we actually trust: 0 if value is missing, else the reported score."""
    if field is None or field.value is None or field.value == "":
        return 0.0
    return float(field.confidence)


def overall_confidence(inv: ExtractedInvoice) -> float:
    """Min effective confidence across critical fields."""
    scores = [_effective_confidence(getattr(inv, name)) for name in CRITICAL_FIELDS]
    return min(scores) if scores else 0.0