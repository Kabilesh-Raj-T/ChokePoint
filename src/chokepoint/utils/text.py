"""Text formatting helpers shared across ChokePoint modules."""

from __future__ import annotations

HUMAN_JOIN_PAIR_COUNT = 2


def escape_markdown_table(value: str) -> str:
    """Escape Markdown table separators in a cell value."""
    return value.replace("|", "\\|")


def escape_mermaid_label(value: str) -> str:
    """Escape Mermaid label text."""
    return value.replace('"', '\\"')


def human_join(values: tuple[str, ...]) -> str:
    """Join plain text values for human-readable explanations."""
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    if len(values) == HUMAN_JOIN_PAIR_COUNT:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def mermaid_node_id(value: str) -> str:
    """Return a stable Mermaid node id."""
    return "n_" + "".join(
        character if character.isalnum() else "_" for character in value
    )
