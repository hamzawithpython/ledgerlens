"""LLM narrator: turns deterministic validation outcomes into a human-readable
summary for the review queue. The LLM does NOT make routing decisions — it only
explains decisions the rule engine already made.
"""
from app.config import get_settings
from app.providers import get_client
from app.schemas import ProcessedInvoice

settings = get_settings()

_NARRATOR_SYSTEM = """You are an accounts-payable assistant. Given an invoice's
validation outcome, write ONE concise sentence (max 40 words) explaining why it
was approved or flagged for review. Be specific about which checks passed or
failed. Do not invent issues not present in the data. Plain text only."""


def narrate(processed: ProcessedInvoice) -> str:
    """Generate a one-sentence reasoning summary. Falls back to a rule-based
    summary if the LLM call fails (so the pipeline never breaks on narration)."""
    issue_lines = [f"- [{i.severity}] {i.rule}: {i.message}" for i in processed.issues]
    issues_text = "\n".join(issue_lines) if issue_lines else "No issues found."

    prompt = (
        f"Status: {processed.status.value}\n"
        f"Overall confidence: {processed.overall_confidence:.2f}\n"
        f"Confidence threshold: {settings.confidence_threshold}\n"
        f"Validation issues:\n{issues_text}"
    )

    try:
        client = get_client()
        resp = client.chat.completions.create(
            model=settings.extraction_model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": _NARRATOR_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        # Deterministic fallback — never let narration crash the pipeline.
        if processed.status.value == "approved":
            return "Auto-approved: all validation checks passed and confidence cleared the threshold."
        reasons = ", ".join(i.rule for i in processed.issues) or "low confidence"
        return f"Flagged for review: {reasons}."