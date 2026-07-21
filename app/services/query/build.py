import json
import base64
import anthropic
from fastapi import HTTPException
import os
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))  # picks up ANTHROPIC_API_KEY from env

SYSTEM_PROMPT = (
    "Generate one optimized MySQL SELECT query for the requested report. "
    "Rules: identify only dynamic fields from the sample report (ignore static "
    "labels/headers/manual-fill fields). Map fields only to columns present in "
    "the sample JSON — never invent columns. Use explicit JOIN...ON clauses. "
    "Use named parameters (:paramName) for any filter values instead of "
    "hardcoding. If a field needs splitting into multiple columns (e.g. "
    "unit-wise or category-wise values in one column), pivot with CASE WHEN "
    "inside a CTE, filtered by the parameter before pivoting to avoid full "
    "table scans on large tables. "
    "Output ONLY the raw SQL statement — nothing else. No comments, no "
    "assumptions block, no explanation, no markdown code fences (no ``` at "
    "all). The response must start directly with SELECT or WITH and contain "
    "nothing but valid, executable SQL."
)


# ---- call Claude (unchanged) ----
import re
def clean_sql_output(sql_text: str) -> str:
    sql_text = sql_text.strip()

    # Strip a ```sql ... ``` fence if present (handles sql/mysql tag or none)
    fence = re.match(r"^```(?:sql|mysql)?\s*\n(.*)\n```\s*$", sql_text, re.DOTALL | re.IGNORECASE)
    if fence:
        sql_text = fence.group(1).strip()

    # Cut everything before the first top-level SELECT or WITH — this removes any
    # assumptions block, prose, or preamble no matter how the model formatted it
    match = re.search(r"\b(SELECT|WITH)\b", sql_text, re.IGNORECASE)
    if match:
        sql_text = sql_text[match.start():].strip()

    return sql_text

def call_claude(content_blocks: list[dict]) -> str:
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content_blocks}],
        )
    except anthropic.APIError as e:
        raise HTTPException(502, f"query generation failed: {e}")

    sql_text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    sql_text = clean_sql_output(sql_text)

    if not sql_text:
        raise HTTPException(502, "model returned an empty response")

    return sql_text

# def call_claude(content_blocks: list[dict]) -> str:
#     try:
#         response = client.messages.create(
#             model="claude-opus-4-5",
#             max_tokens=1500,
#             system=SYSTEM_PROMPT,
#             messages=[{"role": "user", "content": content_blocks}],
#         )
#     except anthropic.APIError as e:
#         raise HTTPException(502, f"query generation failed: {e}")

#     sql_text = "".join(
#         block.text for block in response.content if block.type == "text"
#     ).strip()

#     # safety net, in case the model still wraps output in a fence sometimes
#     if sql_text.startswith("```"):
#         sql_text = sql_text.strip("`").strip()
#         if sql_text.lower().startswith("sql"):
#             sql_text = sql_text[3:].strip()

#     if not sql_text:
#         raise HTTPException(502, "model returned an empty response")

#     return sql_text


