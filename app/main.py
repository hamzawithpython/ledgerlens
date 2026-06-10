"""LedgerLens FastAPI application: upload, list/queue, detail, resolve."""
import shutil
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.db import Base, engine, get_db
from app.schemas import InvoiceDetail, InvoiceStatus, InvoiceSummary
from app.pipeline import process_pdf
from app.store import get_invoice, list_invoices, resolve_review

# Create tables on startup if they don't exist (idempotent).
Base.metadata.create_all(engine)

app = FastAPI(title="LedgerLens", description="Agentic invoice processing with confidence-gated human review.")

UI_DIR = Path(__file__).parent / "ui"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/invoices", response_model=InvoiceDetail)
async def upload_invoice(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a PDF invoice; runs the full pipeline and returns the processed result."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Persist the upload to a temp file (pdf2image needs a path).
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        row = process_pdf(tmp_path, db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return InvoiceDetail.model_validate(row)


@app.get("/invoices", response_model=list[InvoiceSummary])
def get_invoices(status: str | None = None, db: Session = Depends(get_db)):
    """List all invoices, or filter by status (e.g. ?status=needs_review for the queue)."""
    if status is not None and status not in {s.value for s in InvoiceStatus}:
        raise HTTPException(status_code=400, detail=f"Invalid status '{status}'.")
    rows = list_invoices(db, status=status)
    return [InvoiceSummary.model_validate(r) for r in rows]


@app.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
def get_invoice_detail(invoice_id: int, db: Session = Depends(get_db)):
    row = get_invoice(invoice_id, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return InvoiceDetail.model_validate(row)


@app.post("/invoices/{invoice_id}/resolve", response_model=InvoiceDetail)
def resolve_invoice(invoice_id: int, approve: bool, db: Session = Depends(get_db)):
    """Human review decision: approve=true clears it, approve=false rejects it."""
    row = resolve_review(invoice_id, approve, db)
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return InvoiceDetail.model_validate(row)


# Serve the UI (built in the next phase). Mounted last so it doesn't shadow API routes.
if UI_DIR.exists():
    app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")