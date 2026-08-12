import json
import anthropic

client = anthropic.Anthropic()

SUGGEST_TABLES_SYSTEM_PROMPT = (
    "You are helping select which database tables are needed to build a report. You will "
    "be given a report type, an optional description of requirements, and a list of "
    "available tables (some with a short description of what they contain, others with no "
    "description at all — infer likely relevance from the table name in that case).\n"
    "Return ONLY a JSON array of table names that are likely needed for this report. "
    "You MUST copy table names character-for-character from the provided list — never invent, "
    "abbreviate, or reformat a table name. If unsure whether a table is needed, include it "
    "only if it's plausibly relevant — do not include unrelated tables just to be thorough. "
    "Output ONLY the JSON array, nothing else — no markdown fences, no prose."
)


def suggest_relevant_tables(report_type: str, description: str, table_lines: list[str], valid_tables: list[str]) -> list[str]:
    user_text = (
        f"Report type: {report_type or '(not specified)'}\n"
        f"Description: {description or '(not specified)'}\n\n"
        f"Available tables:\n" + "\n".join(table_lines)
    )
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=500,
            system=SUGGEST_TABLES_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_text}],
        )
    except anthropic.APIError as e:
        raise RuntimeError(f"table suggestion failed: {e}")

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        suggested = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"model returned unparseable output: {e}")

    valid_set = set(valid_tables)  # hard safety filter — never trust the model's names blindly
    return [t for t in suggested if t in valid_set]