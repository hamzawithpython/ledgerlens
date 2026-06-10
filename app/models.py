"""SQLAlchemy ORM models."""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Core extracted fields (denormalized for easy querying + duplicate checks)
    vendor_name: Mapped[str | None] = mapped_column(String(255))
    invoice_number: Mapped[str | None] = mapped_column(String(128), index=True)
    invoice_date: Mapped[str | None] = mapped_column(String(32))
    total: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(8))

    # Routing outcome
    status: Mapped[str] = mapped_column(String(32), index=True)
    overall_confidence: Mapped[float] = mapped_column(Float)
    agent_reasoning: Mapped[str | None] = mapped_column(Text)

    # Full structured payloads, kept as JSON for audit + the review UI
    extracted_json: Mapped[dict] = mapped_column(JSON)
    issues_json: Mapped[list] = mapped_column(JSON, default=list)