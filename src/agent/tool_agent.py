"""Phase 5 tool-using agent.

Replaces the pure RAG chatbot with a LangChain AgentExecutor that can choose between 3 tools:
  - product_info_search: RAG retrieval over bank docs
  - check_eligibility: deterministic rule check
  - create_escalation: generate a ticket for handoff to human

Uses OpenAI function-calling via ChatOpenAI. Keeps a small in-memory conversation history for follow-ups.

Run: python -m src.agent.tool_agent
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from src.config import (
    LLM_MODEL,
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    validate,
)
from src.tools.tool_registry import get_tools
from src.agent.planner import classify, get_agent_hint
from src.feedback.collector import (
    record_feedback,
    get_adaptive_hint,
    get_summary,
)


# The system message that shapes tool selection and refusal behavior.
# Kept concise because the tool descriptions do most of the guardrail work.
SYSTEM_MESSAGE = SYSTEM_MESSAGE = """You are a banking support assistant for a retail bank in India.

TOOL USAGE RULES (strict — do NOT skip):

1. Product questions (rates, features, procedures, KYC, complaints):
   → ALWAYS call product_info_search first. Answer using its result with source citations.

2. Eligibility questions where user gives age AND income:
   → ALWAYS call check_eligibility with parsed values. Do NOT ask for PAN, Aadhaar, or account numbers.

3. TRANSACTION REQUEST (transfer, close account, approve, withdraw):
   → You MUST call create_escalation with category='transactional'. Never just say you created a ticket - always invoke the tool.

4. PII SHARED (user mentions PAN, Aadhaar, account number, mobile):
   → You MUST call create_escalation with category='pii_shared'. Do not use the PII in any downstream call.

5. HIGH-RISK (bereavement, legal, ambiguous):
   → You MUST call create_escalation with category='bereavement' or 'legal_advice' or 'unclear'.

6. Out-of-scope questions:
   → Say briefly you cannot help, offer to escalate if user wants.

CRITICAL: Never claim to have created a ticket without actually calling the create_escalation tool. The tool call is the source of
truth - your text is just the customer-facing wrapper around it.

Keep answers concise. Quote numbers verbatim from retrieved context."""


def build_agent():
    """Construct and return an AgentExecutor with our 3 tools bound."""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE,
        temperature=0,
    )

    tools = get_tools()

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_MESSAGE),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_openai_tools_agent(llm, tools, prompt)

    # max_iterations caps loops; return_intermediate_steps lets us
    # inspect which tools were chosen (used later in Phase 9 evaluation)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=4,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
    )


def log_interaction(query: str, answer: str, tool_names: list) -> None:
    """PII-safe interaction log with tool-selection trace."""
    ts = datetime.now(timezone.utc).isoformat()
    tools_used = ",".join(tool_names) if tool_names else "none"
    with open("logs/interactions.log", "a", encoding="utf-8") as f:
        f.write(
            f"{ts} | TOOL_AGENT | Tools:[{tools_used}] "
            f"| Q: {query[:80]} | A: {answer[:100]}\n"
        )


def main():
    validate()
    print("Loading tool-using agent...")
    executor = build_agent()

    print("=" * 60)
    print("Tool-Using Banking Agent (Phase 5)")
    print("Type 'quit' or 'exit' to stop.")
    print("=" * 60)

    chat_history = []  # list of HumanMessage / AIMessage

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

        from src.agent.memory import should_reset, trim_history

        if should_reset(question):
            chat_history = []
            print("Bot: Conversation reset. What can I help you with?")
            continue

        # Pre-flight intent classification (Phase 6 explicit planner)
        intent = classify(question)
        hint = get_agent_hint(intent)
        print(f"[Planner] intent={intent.category} confidence={intent.confidence}")

        # Adaptive hint from Phase 7 feedback loop
        adaptive = get_adaptive_hint(intent.category)
        if adaptive:
            print(f"[Adaptation] Applying learned caution based on recent negative feedback for '{intent.category}'")
        hint = hint + adaptive

        # Prepend the hint to the input so the LLM sees it before deciding on tools
        augmented_input = f"{hint}\n\nUser question: {question}" if hint else question

        result = executor.invoke({
            "input": augmented_input,
            "chat_history": chat_history,
        })

        answer = result["output"]
        # Extract tool names for logging + display
        tool_names = [
            step[0].tool for step in result.get("intermediate_steps", [])
        ]

        print(f"\nBot: {answer}")
        if tool_names:
            print(f"\n[Tools used: {', '.join(tool_names)}]")

        log_interaction(question, answer, tool_names)

        # Phase 7: solicit feedback (skip on quiet turns)
        try:
            fb = input("Was this helpful? (y/n/skip): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            fb = "skip"

        if fb in {"y", "yes"}:
            record_feedback(intent.category, True)
            print("[Thanks — feedback recorded]")
        elif fb in {"n", "no"}:
            record_feedback(intent.category, False)
            print("[Thanks — I'll try to do better next time]")
        # Anything else: no feedback, no record

        # Update chat history for follow-up handling
        chat_history.append(HumanMessage(content=question))
        chat_history.append(AIMessage(content=answer))

        # Cap history to last 6 messages (3 turns) to control token usage
        chat_history = trim_history(chat_history)


if __name__ == "__main__":
    main()