import json
import base64
import anthropic
from fastapi import HTTPException
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from ...models.model import Upload, Process, Dbcredentials, SavedQuery



load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))  # picks up ANTHROPIC_API_KEY from env

SYSTEM_PROMPT = (
    "Generate one optimized MySQL SELECT query for the requested report. "
    "Rules:\n"
    "1. Identify only dynamic fields from the sample report (ignore static labels/headers/manual-fill fields).\n"
    "2. Map each dynamic field to a column in the sample JSON. Column identifiers in the "
    "generated SQL (in SELECT, JOIN, WHERE, GROUP BY, ORDER BY — before any AS alias) MUST be "
    "copied character-for-character, including exact case, from the keys in the sample JSON. "
    "Do NOT reformat, normalize casing, translate, abbreviate, or guess a column name — "
    "if the sample JSON key is 'SUBJECTNAME', the SQL must reference SUBJECTNAME, never "
    "subject_name or Subjectname. You may rename the OUTPUT column via 'AS alias' using a "
    "readable name, but the source column reference itself must be verbatim.\n"
    "3. If a field mentioned in the report has no matching key anywhere in the sample JSON, "
    "omit that field entirely rather than inventing a plausible-looking column for it.\n"
    "4. Use explicit JOIN...ON clauses.\n"
    "5. Use named parameters (:paramName) for any filter values instead of hardcoding.\n"
    "6. Default to a plain SELECT with no CTE. Only use a WITH clause and CASE WHEN pivoting "
    "if a single field's value must be split across multiple output columns based on another "
    "column's value (e.g. one 'marks' column that needs to become separate columns per unit/subject). "
    "If every requested field already corresponds to one column in one row per record, do not "
    "use a CTE — write a direct SELECT ... FROM ... JOIN ... WHERE ... ORDER BY.\n"
    "7. When a CTE is genuinely needed for pivoting, filter by the parameter before pivoting "
    "to avoid full table scans on large tables.\n"
    "Output ONLY the raw SQL statement — nothing else. No comments, no assumptions block, "
    "no explanation, no markdown code fences (no ``` at all). The response must start directly "
    "with SELECT or WITH and contain nothing but valid, executable SQL."

    "8. If reference queries from previously saved reports are provided, use them ONLY for "
    "structural and stylistic guidance — JOIN patterns, named-parameter conventions, CTE/pivot "
    "style, general query shape. NEVER copy a column name, table name, or alias from a "
    "reference query unless that exact name also appears in the CURRENT sample JSON provided "
    "above. A reference query may be for an entirely different table set, and its columns will "
    "not exist in this one — treat it as a pattern to learn from, not a source of truth for "
    "identifiers."
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

#     sql_text = clean_sql_output(sql_text)

#     if not sql_text:
#         raise HTTPException(502, "model returned an empty response")

#     return sql_text

def call_claude(content_blocks: list[dict]) -> str:
    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,   # bumped from 1500 — pivot-heavy queries with many CASE WHEN branches can be long
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

    if response.stop_reason == "max_tokens":
        # the model was still writing when it hit the token limit — what we have is
        # a genuinely truncated query, not a complete one. Surfacing this clearly beats
        # silently handing back broken SQL that looks complete until someone runs it.
        raise HTTPException(
            502,
            "the generated query was cut off before it finished — this report may need "
            "more output room than expected (a lot of pivoted columns, usually). "
            "Try again, or simplify the report/description and retry."
        )

    return sql_text



def find_similar_saved_queries(db: Session, connection_id: str, tables: list[str], report_type: str, limit: int = 2) -> list:
    """
    Finds previously saved queries for THIS connection that overlap with the current
    request — either by sharing tables, or matching report type. Only pulls from
    active, non-deleted rows: disabling a query is treated as "don't trust this as
    a reference anymore," same as it already means "don't offer this to reports."
    """
    candidates = (
        db.query(SavedQuery)
        .filter(
            SavedQuery.connection_id == int(connection_id),
            SavedQuery.active == True,
            SavedQuery.deleted_at.is_(None),
        )
        .all()
    )

    current_tables = set(tables)
    scored = []
    for sq in candidates:
        sq_tables = set(sq.tables or [])
        overlap = len(current_tables & sq_tables)
        type_match = 1 if report_type and sq.report_type and report_type.strip().lower() == sq.report_type.strip().lower() else 0
        score = overlap * 2 + type_match  # table overlap weighted higher than a type-name match
        if score > 0:
            scored.append((score, sq))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [sq for _, sq in scored[:limit]]