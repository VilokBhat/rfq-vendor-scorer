# Build Log

Fill this in as you go, or at the end. Keep it short — bullet points are fine.
This is read as carefully as the code.

---

## Stack

What you used and why. One line each.

- Frontend: One static `index.html` with vanilla JS. The spec asks for a single page with no routing, and with no build step there is nothing extra to install or break on a clean clone.
- Backend: Python + FastAPI. Small, validates request bodies with Pydantic, and runs the blocking LLM call in its threadpool for free.
- Database: SQLite through the standard-library `sqlite3`. Zero setup, one file, and the spec says SQLite is plenty.
- LLM / agent: Claude (`claude-opus-5` by default, overridable with `ANTHROPIC_MODEL`) through the official `anthropic` SDK. One Messages API call with structured outputs (JSON schema), adaptive thinking, effort `medium` and server-side refusal fallback. No agent framework: the task is one judgement, not an open-ended tool loop.

---

## Scoring approach

How does your agent arrive at a number? What did you do to make that number
mean something?

- **The LLM classifies, the code does the arithmetic.** LLMs are poor at picking a calibrated number but good at judging "does this text show X?". So the model never outputs a score.
- The RFQ is flattened into a checklist with stable ids (`scoring.build_criteria`): mandatory `M*`, required `R*`, technical `T*`, commercial `C*` (quantity, material, delivery from the RFQ header) and preferred `P*`.
- The JSON schema sent to Claude is **generated from that checklist**, with one required property per criterion id. The model cannot skip or invent a requirement.
- For each criterion the model returns `evidence` (a word-for-word quote), a one-line `note`, and a `status` of `met` / `partial` / `not_met` / `not_stated`.
- `scoring.compute_score` applies fixed weights. Mandatory, required and technical criteria are worth 3, commercial 2, preferred 1. `met` earns 100% of the points, `partial` 50%, `not_met` and `not_stated` 0%. Score = earned / available × 100.
- **Mandatory requirements act as a gate.** If any mandatory criterion is not `met`, the score is capped at 30 ("Not eligible"). The uncapped `raw_score` is stored and shown, so a capable-but-uncertified vendor still reads as capable.
- **`not_stated` scores the same as `not_met`.** The prompt says marketing language without a named standard, number or certificate is not evidence, and that ISO 9001 or IATF 16949 is not AS9100D. This stops vendor C's brochure copy earning points.
- **Evidence check** (`evaluator._check_evidence`): every quote is looked up in the profile after normalising case, whitespace, ± and smart quotes. If a `met`/`partial` verdict's quote isn't there, it is downgraded one level, and the UI shows "Model said X, but its quote is not in the profile". This guards against hallucinated support.
- The number has a stated reading: 80+ strong, 60–79 possible with gaps, 40–59 weak, below 40 poor. Every point traces back to a row in the criterion breakdown.
- Worked example to check the arithmetic, using verdicts **written by hand** (not model output): RFQ-001 with vendor A gives raw 81, capped to 30 (no AS9100D, which is the trap in that sample). Vendor B gives 44: certified, but misses ±0.02 mm, 5-axis and the 6-week delivery. Vendor C should land near 0.

---

## What you built

What works. Be specific.

- SQLite storage for RFQs and evaluations. The three seed RFQs load automatically on first start, or with `python -m app.seed` (idempotent upsert).
- Single page:
  - RFQ dropdown with an expandable requirements panel.
  - Vendor profile textarea, plus a file picker that reads `.txt`/`.md` into the textarea in the browser.
  - Evaluate button with a busy state and inline errors.
- Result view:
  - Score /100, fit band, vendor name (extracted by the model), 3 reasons, 2 gaps.
  - The capped-vs-raw explanation when the mandatory gate fails.
  - An expandable per-criterion table with verdict, quote and note.
- Past evaluations, most recent first, each expandable to the full result and the submitted profile.
- JSON API: `GET /api/rfqs`, `POST /api/evaluations`, `GET /api/evaluations`.
- Guard rails:
  - Unknown RFQ returns 404. An empty or oversized profile returns 400, before any LLM call is made.
  - Missing or invalid key, rate limits, API and network errors, refusals and truncated output all become a readable 502 message. Failed evaluations are not saved.
  - Responses with fewer than 3 reasons or 2 gaps are rejected.
  - Vendor text is passed to the model inside `<vendor_profile>` tags and flagged as untrusted (prompt-injection hygiene). The UI renders everything with `textContent`, never `innerHTML`.
- Verified during the build:
  - Scoring, the cap, the quote downgrade and the error paths, with scripted checks against a stubbed model response.
  - The full UI flow in headless Chrome: evaluate, breakdown, history order, no console errors, no horizontal scroll at 390 px.
  - A clean clone followed step by step from the README: install, auto-seed, run.
  - A real SDK call reaching the API (with an invalid key, so it got a 401 that was mapped correctly).

---

## What you skipped

What you consciously left out, and why.

- **A live evaluation against the real model.** There was no API key in the build environment. The request shape passes the SDK and reaches the API, but the prompt has not yet been run end to end. This is the first thing to do with a key: run the 3 samples against RFQ-001.
- Test suite and CI: out of scope per the spec. The scripted checks above were throwaway and are not committed.
- Retrying on a bad model response: the "one LLM call per evaluation" constraint means a retry would be a second call. It fails loudly instead.
- RFQ create/edit UI: the spec only needs stored and seeded RFQs. Editing `seed/rfqs.json` and re-running the seed command covers it.
- History filtering or pagination: the API returns the latest 100, which is enough for this exercise.
- Streaming or progress events: one 20–60 s call behind a busy indicator is acceptable here.
- Prompt caching: the system prompt is below the minimum cacheable length, so it would do nothing.
- PDF/DOCX upload: the spec says all samples are plain text.
- Auth, deployment, styling beyond legible: out of scope per the spec.

---

## Where the spec was unclear

Anything ambiguous, contradictory, or underspecified. What did you assume,
and what did you do about it?

- **What "alignment score out of 100" means is not defined.** I assumed it means "how close this vendor is to being awardable, as a buyer would weigh it", with mandatory items as pass/fail. I documented the weights and the cap so the assumption is visible and easy to change (`scoring.py`).
- **"AI agent" vs "one LLM call per evaluation".** A tool-using agent loop needs several calls. I read "agent" as "the LLM step" and used one structured-output call with no tool loop.
- **Reasons "supporting" a score can be positive or negative.** Reasons explain the score either way, and gaps are the shortfalls. When a vendor has no material gaps, the model is told to name the two points a buyer should verify before award, so the UI always has two.
- **`rfqs.json` and the `.md` files differ.**
  - RFQ-002's JSON lists "Parts up to 600 mm" as technical and again as preferred; the `.md` lists it only as preferred.
  - RFQ-003's JSON has "Cut-to-size capability" (technical) and "Ability to supply cut-to-size" (required).
  - RFQ-002's `material` field repeats the coating spec that is also technical item 1.
  - I loaded the JSON as-is, because the spec calls it "ready to load", rather than silently editing the provided data. So these requirements are counted twice in the score. Noted here, not fixed.
- **Some header fields aren't really assessable.** RFQ-003's delivery is "Call-off against rate contract", and RFQ-001's material is free-issue (the vendor doesn't supply it). They still become commercial criteria. The model is asked to judge them from the profile, and "free-issue handling / 7075 experience" is the sensible reading for RFQ-001.
- **"Past evaluations are listed below": for all RFQs or the selected one?** I show all of them, each labelled with its RFQ id.
- **"Uploads or pastes".** The upload is read in the browser into the same textarea, so the backend only ever sees text and the user can see and edit what is being sent.
- **"Mandatory" vs "Required" is not defined.** I treated mandatory as a gate, and required as heavily weighted but not gating.

---

## What broke

Something that did not work first time. What was it, how did you diagnose it,
how did you fix it?

- **`pip install` failed on a clean clone (Windows).**
  - What happened: following my own README in a fresh clone, install failed with `OSError: [Errno 2] No such file or directory: ...\.venv\Lib\site-packages\anthropic\types\beta\beta_managed_agents_environment_archived_deployment_paused_reason_error.py`.
  - Diagnosis: the same install worked in the main project folder. The only difference was the clone location, a deeply nested temp folder. The full path was over Windows' 260-character limit, because of how long the SDK's module file names are.
  - Fix: re-cloned to a short path and the install, seed and run steps all worked. I added a warning to the README so a reviewer on Windows doesn't hit it.
- **Missing API key surfaced a raw SDK error.** With no key set, the SDK raises a `TypeError` ("Could not resolve authentication method...") rather than an `AuthenticationError`, so my first error mapping showed that raw text. I caught it in the scripted no-key check and mapped it to "No Anthropic API key found. Set ANTHROPIC_API_KEY in .env."
- **Python version vs SDK version.** The machine has Python 3.9, and `anthropic` 1.x needs 3.10+, so pip resolved 0.125.0. I checked that 0.125.0 supports `output_config`, `betas` and `fallbacks="default"` on `client.beta.messages.create` before relying on them, then pinned exact versions in `requirements.txt` so 3.9 and newer Pythons get the same SDK.

---

## Working with AI

We expect you used AI assistants. This section is about how you worked with
them, not whether you did.

- Which tools you used, and roughly how you split the work with them:
  Claude Code (Claude Opus 5.5) in the terminal. From the brief it chose the stack, wrote the code, README and this log, and ran the verification (stubbed-model checks, a headless-browser run of the UI, a clean-clone install). It committed in steps and did not push. *[Candidate: add your own part — what you reviewed, changed or decided.]*
- Something your AI assistant got wrong that you caught and corrected:
  *[Candidate to complete from your own review.]* Caught during the build itself: the raw SDK error for a missing key, and the README not warning about the Windows path-length failure (both under "What broke").
- Something you decided to write yourself rather than generate, and why:
  *[Candidate to complete.]* The obvious candidate is the weights and cap in `app/scoring.py`. They are business judgement, not code, and are the first thing an interviewer will ask you to defend or change.

---

## Weakest part of this code

The thing you would be least comfortable defending. Be specific — name the
file or function.

- **`app/evaluator.py`, `_check_evidence` / `_quote_in_profile`.** It is exact substring matching after light normalisation, which fails in both directions:
  - A legitimate verdict whose quote differs slightly from the profile (a dropped word, different spacing in "Ra1.6") gets downgraded.
  - A real quote attached to the wrong verdict passes, because the check proves the quote exists, not that it supports the verdict.
- Close second: the weights and the cap of 30 in `app/scoring.py` are my judgement. They have not been calibrated against real buyer decisions.

---

## Next 48 hours

If you had two more days, what is the first thing you would change?

- Build a small labelled eval set first: the 3 sample vendors × 3 RFQs, with a buyer's expected verdict per criterion.
- Run each pair several times to measure verdict agreement and score variance.
- Then tune the prompt, the partial-credit rule and the weights against that set, instead of by eye.
- After that: de-duplicate overlapping criteria (the 600 mm and cut-to-size double counts), and make the evidence check tolerant (fuzzy matching with a threshold) without letting unsupported claims through.
