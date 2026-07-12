"""Central tool registry using StructuredTool with typed schemas.

StructuredTool (rather than plain Tool) lets the LLM pass multiple named arguments to a tool. LangChain 1.x requires StructuredTool for
multi-arg functions; the plain Tool class raises ToolException.
"""
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from src.tools.product_info import product_info_search
from src.tools.escalate import create_escalation
from src.tools.eligibility import check_eligibility


# ---- Argument schemas for each tool -----------------------------------

class ProductInfoArgs(BaseModel):
    query: str = Field(
        description="Natural language question about a bank product, rate, feature, or procedure."
    )


class EligibilityArgs(BaseModel):
    product: str = Field(
        description="Product name. Must be one of: personal_loan, home_loan, credit_card_basic, savings_account."
    )
    age: int = Field(description="Applicant's age in years.")
    income: int = Field(description="Applicant's monthly income in Indian Rupees (INR).")


class EscalationArgs(BaseModel):
    category: str = Field(
        description="Escalation category. One of: transactional, pii_shared, bereavement, legal_advice, unclear, other."
    )
    reason: str = Field(
        description="One-line summary of why escalation is needed. Do NOT include PAN, Aadhaar, account numbers, or other PII."
    )


def get_tools() -> list:
    """Return all tools available to the agent."""
    return [
        StructuredTool.from_function(
            func=product_info_search,
            name="product_info_search",
            description=(
                "Use for questions about bank product features, interest rates, "
                "loan terms, KYC procedures, complaint procedures, or anything "
                "explainable from official bank documents. Do NOT use for "
                "account-specific data or transactions."
            ),
            args_schema=ProductInfoArgs,
        ),
        StructuredTool.from_function(
            func=check_eligibility,
            name="check_eligibility",
            description=(
                "Use when the user provides their age AND monthly income and "
                "asks if they qualify for a specific product. Do NOT ask for "
                "or use PAN, Aadhaar, or bank account numbers."
            ),
            args_schema=EligibilityArgs,
        ),
        StructuredTool.from_function(
            func=create_escalation,
            name="create_escalation",
            description=(
                "Use ONLY when: (a) user requests a transaction (transfer, "
                "close account, approve loan); (b) user shares personal data "
                "(PAN, Aadhaar, account number); (c) situation involves "
                "bereavement, legal issues, or is otherwise high-risk; or "
                "(d) user explicitly asks for a human. Returns a ticket ID "
                "and callback window."
            ),
            args_schema=EscalationArgs,
        ),
    ]