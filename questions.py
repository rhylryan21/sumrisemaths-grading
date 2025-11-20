# Minimal, extendable question bank.
# For now: numeric-only questions (no variables).
# Later we can add types: "algebra", "fraction-simplify", etc.

QUESTIONS = [
    {
        "id": "q1",
        "topic": "arithmetic",
        "prompt": "Compute 3^2 + 4^2",
        "answer_expr": "3^2 + 4^2",  # 25
        "type": "numeric",
    },
    {
        "id": "q2",
        "topic": "fractions",
        "prompt": "Compute (1/2) + (1/3)",
        "answer_expr": "1/2 + 1/3",  # 5/6 ≈ 0.8333
        "type": "numeric",
    },
    {
        "id": "q3",
        "topic": "order-of-operations",
        "prompt": "Compute 7 - 3 * 2",
        "answer_expr": "7 - 3*2",  # 1
        "type": "numeric",
    },
]
