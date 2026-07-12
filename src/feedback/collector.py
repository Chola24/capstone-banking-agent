"""Feedback collection + adaptive behavior for Phase 7.

Design principle: no PII in feedback storage. We only tag by intent category and record thumbs up/down. Cross-user learning is possible
via category-level signals without knowing anything about specific users.

Adaptive rule (simple, transparent, auditable):
  - If a given intent category has >= 2 recent thumbs-down within the last 10 events, the next agent response for that category
    gets a warning prepended: 'be extra careful, users recently reported issues.'

This is a lightweight substitute for real RLHF. In production this would feed a proper labeling pipeline.
"""
import json
from pathlib import Path
from datetime import datetime, timezone


FEEDBACK_FILE = Path("data/feedback/feedback_store.json")
RECENT_WINDOW = 10       # look at last N feedback events
NEGATIVE_THRESHOLD = 2   # trigger warning if >= N negatives in window


def _load_events() -> list:
    if not FEEDBACK_FILE.exists():
        return []
    try:
        return json.loads(FEEDBACK_FILE.read_text())
    except json.JSONDecodeError:
        return []


def _save_events(events: list) -> None:
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    FEEDBACK_FILE.write_text(json.dumps(events, indent=2))


def record_feedback(intent_category: str, was_helpful: bool) -> None:
    """Store a feedback event. Never store the raw query — only the category.

    Args:
        intent_category: One of the classifier's 6 categories.
        was_helpful: True for thumbs up, False for thumbs down.
    """
    events = _load_events()
    events.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "category": intent_category,
        "helpful": was_helpful,
    })
    _save_events(events)


def has_recent_negatives(intent_category: str) -> bool:
    """Check whether this category has crossed the negative threshold recently."""
    events = _load_events()
    recent = events[-RECENT_WINDOW:]
    negatives = [
        e for e in recent
        if e["category"] == intent_category and not e["helpful"]
    ]
    return len(negatives) >= NEGATIVE_THRESHOLD


def get_adaptive_hint(intent_category: str) -> str:
    """Return an extra instruction if this category has recent complaints."""
    if has_recent_negatives(intent_category):
        return (
            "\n[Adaptation note: Recent users reported dissatisfaction with "
            f"'{intent_category}' answers. Be extra precise, always cite sources, "
            "and offer escalation if uncertain.]"
        )
    return ""


def get_summary() -> dict:
    """Return aggregate feedback stats — used for before/after demonstration."""
    events = _load_events()
    if not events:
        return {"total": 0, "by_category": {}}

    by_cat = {}
    for e in events:
        cat = e["category"]
        if cat not in by_cat:
            by_cat[cat] = {"positive": 0, "negative": 0}
        if e["helpful"]:
            by_cat[cat]["positive"] += 1
        else:
            by_cat[cat]["negative"] += 1

    return {"total": len(events), "by_category": by_cat}