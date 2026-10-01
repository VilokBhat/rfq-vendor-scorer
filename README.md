# RFQ Vendor Scorer

A small web app that scores a vendor profile against a stored RFQ (Request for
Quotation). Pick an RFQ, paste or upload a vendor profile, and one Claude call
assesses the profile requirement by requirement. The app shows an alignment
score out of 100, three supporting reasons, two gaps, and a per-requirement
breakdown with the evidence quoted from the profile. Past evaluations are
listed below, most recent first.

- **Backend:** Python, FastAPI, SQLite (standard library `sqlite3`)
- **LLM:** Anthropic Claude via the official `anthropic` SDK (one call per evaluation)
- **Frontend:** one static HTML page with vanilla JavaScript, no build step

Design decisions, scoring approach and trade-offs are in [BUILD_LOG.md](BUILD_LOG.md).

## Requirements

- Python 3.9 or newer
- An Anthropic API key: <https://console.anthropic.com/settings/keys>

## Setup

Run every command from the repository root.

```bash
git clone <this-repo-url> rfq-vendor-scorer
cd rfq-vendor-scorer

python -m venv .venv
```

Activate the virtual environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (cmd)
.venv\Scripts\activate.bat
```

Install dependencies and create your `.env`:

```bash
pip install -r requirements.txt

# macOS / Linux
cp .env.example .env
# Windows
copy .env.example .env
```

Open `.env` and set `ANTHROPIC_API_KEY`.

## Environment variables

Set these in `.env` (loaded automatically) or in your shell. `.env` is git-ignored.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | yes | none | Key for the Claude API |
| `ANTHROPIC_MODEL` | no | `claude-opus-5` | Model used for evaluations. Any model that supports adaptive thinking and structured outputs works, e.g. `claude-sonnet-5` for faster, cheaper runs |

## Load the seed data

The three RFQs in `seed/rfqs.json` are loaded **automatically the first time
the app starts** (when the database has no RFQs yet). To load them explicitly,
or to reload them after editing `seed/rfqs.json`:

```bash
python -m app.seed
```

The command is safe to run repeatedly: RFQs are upserted by id. The database
is a single file, `rfq_scorer.db`, in the repository root. Delete it to start
from scratch.

## Run

```bash
uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000>.

1. Choose an RFQ from the dropdown. "Show RFQ requirements" expands its details.
2. Paste a vendor profile, or use "Choose File" to load one of `samples/vendor-*.txt`.
3. Click **Evaluate**. A single model call usually takes 20 to 60 seconds.
4. The result shows the score, fit band, 3 reasons, 2 gaps and an expandable
   criterion-by-criterion breakdown. Every evaluation is saved and listed
   under "Past evaluations", most recent first. Click a row to expand it.

If something is wrong with the API key or the model call, the error message
appears next to the Evaluate button and nothing is saved.

## How the score is calculated (short version)

The model does not pick the number. It gives every RFQ requirement a verdict
(`met`, `partial`, `not_met`, `not_stated`) with a word-for-word quote from the
profile, and the app computes the score in `app/scoring.py`:

- Points per requirement: mandatory, required and technical **3**, commercial
  (quantity, material, delivery) **2**, preferred **1**.
- `met` earns full points, `partial` half, `not_met` and `not_stated` nothing.
- Score = earned / available x 100.
- If any mandatory requirement is not met, the score is **capped at 30**. The
  uncapped "capability" score is still shown.
- If a quote cannot be found in the profile, the verdict is downgraded one level.

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | The single-page UI |
| `GET` | `/api/rfqs` | All RFQs |
| `POST` | `/api/evaluations` | Body `{"rfq_id": "RFQ-001", "vendor_profile": "..."}`. Runs and saves an evaluation |
| `GET` | `/api/evaluations` | Past evaluations, most recent first |

## Project layout

```
app/
  main.py         FastAPI app: routes, startup seeding, error handling
  evaluator.py    Prompt, the single Claude call, response checks, quote verification
  scoring.py      RFQ -> criteria list, weights, score, mandatory cap, fit bands
  db.py           SQLite schema and queries
  seed.py         Loads seed/rfqs.json (python -m app.seed)
  static/index.html   The whole frontend
seed/             Provided RFQs (rfqs.json is what gets loaded)
samples/          Provided vendor profiles for testing
BUILD_LOG.md      Build notes: approach, decisions, what was skipped
SPEC.md           The original brief, unmodified
```
