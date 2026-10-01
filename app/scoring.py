"""Turn an RFQ into a criteria checklist, and per-criterion verdicts into a score.

The LLM never produces the number. It gives each criterion a verdict
(met / partial / not_met / not_stated) backed by a quote from the profile, and
this module turns those verdicts into a score using fixed weights. The same
verdicts always give the same score, and every point can be traced back to a
criterion in the breakdown.
"""
from typing import Any, Dict, List

# Points available per criterion, by the RFQ section it comes from.
WEIGHTS = {
    "mandatory": 3,
    "required": 3,
    "technical": 3,
    "commercial": 2,  # quantity, material and delivery from the RFQ header
    "preferred": 1,
}

# Share of a criterion's points earned for each verdict. "not_stated" scores
# the same as "not_met": a buyer cannot award work on capabilities the vendor
# has not claimed.
CREDIT = {"met": 1.0, "partial": 0.5, "not_met": 0.0, "not_stated": 0.0}
STATUSES = list(CREDIT)

# A vendor missing any mandatory requirement cannot be awarded the work however
# capable it is otherwise, so its score is capped. The uncapped figure is kept
# as raw_score so the UI can still show how capable the vendor is.
MANDATORY_CAP = 30


def build_criteria(rfq: Dict[str, Any]) -> List[Dict[str, str]]:
    """Flatten an RFQ into criteria with stable ids, e.g. M1, R2, T3, C1, P2."""
    criteria: List[Dict[str, str]] = []

    def add(prefix: str, category: str, items: List[str]) -> None:
        for i, text in enumerate(items, start=1):
            criteria.append({"id": f"{prefix}{i}", "category": category, "text": text})

    commercial = [
        f"{label}: {rfq[key]}"
        for key, label in (("quantity", "Quantity"), ("material", "Material"), ("delivery", "Delivery"))
        if rfq.get(key)
    ]
    add("M", "mandatory", rfq.get("mandatory", []))
    add("R", "required", rfq.get("required", []))
    add("T", "technical", rfq.get("technical", []))
    add("C", "commercial", commercial)
    add("P", "preferred", rfq.get("preferred", []))
    return criteria


def compute_score(assessed: List[Dict[str, Any]]) -> Dict[str, Any]:
    """assessed: criteria from build_criteria(), each with a "status" added."""
    earned = possible = 0.0
    mandatory_met = True
    for criterion in assessed:
        weight = WEIGHTS[criterion["category"]]
        possible += weight
        earned += weight * CREDIT[criterion["status"]]
        if criterion["category"] == "mandatory" and criterion["status"] != "met":
            mandatory_met = False

    raw_score = round(100 * earned / possible) if possible else 0
    score = raw_score if mandatory_met else min(raw_score, MANDATORY_CAP)
    return {"score": score, "raw_score": raw_score, "mandatory_met": mandatory_met}


def fit_label(score: int, mandatory_met: bool) -> str:
    if not mandatory_met:
        return "Not eligible - mandatory requirement not evidenced"
    if score >= 80:
        return "Strong fit"
    if score >= 60:
        return "Possible fit - gaps to close"
    if score >= 40:
        return "Weak fit"
    return "Poor fit"
