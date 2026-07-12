# Engineering & Product Justification

## Framework choice: LangChain (Track A)

Chose LangChain over CrewAI because Scenario 2 is a single-agent workflow (one specialist agent using multiple tools). CrewAI's strength is
multi-agent orchestration (roles, delegation) — we don't need that here. LangChain's AgentExecutor with StructuredTool bindings fits the workflow
exactly, and I already had working code from a prior RAG project that carried over cleanly.

## LLM: gpt-4o-mini, temperature=0

Deterministic responses matter in finance — same question should give the same answer across sessions. Non-zero temperature could produce
different rate quotes for the same query. Cost is negligible on the Vocareum budget.

## Vector store: FAISS

Local, persistent, cheap to reindex. For ~450 chunks (this project), in-memory FAISS is sub-millisecond per query. At 10K+ documents we'd move to a hosted
vector store (Pinecone, Weaviate) for horizontal scaling.

## Chunking: RecursiveCharacterTextSplitter, size=1000, overlap=150

Reused from a prior RAG project. Tuned so a typical policy paragraph (exit load, NAV formula, KYC procedure) stays in one chunk while
boundaries share context. Different corpora would want different values — legal contracts want bigger, short FAQs want smaller.

## Three tools, not two

Two tools would meet the minimum bar. I added a third — `check_eligibility`
— because it demonstrates a design principle:

> Not every step needs an LLM. Deterministic checks against clear rules
> should stay deterministic.

The eligibility tool is pure Python — no LLM inside. The LLM agent decides *when* to call it; the tool itself is fast, auditable, and always
returns the same answer for the same input. In banking, this matters:
"why did the bot say I was eligible?" needs to be answerable by pointing at a rule, not by re-running an LLM.

## Two-layer intent classification (planner + agent)

Rather than relying only on the LLM's ReAct planner, I added a lightweight Python-based intent classifier that runs *before* the AgentExecutor.
Reasons:

- Safety-critical categories (PII, transactional, high-risk) get flagged even before an LLM call, in case the LLM misclassifies
- Metrics — we can count intent distribution from logs
- Cheaper — clear out-of-scope questions can be refused without a full agent invocation

This is defense-in-depth, not redundancy. Both layers catching a query is the safe default; the layers acting as backup for each other is the point.

## Memory: short-term only, in-process

Retention: last 6 messages (3 turns). No cross-session persistence.
Deliberate design choice for banking compliance:

- Persistent conversation memory would risk storing customer context across sessions
- Cross-user aggregation is limited to intent categories, never raw content

Documented in `src/agent/memory.py` as a design constraint, not an oversight.

## Feedback loop: category-level, not user-level

The feedback store (`data/feedback/feedback_store.json`) records only intent category + thumbs up/down + timestamp. No raw queries stored.
Adaptation triggers on category patterns (>= 2 negatives in last 10 events) — cross-user learning without cross-user tracking.

Interview note: this is a lightweight substitute for real RLHF. In production this data would feed a proper labeling pipeline and periodic
prompt refinement.

## Safety: three layers

1. **Planner-side classification** — PII patterns, transactional keywords, high-risk phrases caught before the LLM sees them
2. **Tool descriptions** — every tool description tells the LLM what NOT to use it for, in addition to what it's for
3. **Log-side redaction** — interaction logs record intent + tools used + latency, never raw query text beyond a length prefix. PII never
   enters logs.

Defense in depth: any single layer failing shouldn't leak PII or allow a transaction.

## Deployment: CLI entrypoint, structured logs

`src/deployment/app.py` is the single entry point:

- Startup validates config before accepting queries (fail fast)
- Every turn wrapped in try/except; errors go to `logs/errors.log` with stack trace
- Every turn logs latency in milliseconds to `logs/interactions.log`
- Feedback prompt after each response (skippable)
- Special commands: `reset` (clear history), `stats` (feedback summary), `quit`

Production would sit this behind a FastAPI service with:
- API-gateway auth on the request boundary
- Rate limiting per user (prevent tool-loop DoS)
- Structured event pipeline (Kafka → Splunk) instead of file-based logs
- Shadow mode for A/B testing prompt changes
- Feature flags for gradual rollout (1% → 10% → 50%)

Kept CLI-only for the capstone because the agent logic — not the wrapper — is what's being graded.

## Trade-offs I explicitly accepted

- **Keyword-based guardrails miss creative phrasings** ("shift funds" not "transfer"). Acceptable at POC; production would need an LLM-based
  intent classifier.
- **No persistent memory limits personalization**. Acceptable for banking privacy compliance.
- **CLI interface, no auth**. Acceptable for grading; production would need proper AuthN/AuthZ.
- **Simple regex-based PII detection**. Misses OCR-encoded numbers, handwritten-style numerals in transcripts, etc. Production would use
  an ML classifier.
- **No LangSmith or Langfuse observability**. Structured local logs satisfy the minimum bar; observability platform would be my next
  addition in Day 3 polish.

## Deployment assumptions

- Customer identity is verified *before* the agent is invoked (agent runs in read-only advisory mode; auth is upstream)
- Source documents are current and pre-approved by compliance
- OpenAI-compatible API endpoint available (Vocareum or direct OpenAI)
- Python 3.10+ available on host
- Access to `data/`, `knowledge/`, `logs/` directories for read/write
- Single-user session at a time (no concurrent state management in POC)