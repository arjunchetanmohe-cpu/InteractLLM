import re
from sympy import Eq, solve
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)

transformations = standard_transformations + (implicit_multiplication_application,)


def check_letter_count(question: str):
    match = re.search(
        r"how many ['\"]?([a-zA-Z])['\"]?s?\b.*?\bin\b\s+['\"]?([a-zA-Z]+)['\"]?",
        question,
        re.I,
    )
    if match:
        letter, word = match.group(1), match.group(2)
        count = word.lower().count(letter.lower())
        return f"There are {count} '{letter.upper()}'s in \"{word}\"."
    return None


def solve_math(query: str) -> str:
    # 1. Check character/letter counting queries first (bypasses tokenizer issues)
    letter_result = check_letter_count(query)
    if letter_result:
        return letter_result

    try:
        query = query.replace("^", "**").strip()

        # 2. Handle equations with '=' (e.g., "2x + 5 = 15")
        if "=" in query:
            left_str, right_str = query.split("=", 1)
            left = parse_expr(left_str, transformations=transformations)
            right = parse_expr(right_str, transformations=transformations)
            free_vars = list((left - right).free_symbols)
            if not free_vars:
                return str(left == right)
            solutions = solve(Eq(left, right), free_vars)
            return f"{free_vars} = {solutions}"

        # 3. Handle standard arithmetic/algebraic expressions (e.g., "482 * 19" or "sqrt(144)")
        expr = parse_expr(query, transformations=transformations)
        result = expr.evalf() if expr.is_number else expr
        if getattr(result, "is_Integer", False) or (
            hasattr(result, "is_number") and result == int(result)
        ):
            return str(int(result))
        return str(result)
    except Exception as e:
        return f"Math Error: {e}"
