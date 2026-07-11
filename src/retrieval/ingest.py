"""Document ingestion pipeline.

Reads PDFs from data/raw/, splits them into chunks, embeds each chunk
via OpenAI, and persists a FAISS index to vectorstore/.

Run once (or whenever documents change):
    python -m src.ingest
"""

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from src.config import (
    DATA_DIR,
    VECTORSTORE_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    validate,
)


def load_pdfs(data_dir: Path) -> List[Document]:
    """Read every PDF in data_dir. Each page becomes one Document."""
    pdf_files = sorted(data_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDFs in {data_dir}. Add source docs first.")

    print(f"Loading {len(pdf_files)} PDF(s) from {data_dir}")
    all_docs = []
    for pdf_path in pdf_files:
        # keep this a normal call, no fancy error handling — if a PDF is
        # broken we want to know immediately, not silently skip it
        loader = PyPDFLoader(str(pdf_path))
        pages = loader.load()
        print(f"  {pdf_path.name:45s} -> {len(pages):4d} pages")
        all_docs.extend(pages)

    print(f"Total pages loaded: {len(all_docs)}\n")
    return all_docs


def split_documents(documents: List[Document]) -> List[Document]:
    """Split page-level Documents into retrieval-sized chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    chunks = splitter.split_documents(documents)
    print(f"Split {len(documents)} pages -> {len(chunks)} chunks "
          f"(size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})\n")
    return chunks


def build_vectorstore(chunks: List[Document], save_path: Path) -> FAISS:
    """Embed chunks via OpenAI and save a FAISS index to disk.

    This is the step that spends money. Cost is roughly
    (total chars / 4) tokens * $0.02 / 1M — cents for our size.
    """
    print(f"Embedding {len(chunks)} chunks with {EMBEDDING_MODEL}...")
    print("(This takes 10-60 seconds. Watch for the save confirmation.)")

    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE,
    )
    store = FAISS.from_documents(chunks, embeddings)

    save_path.mkdir(parents=True, exist_ok=True)
    store.save_local(str(save_path))
    print(f"FAISS index saved to {save_path}\n")
    return store


if __name__ == "__main__":
    validate()
    docs = load_pdfs(DATA_DIR)
    chunks = split_documents(docs)
    build_vectorstore(chunks, VECTORSTORE_DIR)
    print("Ingestion complete. Ready for chatbot.\n")