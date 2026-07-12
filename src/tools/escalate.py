"""Tool 2 — Human escalation.

Called when the agent detects: transactional intent, PII in the query,
ambiguous or high-risk situation, or explicit user request for a human.

In production this would create a real ticket in a CRM (Salesforce,
ServiceNow etc). Here we simulate with an in-memory counter and a
timestamped ticket ID.
"""
from datetime import datetime, timezone
from pathlib import Path
import json


TICKET_STORE = Path("data/policy/escalations.json")

# Category → estimated callback window
CALLBACK_WINDOWS = {
    "transactional": "within 2 hours",
    "pii_shared": "within 4 hours",
    "bereavement": "within 24 hours (compassionate handling)",
    "legal_advice": "within 24 hours",
    "unclear": "within 4 hours",
    "other": "within 4 hours",
}


def _next_ticket_id() -> str:
    """Generate a unique-ish ticket ID from a monotonic counter."""
    TICKET_STORE.parent.mkdir(parents=True, exist_ok=True)
    if TICKET_STORE.exists():
        existing = json.loads(TICKET_STORE.read_text())
    else:
        existing = []
    n = len(existing) + 1001
    return f"ESC-{n:04d}"


def _log_ticket(ticket_id: str, reason: str, category: str) -> None:
    """Persist ticket metadata (never the raw user query — PII safety)."""
    if TICKET_STORE.exists():
        existing = json.loads(TICKET_STORE.read_text())
    else:
        existing = []
    existing.append({
        "ticket_id": ticket_id,
        "category": category,
        "reason_summary": reason[:120],
        "created_utc": datetime.now(timezone.utc).isoformat(),
    })
    TICKET_STORE.write_text(json.dumps(existing, indent=2))


def create_escalation(category: str, reason: str) -> str:
    """Create an escalation ticket and return a customer-facing message.

    Args:
        category: One of 'transactional', 'pii_shared', 'bereavement',
                  'legal_advice', 'unclear', 'other'.
        reason: One-line summary of why escalation is needed (no PII).

    Returns:
        Customer-facing string with ticket ID and expected callback window.
    """
    if category not in CALLBACK_WINDOWS:
        category = "other"

    ticket_id = _next_ticket_id()
    _log_ticket(ticket_id, reason, category)
    callback = CALLBACK_WINDOWS[category]

    return (
        f"Escalation created. Ticket: {ticket_id}. "
        f"A specialist will call back {callback}. "
        f"You do not need to share any personal details here."
    )