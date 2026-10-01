"""FastAPI app: serves the single page and a small JSON API.

    uvicorn app.main:app --reload
"""
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import db, evaluator
from app.scoring import fit
from app.seed import seed_if_empty

load_dotenv(db.ROOT / ".env")
logging.basicConfig(level=logging.INFO)

INDEX_HTML = db.ROOT / "app" / "static" / "index.html"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    seed_if_empty()  # first run on a fresh clone loads the three seed RFQs
    yield


app = FastAPI(title="RFQ Vendor Scorer", lifespan=lifespan)


class EvaluationRequest(BaseModel):
    rfq_id: str
    vendor_profile: str


def _present(ev: Dict[str, Any]) -> Dict[str, Any]:
    return {**ev, "fit": fit(ev["score"], ev["mandatory_met"])}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX_HTML)


@app.get("/api/rfqs")
def list_rfqs() -> List[Dict[str, Any]]:
    return db.list_rfqs()


@app.get("/api/evaluations")
def list_evaluations() -> List[Dict[str, Any]]:
    return [_present(ev) for ev in db.list_evaluations()]


# A plain `def` (not async) so FastAPI runs the blocking LLM call in its threadpool.
@app.post("/api/evaluations", status_code=201)
def create_evaluation(req: EvaluationRequest) -> Dict[str, Any]:
    rfq = db.get_rfq(req.rfq_id)
    if rfq is None:
        raise HTTPException(404, f"Unknown RFQ {req.rfq_id}")

    profile = req.vendor_profile.strip()
    if not profile:
        raise HTTPException(400, "Vendor profile is empty.")
    if len(profile) > evaluator.MAX_PROFILE_CHARS:
        raise HTTPException(400, f"Vendor profile is too long (max {evaluator.MAX_PROFILE_CHARS} characters).")

    try:
        result = evaluator.evaluate(rfq, profile)
    except evaluator.EvaluationError as e:
        raise HTTPException(502, str(e)) from e

    evaluation_id = db.insert_evaluation({**result, "rfq_id": rfq["id"], "vendor_profile": profile})
    return _present(db.get_evaluation(evaluation_id))
