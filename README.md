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

## What Didn'\''t Work / Lessons
_(updated as we go)_
