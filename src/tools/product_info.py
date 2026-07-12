"""Tool 1 - RAG-based product information lookup.

Wraps the FAISS retriever as a callable LangChain tool. The LLM agent invokes this when the user asks about banking products, rates, features,
or procedures.
"""
from pathlib import Path
from src.agent.llm_agent import load_vectorstore, retrieve_and_format


# Load once at import time — reused across many tool calls
_STORE = None


def _get_store():
    """Lazy-load the FAISS index so import doesnt trigger it."""
    global _STORE
    if _STORE is None:
        _STORE = load_vectorstore()
    return _STORE


def product_info_search(query: str) -> str:
    """Search bank product documents and return relevant chunks + sources.

    Args:
        query: natural-language question about products, rates, features,
               or banking procedures.

    Returns:
        A formatted string with retrieved context and source citations,
        suitable for the LLM to summarize into a final answer.
    """
    store = _get_store()
    context, citations = retrieve_and_format(store, query, k=4)

    if not citations:
        return "No relevant product information found in the bank documents."

    sources_line = "Sources: " + "; ".join(
        f"{c['source']} p.{c['page']}" for c in citations
    )
    return f"{context}\n\n{sources_line}"