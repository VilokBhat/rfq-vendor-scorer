"""SQLite storage for RFQs and past evaluations.

One file, plain sqlite3 from the standard library. A new connection is opened
per call, which keeps things simple and safe under FastAPI's threadpool.
"""
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DATABASE_PATH") or ROOT / "rfq_scorer.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS rfqs (
    id       TEXT PRIMARY KEY,
    title    TEXT NOT NULL,
    category TEXT,
    data     TEXT NOT NULL              -- the full RFQ object as JSON
);

CREATE TABLE IF NOT EXISTS evaluations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    rfq_id         TEXT NOT NULL REFERENCES rfqs(id),
    vendor_name    TEXT,
    vendor_profile TEXT NOT NULL,
    score          INTEGER NOT NULL,    -- final score shown to the user
    raw_score      INTEGER NOT NULL,    -- score before the mandatory-requirement cap
    mandatory_met  INTEGER NOT NULL,    -- 0/1
    reasons        TEXT NOT NULL,       -- JSON list of 3 strings
    gaps           TEXT NOT NULL,       -- JSON list of 2 strings
    criteria       TEXT NOT NULL,       -- JSON list of per-criterion assessments
    model          TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


# --- RFQs -------------------------------------------------------------------

def upsert_rfqs(rfqs: List[Dict[str, Any]]) -> None:
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO rfqs (id, title, category, data) VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title, category = excluded.category, data = excluded.data
            """,
            [(r["id"], r["title"], r.get("category"), json.dumps(r)) for r in rfqs],
        )


def count_rfqs() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM rfqs").fetchone()[0]


def list_rfqs() -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT data FROM rfqs ORDER BY id").fetchall()
    return [json.loads(row["data"]) for row in rows]


def get_rfq(rfq_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute("SELECT data FROM rfqs WHERE id = ?", (rfq_id,)).fetchone()
    return json.loads(row["data"]) if row else None


# --- Evaluations ------------------------------------------------------------

def insert_evaluation(ev: Dict[str, Any]) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO evaluations (rfq_id, vendor_name, vendor_profile, score, raw_score,
                                     mandatory_met, reasons, gaps, criteria, model)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ev["rfq_id"],
                ev["vendor_name"],
                ev["vendor_profile"],
                ev["score"],
                ev["raw_score"],
                int(ev["mandatory_met"]),
                json.dumps(ev["reasons"]),
                json.dumps(ev["gaps"]),
                json.dumps(ev["criteria"]),
                ev["model"],
            ),
        )
        return cur.lastrowid


def _evaluation_from_row(row: sqlite3.Row) -> Dict[str, Any]:
    ev = dict(row)
    ev["mandatory_met"] = bool(ev["mandatory_met"])
    for key in ("reasons", "gaps", "criteria"):
        ev[key] = json.loads(ev[key])
    return ev


_EVALUATION_SELECT = """
    SELECT e.*, r.title AS rfq_title
    FROM evaluations e JOIN rfqs r ON r.id = e.rfq_id
"""


def get_evaluation(evaluation_id: int) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(_EVALUATION_SELECT + " WHERE e.id = ?", (evaluation_id,)).fetchone()
    return _evaluation_from_row(row) if row else None


def list_evaluations(limit: int = 100) -> List[Dict[str, Any]]:
    # ORDER BY id rather than created_at: created_at has 1-second resolution,
    # id is strictly increasing, so "most recent first" is unambiguous.
    with connect() as conn:
        rows = conn.execute(_EVALUATION_SELECT + " ORDER BY e.id DESC LIMIT ?", (limit,)).fetchall()
    return [_evaluation_from_row(row) for row in rows]
