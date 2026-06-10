"""Pydantic schemas — the data contract across extraction, validation, and storage."""
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class InvoiceStatus(str, Enum):
    approved = "approved"
    needs_review = "needs_review"
    rejected = "rejected"


class FieldConfidence(BaseModel):
    """A single extracted field with the model's self-reported confidence."""
    value: str | float | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class LineItem(BaseModel):
    description: FieldConfidence
    quantity: FieldConfidence
    unit_price: FieldConfidence
    amount: FieldConfidence


class ExtractedInvoice(BaseModel):
    """Raw structured output from the extraction model."""
    vendor_name: FieldConfidence
    invoice_number: FieldConfidence
    invoice_date: FieldConfidence          # ISO string at extraction; parsed downstream
    due_date: FieldConfidence | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: FieldConfidence
    tax: FieldConfidence | None = None
    total: FieldConfidence
    currency: FieldConfidence


class ValidationIssue(BaseModel):
    rule: str                              # "math_check" | "duplicate" | "missing_field"
    severity: str                          # "error" | "warning"
    message: str


class ProcessedInvoice(BaseModel):
    """Final result after extraction + validation + routing."""
    extracted: ExtractedInvoice
    overall_confidence: float = Field(ge=0.0, le=1.0)
    issues: list[ValidationIssue] = Field(default_factory=list)
    status: InvoiceStatus
    agent_reasoning: str


# ---- API response models ----

class InvoiceSummary(BaseModel):
    """Compact row for list/queue views."""
    id: int
    vendor_name: str | None
    invoice_number: str | None
    invoice_date: str | None
    total: float | None
    currency: str | None
    status: str
    overall_confidence: float

    model_config = {"from_attributes": True}


class InvoiceDetail(InvoiceSummary):
    """Full record for the review screen — includes extracted payload + issues."""
    agent_reasoning: str | None
    extracted_json: dict
    issues_json: list

    model_config = {"from_attributes": True}