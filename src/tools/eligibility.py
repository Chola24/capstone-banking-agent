"""Tool 3 - Deterministic eligibility check.

Runs a rule-based check for standard retail banking products. Used instead of an LLM inference so the answer is exact, auditable, and
fast. The LLM decides when to invoke this; the tool itself has no LLM inside.

This demonstrates a design principle: not every step in an agentic workflow needs an LLM. Deterministic checks against clear criteria
should stay deterministic.
"""

# Minimum eligibility rules - hard-coded here for demo; in production
# these come from the product policy config.
RULES = {
    "personal_loan": {
        "min_age": 21,
        "max_age": 60,
        "min_monthly_income": 25000,
        "note": "Salaried applicants only. Self-employed require separate criteria.",
    },
    "home_loan": {
        "min_age": 21,
        "max_age": 65,
        "min_monthly_income": 30000,
        "note": "Loan tenure capped at (65 - age) years.",
    },
    "credit_card_basic": {
        "min_age": 21,
        "max_age": 65,
        "min_monthly_income": 15000,
        "note": "Additional credit-score check applies at application time.",
    },
    "savings_account": {
        "min_age": 18,
        "max_age": 100,
        "min_monthly_income": 0,
        "note": "No minimum income requirement.",
    },
}




def check_eligibility(product: str, age: int, income: int) -> str:
    """Check basic eligibility for a banking product.

    Args:
        product: One of 'personal_loan', 'home_loan',
                 'credit_card_basic', 'savings_account'.
        age: Applicant's age in years.
        income: Monthly income in Indian Rupees.

    Returns:
        Structured eligibility verdict.
    """
    product = product.lower().strip()

    if product not in RULES:
        return (
            f"I dont have eligibility rules for '{product}'. "
            f"Supported products: {', '.join(RULES.keys())}."
        )

    rules = RULES[product]
    reasons_ineligible = []

    if age < rules["min_age"]:
        reasons_ineligible.append(f"minimum age is {rules['min_age']} (you are {age})")
    if age > rules["max_age"]:
        reasons_ineligible.append(f"maximum age is {rules['max_age']} (you are {age})")
    if income < rules["min_monthly_income"]:
        reasons_ineligible.append(
            f"minimum monthly income is Rs {rules['min_monthly_income']:,} "
            f"(you have Rs {income:,})"
        )

    if not reasons_ineligible:
        return (
            f"Eligible for {product}. Note: {rules['note']} "
            f"Final approval subject to full documentation and credit checks."
        )

    return (
        f"Not eligible for {product} at this time. Reason(s): "
        f"{'; '.join(reasons_ineligible)}. Note: {rules['note']}"
    )