# services/dbconn/describe.py
import json
import anthropic

client = anthropic.Anthropic()

DESCRIBE_TABLE_SYSTEM_PROMPT = (
    "You are documenting a database table for someone building SQL reports later. "
    "Given the table name and a few sample rows, write ONE short paragraph (1-3 sentences) "
    "describing what this table represents, what each row corresponds to, and when someone "
    "should join to or select from it. Be concrete — mention actual column names where useful "
    "(e.g. 'one row per student, keyed by studentcode'). Do not speculate about columns not "
    "shown in the sample. Output ONLY the description text — no preamble, no markdown, no "
    "quotes around it."
)


def generate_table_description(table_name: str, sample_rows: list[dict]) -> str:
    user_text = f"Table name: {table_name}\nSample rows (JSON): {json.dumps(sample_rows, ensure_ascii=False, default=str)}"
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=300,
            system=DESCRIBE_TABLE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_text}],
        )
    except anthropic.APIError as e:
        raise RuntimeError(f"AI description failed: {e}")

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise RuntimeError("model returned an empty description")
    return text