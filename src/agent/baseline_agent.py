"""Phase 2 baseline agent — rule-based, no LLM.

This is deliberately limited  to show:
  1. What a naive rule-based version can do (very little)
  2. Why we NEED LLM + RAG (documented limitations)


"""
import re
from datetime import datetime, timezone


TRANSACTIONAL_KEYWORDS = [
    "transfer", "send money", "move funds", "withdraw",
    "close account", "approve", "pay bill", "book fd",
]

LEGAL_KEYWORDS = [
    "legal advice", "should i sue", "draft a will",
    "tax advice", "tax filing",
]

CANNED_RESPONSES = {
    "hi": "Hello! I can help with basic banking product questions.",
    "hello": "Hi there. Ask me a question about our banking products.",
    "home loan": (
        "Home loan interest rates typically range from 8-9%. "
        "For exact rates, please refer to our official rate sheet."
    ),
    "savings": (
        "Our savings account has zero minimum balance for the basic tier. "
        "Please check the branch for premium tier details."
    ),
}

REFUSAL_TRANSACTIONAL = (
    "I can't help with transactions. Please use your mobile banking app "
    "or contact your branch."
)

REFUSAL_LEGAL = (
    "I can't provide legal or tax advice. Please consult a qualified "
    "professional."
)

DEFAULT_FALLBACK = (
    "I don't have a specific answer for that. Please contact customer "
    "care at 1800-XXX-XXXX."
)


def classify_and_respond(user_query: str) -> str:
    """The whole agent, in 15 lines. Pattern-match, return a canned reply."""
    q = user_query.lower().strip()

    # Refusal patterns first (safety)
    if any(kw in q for kw in TRANSACTIONAL_KEYWORDS):
        return REFUSAL_TRANSACTIONAL

    if any(kw in q for kw in LEGAL_KEYWORDS):
        return REFUSAL_LEGAL

    # Match canned responses
    for keyword, response in CANNED_RESPONSES.items():
        if keyword in q:
            return response

    return DEFAULT_FALLBACK


def log_interaction(query: str, response: str) -> None:
    """Basic interaction logger. Uppercase writes real logs later."""
    ts = datetime.now(timezone.utc).isoformat()
    with open("logs/interactions.log", "a", encoding="utf-8") as f:
        f.write(f"{ts} | BASELINE | Q: {query} | A: {response[:80]}\n")


def main():
    """Baseline agent CLI. Type 'quit' to exit."""
    print("=" * 60)
    print("Baseline Banking Agent (Phase 2 — rule-based, NO LLM)")
    print("Type 'quit' or 'exit' to stop.")
    print("=" * 60)

    while True:
        try:
            user_query = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break

        if not user_query:
            continue
        if user_query.lower() in {"quit", "exit", "q"}:
            print("Bye.")
            break

        response = classify_and_respond(user_query)
        print(f"\nBot: {response}")
        log_interaction(user_query, response)


if __name__ == "__main__":
    main()