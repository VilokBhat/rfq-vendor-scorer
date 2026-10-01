"""Load seed/rfqs.json into the database.

    python -m app.seed

Safe to run repeatedly: RFQs are upserted by id. The web app also calls
seed_if_empty() on startup, so a fresh clone works without running this.
"""
import json

from app import db

SEED_FILE = db.ROOT / "seed" / "rfqs.json"


def load_seed_rfqs() -> int:
    rfqs = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    db.upsert_rfqs(rfqs)
    return len(rfqs)


def seed_if_empty() -> None:
    if db.count_rfqs() == 0:
        load_seed_rfqs()


if __name__ == "__main__":
    db.init_db()
    count = load_seed_rfqs()
    print(f"Loaded {count} RFQs from {SEED_FILE} into {db.DB_PATH}")
