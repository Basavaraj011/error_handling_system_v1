# scripts/adaptive_cards.py

def table_card(title: str, rows: list[dict], max_rows: int = 10) -> dict:
    """
    Build a simple Adaptive Card that shows up to max_rows rows as FactSet.
    Keep it minimal for Teams webhook (display-only).
    """
    body = [
        {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium"}
    ]
    if not rows:
        body.append({"type": "TextBlock", "text": "No results.", "isSubtle": True})
    else:
        facts = []
        # Show each row as a list of key: value pairs
        for i, row in enumerate(rows[:max_rows], start=1):
            title_i = f"{i}."
            value_i = " \n".join([f"**{k}**: {row.get(k)}" for k in row.keys()])
            facts.append({"title": title_i, "value": value_i})
        body.append({"type": "FactSet", "facts": facts})

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": body
    }


def code_block_card(title: str, code_text: str) -> dict:
    """
    Render a monospaced block (e.g., the SQL that was executed).
    """
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {"type": "TextBlock", "text": title, "weight": "Bolder"},
            {"type": "TextBlock", "wrap": True, "fontType": "Monospace", "text": code_text}
        ]
    }
