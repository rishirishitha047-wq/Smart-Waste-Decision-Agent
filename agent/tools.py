"""EcoMind AI tools: waste-management data access and planning, with simulated data.

All data is loaded from agent/data/bins.json and config.json. No live sensors,
real dispatches or invented environmental measurements. Every tool response includes
data_source: "simulated" so the agent and UI can label it clearly.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strands import tool

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent / "data"


def _load_bins() -> list[dict[str, Any]]:
    with open(_DATA_DIR / "bins.json", encoding="utf-8") as f:
        return json.load(f)


def _load_config() -> dict[str, Any]:
    with open(_DATA_DIR / "config.json", encoding="utf-8") as f:
        return json.load(f)


def _find_bin(bins: list[dict], bin_id: str) -> dict | None:
    target = bin_id.strip().upper()
    for b in bins:
        if b["id"].strip().upper() == target:
            return b
    return None


def _hours_since(last_collected_iso: str) -> float:
    try:
        dt = datetime.fromisoformat(last_collected_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() / 3600
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# In-memory issue log (resets on process restart; clearly simulated)
# ---------------------------------------------------------------------------

ISSUES: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
def get_bin_status(bin_id: str) -> dict:
    """Retrieve a bin's recorded condition, fill level, location and issue status by its bin ID."""
    if not bin_id or not bin_id.strip():
        return {"error": "bin_id is required"}
    bins = _load_bins()
    b = _find_bin(bins, bin_id)
    if b is None:
        return {"error": f"bin '{bin_id}' not found"}
    return {
        "bin_id": b["id"],
        "fill_level": b["fill_level"],
        "location": b["location"],
        "waste_type": b["waste_type"],
        "last_collected": b["last_collected"],
        "issue_status": b["issue_status"],
        "distance_meters": b["distance_meters"],
        "data_source": "simulated",
    }


@tool
def assess_collection_priority(bin_ids: list | None = None) -> dict:
    """Calculate collection priority scores for bins from their fill level and time since last collection.

    If bin_ids is None or empty, assesses all bins. Returns bins sorted by descending priority score.
    Priority score = fill_level * 0.7 + min(hours_since_collection, 72) / 72 * 100 * 0.3
    """
    bins = _load_bins()
    config = _load_config()
    overflow_threshold = config.get("overflow_threshold", 90)

    if bin_ids:
        target_ids = [b.strip().upper() for b in bin_ids]
        bins = [b for b in bins if b["id"].upper() in target_ids]

    results = []
    for b in bins:
        hours = _hours_since(b["last_collected"])
        capped = min(hours, 72)
        score = round(b["fill_level"] * 0.7 + (capped / 72) * 100 * 0.3, 1)
        results.append({
            "bin_id": b["id"],
            "fill_level": b["fill_level"],
            "priority_score": score,
            "overflow": b["fill_level"] >= overflow_threshold,
            "hours_since_collection": round(hours, 1),
            "location": b["location"],
            "issue_status": b["issue_status"],
        })

    results.sort(key=lambda x: x["priority_score"], reverse=True)
    return {
        "bins": results,
        "overflow_threshold": overflow_threshold,
        "data_source": "simulated",
    }


@tool
def create_collection_plan(vehicle_capacity: int | None = None) -> dict:
    """Recommend a waste collection order based on priority and distance. Returns a recommendation only — no real dispatch occurs."""
    config = _load_config()
    capacity = vehicle_capacity if vehicle_capacity is not None else config.get("vehicle_capacity", 5)

    if capacity < 1:
        return {"error": "vehicle_capacity must be at least 1"}

    bins = _load_bins()
    overflow_threshold = config.get("overflow_threshold", 90)
    hours_map = {b["id"]: _hours_since(b["last_collected"]) for b in bins}

    def sort_key(b: dict):
        capped = min(hours_map[b["id"]], 72)
        score = b["fill_level"] * 0.7 + (capped / 72) * 100 * 0.3
        return (-score, b["distance_meters"])

    sorted_bins = sorted(bins, key=sort_key)
    plan_bins = sorted_bins[:capacity]

    plan = []
    for rank, b in enumerate(plan_bins, start=1):
        hours = hours_map[b["id"]]
        capped = min(hours, 72)
        score = round(b["fill_level"] * 0.7 + (capped / 72) * 100 * 0.3, 1)
        plan.append({
            "rank": rank,
            "bin_id": b["id"],
            "priority_score": score,
            "fill_level": b["fill_level"],
            "overflow": b["fill_level"] >= overflow_threshold,
            "location": b["location"],
            "distance_meters": b["distance_meters"],
            "issue_status": b["issue_status"],
        })

    return {
        "recommendation": True,
        "plan": plan,
        "total_bins_assessed": len(bins),
        "capacity_used": len(plan),
        "note": "This is a recommendation only. No real dispatch has occurred.",
        "data_source": "simulated",
    }


@tool
def report_bin_issue(bin_id: str, description: str, issue_type: str = "general") -> dict:
    """Create a simulated issue report for a bin and return its report ID. Returns the existing report ID if the same issue is already open."""
    if not bin_id or not bin_id.strip():
        return {"error": "bin_id is required"}

    bins = _load_bins()
    b = _find_bin(bins, bin_id)
    if b is None:
        return {"error": f"bin '{bin_id}' not found"}

    if not description or not (1 <= len(description.strip()) <= 500):
        return {"error": "description must be between 1 and 500 characters"}

    desc_clean = description.strip().lower()
    bid_clean = bin_id.strip().upper()
    for issue in ISSUES:
        if (
            issue["bin_id"].upper() == bid_clean
            and issue["description"].strip().lower() == desc_clean
            and issue["status"] == "open"
        ):
            return {**issue, "duplicate": True}

    report_id = f"RPT-{bid_clean}-{int(time.time())}"
    record: dict[str, Any] = {
        "report_id": report_id,
        "bin_id": bid_clean,
        "description": description.strip(),
        "issue_type": issue_type,
        "status": "open",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duplicate": False,
    }
    ISSUES.append(record)
    return record


TOOLS = [get_bin_status, assess_collection_priority, create_collection_plan, report_bin_issue]
