"""Load the FAISS index and expose a simple retrieval interface.

"""

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from pathlib import Path
from typing import List, Tuple

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from src.config import (
    VECTORSTORE_DIR,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    TOP_K,
)


def load_retriever() -> FAISS:
    """Load the FAISS index that ingest.py built."""
    if not (VECTORSTORE_DIR / "index.faiss").exists():
        raise FileNotFoundError(
            f"No FAISS index at {VECTORSTORE_DIR}. "
            "Run `python -m src.ingest` first."
        )

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


def retrieve(store: FAISS, query: str, k: int = TOP_K) -> List[Document]:
    """Get the top-k most relevant chunks for a query."""
    return store.similarity_search(query, k=k)


def format_context(docs: List[Document]) -> Tuple[str, List[dict]]:
    """Turn retrieved docs into a single context string + a citations list.

    Returns:
        context_str: what we inject into the prompt
        citations:   [{source, page}, ...] for showing after the answer
    """
    if not docs:
        return "(no relevant context found)", []

    context_parts = []
    citations = []
    for i, doc in enumerate(docs, start=1):
        source = Path(doc.metadata.get("source", "?")).name
        page = doc.metadata.get("page", "?")
        context_parts.append(f"[Source {i}: {source}, page {page}]\n{doc.page_content}")
        citations.append({"source": source, "page": page})

    return "\n\n".join(context_parts), citations