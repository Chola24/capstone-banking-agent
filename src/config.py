"""Central configuration.

All tunable parameters live here. The rest of the codebase imports from
this module — no magic numbers scattered across ingest.py and chatbot.py.

This pattern matters for:
  - Reproducibility (one place to log all parameters)
  - Compliance (auditor can see every tunable in one file)
  - Iteration (tweak chunk_size in .env, no code change needed)
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Load environment variables from .env (silently no-op if file missing)
# -----------------------------------------------------------------------------
load_dotenv()

# -----------------------------------------------------------------------------
# Paths (resolved relative to project root, NOT to the current working dir)
# -----------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "knowledge" / "raw"
VECTORSTORE_DIR: Path = PROJECT_ROOT / "knowledge" / "faiss_index"

# -----------------------------------------------------------------------------
# OpenAI configuration
# -----------------------------------------------------------------------------
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE: str | None = os.getenv("OPENAI_API_BASE")  # Optional override

# -----------------------------------------------------------------------------
# Model selection
# -----------------------------------------------------------------------------
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# -----------------------------------------------------------------------------
# Chunking parameters
# -----------------------------------------------------------------------------
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "150"))

# -----------------------------------------------------------------------------
# Retrieval parameters
# -----------------------------------------------------------------------------
TOP_K: int = int(os.getenv("TOP_K", "4"))


# -----------------------------------------------------------------------------
# Validation — fail fast if required secrets are missing
# -----------------------------------------------------------------------------
def validate() -> None:
    """Raise a clear error if essential configuration is missing."""
    if not OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set.\n"
            "Fix: copy .env.example to .env and add your OpenAI key, "
            "or export OPENAI_API_KEY in your shell."
        )

    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Knowledge directory not found: {DATA_DIR}\n"
            "Fix: create it and add banking product PDFs."
        )
