"""Deployment entry point for the Banking Support Agent.

Single script that handles:
  - Config validation (fail fast if env is misconfigured)
  - Graceful startup (loads FAISS index, warms LLM client)
  - Structured logging with latency + errors
  - Clean shutdown

Run:
    python -m src.deployment.app

For a production deployment, this would sit behind a FastAPI or a
job queue. Kept as CLI for the capstone POC.
"""
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage, AIMessage

from src.config import validate
from src.agent.tool_agent import build_agent, log_interaction
from src.agent.planner import classify, get_agent_hint
from src.agent.memory import should_reset, trim_history
from src.feedback.collector import (
    record_feedback,
    get_adaptive_hint,
    get_summary,
)


ERROR_LOG = Path("logs/errors.log")
INTERACTION_LOG = Path("logs/interactions.log")


def log_error(exc: Exception, context: str = "") -> None:
    """Append an error to logs/errors.log with a stack trace."""
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n{ts} | ERROR | context={context}\n")
        f.write(traceback.format_exc())
        f.write("\n")


def log_latency(question: str, tool_names: list, latency_ms: int, status: str) -> None:
    """Structured interaction log with latency in milliseconds."""
    INTERACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    tools = ",".join(tool_names) if tool_names else "none"
    with open(INTERACTION_LOG, "a", encoding="utf-8") as f:
        f.write(
            f"{ts} | DEPLOY | status={status} | latency_ms={latency_ms} "
            f"| tools=[{tools}] | q_len={len(question)}\n"
        )


def startup() -> tuple:
    """Validate config, load agent. Return (executor, error_or_none)."""
    print("=" * 60)
    print("Banking Support Agent — Deployment Entrypoint")
    print(f"Startup at {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    try:
        validate()
        print("[startup] Config validated")
    except Exception as e:
        log_error(e, "config_validation")
        return None, f"Config validation failed: {e}"

    try:
        executor = build_agent()
        print("[startup] Agent ready")
        return executor, None
    except Exception as e:
        log_error(e, "agent_build")
        return None, f"Agent build failed: {e}"


def handle_turn(executor, question: str, chat_history: list) -> tuple:
    """Process one turn with full error handling.

    Returns (answer, tool_names, chat_history, latency_ms, error_or_none).
    """
    t0 = time.time()
    try:
        intent = classify(question)
        hint = get_agent_hint(intent)
        adaptive = get_adaptive_hint(intent.category)

        if adaptive:
            print(f"[Adaptation] Applying learned caution for '{intent.category}'")

        print(f"[Planner] intent={intent.category} confidence={intent.confidence}")

        augmented = f"{hint}{adaptive}\n\nUser question: {question}" if (hint or adaptive) else question

        result = executor.invoke({
            "input": augmented,
            "chat_history": chat_history,
        })
        answer = result["output"]
        tool_names = [step[0].tool for step in result.get("intermediate_steps", [])]

        chat_history.append(HumanMessage(content=question))
        chat_history.append(AIMessage(content=answer))
        chat_history = trim_history(chat_history)

        latency_ms = int((time.time() - t0) * 1000)
        return answer, tool_names, chat_history, intent, latency_ms, None

    except Exception as e:
        log_error(e, f"handle_turn: {question[:40]}")
        latency_ms = int((time.time() - t0) * 1000)
        fallback = (
            "Sorry — I hit a technical issue processing that. "
            "I've logged the error and a specialist can be alerted if needed."
        )
        return fallback, [], chat_history, None, latency_ms, str(e)


def main():
    executor, startup_err = startup()
    if startup_err:
        print(f"\nFATAL: {startup_err}")
        sys.exit(1)

    print("\nType 'quit' to exit, 'reset' to clear history, 'stats' for feedback summary.\n")

    chat_history = []

    while True:
        try:
            question = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break

        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            print("Bye.")
            break
        if should_reset(question):
            chat_history = []
            print("Bot: Conversation reset.\n")
            continue
        if question.lower() == "stats":
            print(f"Bot: Feedback summary: {get_summary()}\n")
            continue

        answer, tool_names, chat_history, intent, latency_ms, err = handle_turn(
            executor, question, chat_history
        )

        print(f"\nBot: {answer}")
        if tool_names:
            print(f"[Tools: {', '.join(tool_names)}]")
        print(f"[Latency: {latency_ms}ms]\n")

        status = "error" if err else "ok"
        log_latency(question, tool_names, latency_ms, status)

        if not err:
            log_interaction(question, answer, tool_names)

            # Feedback loop
            try:
                fb = input("Was this helpful? (y/n/skip): ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                fb = "skip"

            if fb in {"y", "yes"} and intent:
                record_feedback(intent.category, True)
                print("[Thanks — recorded]\n")
            elif fb in {"n", "no"} and intent:
                record_feedback(intent.category, False)
                print("[Thanks — will improve]\n")


if __name__ == "__main__":
    main()