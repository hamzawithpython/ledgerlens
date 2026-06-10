"""PDF invoice -> rasterize -> vision LLM -> structured ExtractedInvoice, with disk cache."""
import base64
import hashlib
import io
import json
import re
from pathlib import Path

from pdf2image import convert_from_path

from app.config import get_settings
from app.prompts import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT
from app.providers import get_client
from app.schemas import ExtractedInvoice

settings = get_settings()
CACHE_DIR = Path(__file__).parent.parent / "evals" / "cache"


def _file_hash(pdf_path: Path) -> str:
    """Hash file bytes so identical content reuses the cache regardless of name."""
    return hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:16]


def pdf_first_page_to_b64(pdf_path: str | Path, dpi: int = 150) -> str:
    """Rasterize the first page of a PDF to a base64-encoded PNG."""
    images = convert_from_path(str(pdf_path), dpi=dpi, first_page=1, last_page=1)
    if not images:
        raise ValueError(f"No pages rendered from {pdf_path}")
    buf = io.BytesIO()
    images[0].save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` fences some models add despite instructions."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def _wrap_field(v):
    """Coerce a raw value into the {value, confidence} shape if it isn't already."""
    if isinstance(v, dict) and "value" in v:
        return v  # already {value, confidence}
    return {"value": v, "confidence": 1.0}


def _normalize_line_items(data: dict) -> dict:
    """Scout returns line-item fields either flat or nested; normalize to nested.

    Some responses give {"description": "X", "quantity": 5, ...} (flat) and others
    give {"description": {"value": "X", "confidence": 1.0}, ...} (nested). We
    coerce every line-item field to the nested {value, confidence} shape so the
    ExtractedInvoice schema validates regardless of which the model emitted.
    """
    items = data.get("line_items")
    if not isinstance(items, list):
        return data
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # Pull a per-line confidence if the model put one at the item level (flat shape).
        line_conf = item.get("confidence", 1.0)
        fixed = {}
        for key in ("description", "quantity", "unit_price", "amount"):
            raw = item.get(key)
            if isinstance(raw, dict) and "value" in raw:
                fixed[key] = raw
            else:
                fixed[key] = {"value": raw, "confidence": line_conf}
        normalized.append(fixed)
    data["line_items"] = normalized
    return data

def extract_invoice(pdf_path: str | Path, use_cache: bool = True) -> ExtractedInvoice:
    """Extract a single-page invoice PDF into validated Pydantic. Caches by file hash."""
    pdf_path = Path(pdf_path)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{_file_hash(pdf_path)}.json"

    if use_cache and cache_file.exists():
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        return ExtractedInvoice.model_validate(data)

    img_b64 = pdf_first_page_to_b64(pdf_path)
    client = get_client()

    response = client.chat.completions.create(
        model=settings.extraction_model,
        temperature=0,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                    },
                ],
            },
        ],
    )

    raw = _strip_fences(response.choices[0].message.content)
    data = json.loads(raw)
    data = _normalize_line_items(data)
    invoice = ExtractedInvoice.model_validate(data)

    # Cache the validated result so we never re-spend quota on identical input.
    cache_file.write_text(invoice.model_dump_json(indent=2), encoding="utf-8")
    return invoice