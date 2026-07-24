# Capability: SQL Generation

## What It Does

Generates a syntactically correct, read‑only SQL query from the user's natural language question, given the available data sources (CSV schemas and/or MsSQL metadata).

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| question | `str` | User message | yes |
| csv_schemas | `dict` | `load_csv` node | no |
| db_metadata | `dict` | `mssql_connection` node | no |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| sql_text | `str` | Passed to `validate_query` |
| reasoning | `str` | Shown in UI under “How I answered” |
| confidence | `float` (0–1) | Stored in state; if < 0.7, flag for best‑guess mode |

## External Calls

| System | Operation | On Failure |
|---------|-----------|------------|
| LLM | single call with prompt | If call fails (rate/500), retry once; if still failing, return a generic “I cannot answer right now” and set `confidence_flags.llm_unavailable` |

## Business Rules

- **Never** generate `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, or `EXEC`.
- Prefer parameterized queries only if user‑supplied values are present (avoid literal injection).
- If both CSV and DB sources exist, the agent may join across them (CSV treated as temporary views).
- Always include a `SELECT` + `FROM` + (optional `WHERE`, `GROUP BY`, `ORDER BY`, `LIMIT/TOP`). If the question is ambiguous, generate the *most likely* query and set `confidence < 0.7` to flag uncertainty.
- For CSV tables, reference them by the file’s UUID‑derived table name (e.g., `csv_<file_id>`).

## Success Criteria

- [ ] ≥ 90 % of generated queries are syntactically valid (tested against a sample schema).
- [ ] LLM produces non‑empty SQL within 3 s for 95 % of questions.
- [ ] Confidence correlates with correctness (R² > 0.6 on test set).
