# Capability: MsSQL Connection

## What It Does

Establishes and maintains a read‑only connection pool to the large MsSQL database. Connection parameters come from environment variables (or a secure vault). The agent uses this connection to introspect schemas and execute queries.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| connection string | `str` (or parts) | `.env` / secrets manager | yes (configured at deploy time) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| connection pool | `sqlalchemy.Engine` | Injected into `mssql_query` tool |
| db_metadata | `dict` (tables, columns, types) | Cached in state, refreshed on demand |

## External Calls

| System | Operation | On Failure |
|---------|-----------|------------|
| MsSQL server | connect, inspect, query | Retry 3× with backoff; if still failing, set `confidence_flags.db_unavailable` and fall back to cached data or return a best‑effort answer with a warning |

## Business Rules

- All connections are **read‑only**; SQL validation ensures no DML/DDL.
- Use connection pooling to minimize overhead.
- Cache schema metadata for at least 5 min to reduce introspection queries.
- Queries must include an explicit `TOP` or `FETCH` limit; max rows returned = 10 000.

## Success Criteria

- [ ] Connection established within 1 s on warm pool.
- [ ] Schema cache refresh < 2 s for a 500‑table database.
- [ ] Query throughput ≥ 50 QPS with < 100 ms average latency for simple selects (on a 1 M‑row table).
