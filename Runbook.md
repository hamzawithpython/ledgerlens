# LedgerLens — Restart Runbook

A quick-start guide for picking this project back up after time away.
Environment assumed: **Windows + PowerShell + VS Code**, Python 3.12, Docker Desktop.

> This file is for local development. It is not part of the app and can stay in the repo root as a personal reference.

---

## 0. One-time-per-machine prerequisites

These only matter on a fresh machine or if something is missing. Skip if already done.

- **Docker Desktop** installed and running.
- **Poppler** installed and on PATH (provides `pdftoppm` for PDF rasterization).
  - Installed at `C:\poppler\Library\bin` — verify with `pdftoppm -h`.
  - If "not recognized", re-add to PATH:
    ```powershell
    [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\poppler\Library\bin", "User")
    ```
    Then open a **new** terminal.
- **gcloud CLI** installed (only needed for deploying). Verify with `gcloud --version` in a fresh terminal.

---

## 1. Open the project and activate the environment

```powershell
cd C:\Users\Admin\Desktop\portfolio\ledgerlens
code .
.\venv\Scripts\Activate.ps1
```

Prompt should show `(venv)`. If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

If the `venv` folder is missing (fresh clone), recreate it:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 2. Confirm secrets exist

`.env` and `env.yaml` are gitignored, so a fresh clone won't have them. They must exist for the app to run.

- **`.env`** (local dev) should contain:
  ```
  EXTRACTION_PROVIDER=groq
  EXTRACTION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
  GROQ_API_KEY=...
  OPENAI_API_KEY=
  GEMINI_API_KEY=
  DATABASE_URL=postgresql+psycopg2://ledger:ledger@localhost:5433/ledgerlens
  CONFIDENCE_THRESHOLD=0.85
  ```
  If missing: `Copy-Item .env.example .env` then fill in the real `GROQ_API_KEY`.

- **`env.yaml`** (Cloud Run deploy only) holds the same keys plus the **Neon** DATABASE_URL. Only needed when deploying. Recreate from memory/password manager if missing.

> If the Groq key was rotated, update it in **both** `.env` and `env.yaml`.

---

## 3. Start the local database

Local dev uses a Dockerized Postgres on **port 5433** (5432 is taken by a native Postgres install on this machine — do not change this).

```powershell
docker compose up -d db
docker compose ps          # confirm ledgerlens-db-1 is "running" on 5433
```

If the tables don't exist (fresh DB / volume was wiped), create them:

```powershell
python -c "from app.db import Base, engine; import app.models; Base.metadata.create_all(engine); print('tables created')"
```

---

## 4. Generate synthetic test invoices (if `evals/samples/` is empty)

Sample PDFs are gitignored, so a fresh clone won't have them. The ground-truth JSON and generator script are committed, so just regenerate:

```powershell
python evals/generate_invoices.py
```

Produces 8 PDFs in `evals/samples/` (2 deliberately broken) + `ground_truth.json`.

> **Gotcha:** close any open sample PDF before regenerating, or you'll get `PermissionError` (Windows file lock).

---

## 5. Run the app locally

```powershell
uvicorn app.main:app --reload --port 8000
```

Then open **http://localhost:8000** in the browser.
Interactive API docs: **http://localhost:8000/docs**

The server runs continuously in this terminal. Use a **second terminal** (cd + activate venv again) for any other commands while it runs.

---

## 6. Test it

**In the browser:** upload `evals/samples/invoice_00.pdf` → should be `approved`.
Upload `invoice_06.pdf` or `invoice_07.pdf` → should land in the review queue.

**Unit tests** (no DB or API needed):

```powershell
pytest tests/ -v
```

**Accuracy eval** (needs DB up; extraction is cached so it's cheap):

```powershell
python -m evals.run_eval
```

Expected ballpark: ~97% field accuracy, 100% routing.

**Reset the database** between test runs (clears all stored invoices):

```powershell
python scripts_reset_db.py
```

---

## 7. Run the full container locally (optional — mimics Cloud Run)

```powershell
docker build -t ledgerlens .
docker run --rm -p 8080:8080 `
  -e DATABASE_URL="<NEON_OR_LOCAL_URL>" `
  -e GROQ_API_KEY="<KEY>" `
  -e EXTRACTION_PROVIDER="groq" `
  -e EXTRACTION_MODEL="meta-llama/llama-4-scout-17b-16e-instruct" `
  -e CONFIDENCE_THRESHOLD="0.85" `
  ledgerlens
```

Then test at http://localhost:8080.

> If port 8080 is "already allocated": `docker ps` to find the old container, `docker stop <id>`.

---

## 8. Deploy to Cloud Run

```powershell
# Confirm correct project + auth (in a fresh terminal if gcloud isn't found)
gcloud config get-value project        # should be ledgerlens-16915
gcloud auth login                      # only if not already authed

# Deploy (env.yaml must exist with real keys + Neon URL)
gcloud run deploy ledgerlens --source . --region us-central1 --allow-unauthenticated --memory 1Gi --timeout 120 --env-vars-file env.yaml
```

Live URL: **https://ledgerlens-223615207409.us-central1.run.app**

Read logs if a deploy fails to start:

```powershell
gcloud run services logs read ledgerlens --region us-central1 --limit 30
```

---

## 9. Git workflow reminder

`main` stays deployable. Each chunk of work goes on a feature branch:

```powershell
git checkout main
git pull
git checkout -b feat/<feature-name>
# ... work, commit with Conventional Commits (feat: / fix: / docs: / refactor: / test: / chore:)
git checkout main
git merge feat/<feature-name> --no-ff -m "Merge feat/<feature-name>: <summary>"
git push origin main
```

---

## Common gotchas (all hit during the original build)

| Symptom | Cause / Fix |
|---|---|
| `gcloud`/`pdftoppm` not recognized | Stale PATH — open a **new** terminal. |
| `ModuleNotFoundError: No module named 'app'` | Not in project root, or running a script directly — use `python -m evals.run_eval`. |
| `password authentication failed` / port clash | Native Postgres on 5432; this project uses **5433**. Check `docker compose ps`. |
| `PermissionError` writing a sample PDF | The PDF is open in a viewer — close it, regenerate. |
| `proxies` keyword error | `httpx`/`openai` version drift — pins are in `requirements.txt`; rebuild. |
| Duplicate flagged on a clean upload | Leftover rows in DB — run `scripts_reset_db.py`. |
| Container won't start on Cloud Run | Usually a malformed `DATABASE_URL` — use `--env-vars-file`, never `--set-env-vars` for the URL (the `@` breaks it). Check logs. |
| Neon first request slow / times out | Free-tier DB auto-suspends; first connect wakes it. Retry once. |

---

## File map

```
app/main.py             FastAPI routes (upload, list, queue, resolve)
app/extraction.py       PDF -> image -> vision LLM -> Pydantic (+ cache, shape normalize)
app/validation_agent.py deterministic rules + routing decision
app/confidence.py       confidence scoring (min of critical fields)
app/reasoning.py        LLM narrator for the review UI
app/store.py            persistence + queue operations
app/schemas.py          Pydantic models (the data contract)
app/db.py / models.py   SQLAlchemy engine + invoices table
app/ui/index.html       single-page UI
evals/                  invoice generator, ground truth, accuracy eval
tests/                  validation rule unit tests
Dockerfile              container w/ Poppler for Cloud Run
docker-compose.yml      local Postgres (5433)
env.yaml                Cloud Run env vars (gitignored)
```
