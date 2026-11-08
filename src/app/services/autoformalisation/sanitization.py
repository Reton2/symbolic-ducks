from __future__ import annotations


def to_canonical_identifier(raw_name: str) -> str:
    """Deterministically converts entity names into valid snake_case identifiers.

    Uses pure character iteration without regular expressions.
    """
    cleaned: list[str] = []
    prev_underscore = False

    for ch in raw_name.strip().lower():
        if ch.isalnum():
            cleaned.append(ch)
            prev_underscore = False
        elif not prev_underscore and len(cleaned) > 0:
            cleaned.append("_")
            prev_underscore = True

    result = "".join(cleaned).strip("_")
    if not result:
        return "unnamed_entity"
    if result[0].isdigit():
        return f"v_{result}"
    return result
