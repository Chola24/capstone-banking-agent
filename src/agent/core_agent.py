"""RAG chatbot loop.

Ties together: retriever -> prompt -> LLM. Maintains a short history so
follow-up questions ("does that apply to me?") work.

Run:
    python -m src.chatbot
"""

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from openai import OpenAI

from src.config import (
    LLM_MODEL,
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    validate,
)
from src.retriever import load_retriever, retrieve, format_context
from src.prompts import build_prompt


# --- setup --------------------------------------------------------------
client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)

# Keep last N turns in history. Small so we don't burn tokens on old context.
HISTORY_TURNS = 3


def format_history(history: list) -> str:
    """Turn a list of (user, bot) tuples into readable text for the prompt."""
    if not history:
        return ""
    lines = []
    for user_msg, bot_msg in history[-HISTORY_TURNS:]:
        lines.append(f"User: {user_msg}")
        lines.append(f"Assistant: {bot_msg}")
    return "\n".join(lines)

def is_followup(question: str) -> bool:
    """Heuristic: does this question rely on prior context?

    Follow-ups use pronouns like 'this', 'that', 'it', or start with  'does', 'what about' etc. Standalone questions don't need the
    previous turn's question injected into retrieval - doing so  would pollute the search with unrelated context.
    """
    q = question.lower().strip()
    if q.startswith(("does", "what about", "and ", "also", "so ", "how about")):
        return True
    words = q.split()
    return len(words) < 10 and any(w in words for w in ("this", "that", "it", "those", "these"))

def ask(question: str, store, history: list) -> tuple:
    """Answer one question. Returns (answer_text, citations_list)."""
# Enrich retrieval query ONLY for follow-ups that need an anchor.
# For new-topic questions, adding the previous question pollutes

    if history and is_followup(question):
        last_q = history[-1][0]
        retrieval_query = f"{last_q} {question}"
    else:
        retrieval_query = question
    docs = retrieve(store, retrieval_query)
    context, citations = format_context(docs)

    # 2. build the prompt with context + history + question
    prompt = build_prompt(
        context=context,
        chat_history=format_history(history),
        question=question,
    )

    # 3. call the LLM
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,  # deterministic answers for finance content
        max_tokens=500,
    )
    answer = response.choices[0].message.content.strip()
    return answer, citations


def main():
    validate()
    print("Loading FAISS index...")
    store = load_retriever()
    print("Ready.\n")
    print("=" * 60)
    print("  Finance RAG Assistant — Mutual Funds")
    print("  Type 'quit' or 'exit' to stop.")
    print("=" * 60)

    history = []

    while True:
        try:
            question = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break

        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            print("Bye.")
            break

        answer, citations = ask(question, store, history)

        print(f"\nBot: {answer}")

        # show sources so the user can verify. This is our "citations" bonus.
        if citations and "don't have enough" not in answer.lower():
            print("\nSources:")
            for c in citations:
                print(f"  - {c['source']}, page {c['page']}")

        # save this turn so follow-ups work
        history.append((question, answer))


if __name__ == "__main__":
    main()