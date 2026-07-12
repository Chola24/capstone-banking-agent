"""Phase 3 LLM agent - same rule-based scaffold but the answer generation now goes through an LLM with retrieved context.

This is the 'evolution' step from baseline. Same CLI shape, but:
  - Uses retrieved chunks from FAISS (Phase 4 groundwork)
  - Sends a structured prompt to gpt-4o-mini
  - Prints sources with every answer

Run: python -m src.agent.llm_agent
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from src.config import (
    LLM_MODEL,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    VECTORSTORE_DIR,
    TOP_K,
    validate,
)
from src.agent.prompts import build_prompt, DEFAULT_PROMPT
# We import PROMPT_VARIANTS via the module for evaluation later
from src.agent import prompts as prompts_module


client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)
HISTORY_TURNS = 3
DEFAULT_VARIANT = "C_few_shot"


def load_vectorstore():
    """Load the FAISS index built by src/retrieval/ingest.py."""
    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE,
    )
    return FAISS.load_local(
        str(VECTORSTORE_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def retrieve_and_format(store, query: str, k: int = TOP_K) -> tuple:
    """Get top-k chunks and format for prompt injection + citation list."""
    docs = store.similarity_search(query, k=k)
    if not docs:
        return "(no relevant context found)", []

    parts, citations = [], []
    for i, doc in enumerate(docs, start=1):
        source = Path(doc.metadata.get("source", "?")).name
        page = doc.metadata.get("page", "?")
        parts.append(f"[Source {i}: {source}, page {page}]\n{doc.page_content}")
        citations.append({"source": source, "page": page})
    return "\n\n".join(parts), citations


def format_history(history: list) -> str:
    """Turn history tuples into readable text for the prompt."""
    if not history:
        return ""
    lines = []
    for user_msg, bot_msg in history[-HISTORY_TURNS:]:
        lines.append(f"User: {user_msg}")
        lines.append(f"Assistant: {bot_msg}")
    return "\n".join(lines)


def ask(question: str, store, history: list, variant: str = DEFAULT_VARIANT) -> tuple:
    """Answer one question. Returns (answer_text, citations_list)."""
    context, citations = retrieve_and_format(store, question)
    prompt = build_prompt(
        variant=variant,
        context=context,
        chat_history=format_history(history),
        question=question,
    )

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=500,
    )
    return response.choices[0].message.content.strip(), citations


def log_interaction(query: str, response: str, variant: str) -> None:
    """Append a PII-safe log line."""
    ts = datetime.now(timezone.utc).isoformat()
    with open("logs/interactions.log", "a", encoding="utf-8") as f:
        f.write(f"{ts} | LLM[{variant}] | Q: {query[:80]} | A: {response[:100]}\n")


def main():
    validate()
    print("Loading FAISS index...")
    store = load_vectorstore()

    print("=" * 60)
    print(f"LLM Banking Agent (Phase 3 - variant: {DEFAULT_VARIANT})")
    print("Type 'quit' or 'exit' to stop.")
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

        if citations and "don't have that in my documents" not in answer.lower():
            print("\nSources:")
            for c in citations:
                print(f"  - {c['source']}, page {c['page']}")

        log_interaction(question, answer, DEFAULT_VARIANT)
        history.append((question, answer))


if __name__ == "__main__":
    main()