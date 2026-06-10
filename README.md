# LedgerLens

> Agentic invoice processing with confidence-gated human review.

LedgerLens ingests PDF invoices, extracts structured fields with per-field confidence using a vision LLM, runs an agentic validation pass (math checks, duplicate detection, missing-field checks), and routes results: high-confidence clean invoices are auto-approved into Postgres, while low-confidence or rule-failing invoices are flagged into a human-review queue surfaced in a simple web UI.

## Problem
Accounts-payable teams manually key invoice data and eyeball it for errors ? slow and error-prone. LedgerLens automates the clean cases and escalates only the uncertain ones to a human.

## Architecture
_(diagram added in a later phase)_

## Tech Stack
- **Extraction:** OpenAI vision (gpt-4o-mini), structured outputs
- **Schema/validation:** Pydantic 2
- **Backend:** FastAPI
- **DB:** Postgres (SQLAlchemy)
- **Infra:** Docker, Cloud Run
- **Evals:** custom field-accuracy + clean-pass-rate script

## Setup
_(filled in once runnable)_

## Live Demo
_(Cloud Run link added at deploy)_

## Technical Decisions
- _Why vision LLM over a PDF parser:_ handles arbitrary invoice layouts and emits structured fields + confidence in one call.
- _Confidence thresholding:_ overall confidence = min of critical fields (vendor, invoice number, total); below 0.85 ? human review.

## What Didn't Work / Lessons
- LLM self-reported confidence is poorly calibrated (Llama 4 Scout returns ~1.0 on nearly everything). Rule-based validation (math/duplicate/missing-field checks) is therefore the primary routing gate; model confidence is a secondary signal, with missing fields forced to 0.
- PowerShell here-strings are fragile for config files: a malformed @'...'@ wrote the literal @' markers into pyproject.toml, breaking TOML parsing. Switched to creating config/text files in the editor (UTF-8 no BOM) rather than shell heredocs.
- Open-weight vision models return inconsistent JSON shapes across calls: Llama 4 Scout emitted line-item fields both flat and nested ({value, confidence}) for different invoices. Rather than fight it with prompt tweaks, the extraction layer normalizes any shape into the schema's expected form before Pydantic validation — defensive parsing that makes the pipeline robust to model variance.
- Provider-agnostic design earned its keep: Groq decommissioned the Llama 3.2 vision models mid-build. Because extraction goes through a thin provider abstraction over the OpenAI-compatible API, swapping to Llama 4 Scout was a one-line `.env` change with zero code edits. Preview models can vanish without notice, so the system reads provider + model from config and can switch between Groq, OpenAI, or Gemini freely.
- SDK and transport version drift: a newer `httpx` removed a keyword argument the pinned `openai` SDK still passed (`proxies`), breaking client init. Fixed by upgrading the SDK and pinning both in `requirements.txt`. Pinning transitive-adjacent deps, not just top-level ones, prevents this class of break on fresh installs.
- The model launders numeric errors, so tests target what it can't fix: Scout silently corrected both wrong totals and wrong line-item amounts back to internal consistency on extraction, masking the very discrepancies AP review exists to catch. The deterministic math rule is therefore unit-tested against synthetic data, while end-to-end review routing is exercised via missing-field corruptions (blank vendor / invoice number), which vision models report faithfully rather than repair.
- Don't model every field — reconcile the math: real invoices carry charges we can't anticipate (shipping, handling, discounts, deposits). Rather than enumerate them, LedgerLens captures all non-tax adjustments into a single other_charges bucket and enforces subtotal + tax + other_charges = total. When the arithmetic doesn't close, an unaccounted charge wasn't extracted, and the invoice routes to human review — so silent extraction gaps surface as reconciliation failures instead of bad data. The human-in-the-loop is the safety net for what extraction misses.
- Cache extraction by file-content hash: vision API calls cost quota and latency, and the same invoice shouldn't be re-extracted on every eval run or re-upload. Hashing file bytes (rename-safe) means each unique invoice costs exactly one model call, ever — making the project runnable entirely within a free tier.