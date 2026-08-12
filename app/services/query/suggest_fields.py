import anthropic

client = anthropic.Anthropic()

SUGGEST_FIELDS_SYSTEM_PROMPT = (
    "You are helping someone define which fields should appear in a database report, "
    "when no sample report layout or image is available. You will be given the report "
    "type, an optional description of requirements, and sample JSON data showing the "
    "actual columns available across the tables involved.\n"
    "Propose the column headers / field labels that should appear in this report, based "
    "ONLY on what's actually present in the sample data. Never invent a field that isn't "
    "a real key in the sample JSON. Write the output as a report format description would "
    "normally look: a short list of column headers or section labels, one per line, in a "
    "sensible left-to-right order (identifying fields first, then descriptive fields, then "
    "numeric/measure fields). Output ONLY the field list text — no explanation, no markdown, "
    "no JSON, just plain lines as if pasting a report's column headers."
)


def suggest_report_fields(report_type: str, description: str, sample_json: str) -> str:
    user_text = (
        f"Report type: {report_type or '(not specified)'}\n"
        f"Description: {description or '(not specified)'}\n"
        f"Sample data (JSON): {sample_json}"
    )
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=500,
            system=SUGGEST_FIELDS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_text}],
        )
    except anthropic.APIError as e:
        raise RuntimeError(f"field suggestion failed: {e}")

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if not text:
        raise RuntimeError("model returned an empty field list")
    return text