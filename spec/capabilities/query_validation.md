# Capability: Query Validation & Caching

## What It Does

Validates that the generated SQL is read‑only, within row limits, and does not reference forbidden system tables. It also checks the cache to reuse prior results when identical SQL and data sources have been executed recently.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| sql_text | `str` | `sql_generation` | yes |
| csv_schemas | `dict` | `load_csv` | no |
| db_metadata | `dict` | `mssql_connection` | no |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| validated_sql | `str` | Passed to `execute_sql` |
| cache_hit | `bool` | Stored in state; if true, skip execution and return cached result |
| cache_key | `str` (SHA256) | Used to look up `cached_query` |

## External Calls

| System | Operation | On Failure |
|---------|-----------|------------|
| cache DB | `SELECT` by `sql_hash` | If cache DB unreachable, log and continue (no cache) – does not block execution |

## Business Rules

- Disallow any keyword from the DML/DDL block (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `EXEC`, `sp_`).
- Require `TOP` or `FETCH` clause; if missing, automatically append `TOP 10000`.
- Reject queries that reference system tables (`sys.*`, `information_schema.*`) unless explicitly needed for schema introspection (not allowed in user‑facing).
- Normalize SQL (uppercase keywords, strip whitespace) before computing hash for cache lookup.
- Cache TTL = 24 h. If cache hit, populate `result_df` and `chart_config` directly and skip `execute_sql`.

## Success Criteria

- [ ] Validation latency < 50 ms.
- [ ] Cache hit rate ≥ 30 % for repetitive questions.
- [ ] Zero false negatives on safe read‑only queries.
