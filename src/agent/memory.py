"""Memory retention and reset policy.

The agent uses LangChain's built-in message history via the MessagesPlaceholder in tool_agent.py. This file documents the
retention rules and provides a manual reset helper.

Retention policy:
  - Keep last 6 messages (3 turns) in memory
  - No cross-session persistence — history dies when the CLI exits
  - No PII stored — all user inputs pass through planner classification before entering history; PII-flagged queries route to escalation
    and do NOT populate history

Reset triggers:
  - User types 'reset' or 'clear'
  - Session ends (quit/exit)
  - Explicit escalation created (history cleared to avoid leaking context into a human handoff)

Rationale (banking):
  Persistent conversation memory would be a privacy risk in a
  banking context. We deliberately choose in-memory-only, small
  window. This is a design constraint, not an oversight.
"""

MAX_HISTORY_MESSAGES = 6   # 3 turns


def should_reset(user_input: str) -> bool:
    """Return True if the user asked to reset the conversation."""
    return user_input.lower().strip() in {"reset", "clear", "start over"}


def trim_history(history: list) -> list:
    """Cap history to MAX_HISTORY_MESSAGES most recent."""
    if len(history) > MAX_HISTORY_MESSAGES:
        return history[-MAX_HISTORY_MESSAGES:]
    return history