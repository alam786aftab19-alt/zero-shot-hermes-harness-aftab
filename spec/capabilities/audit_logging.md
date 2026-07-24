# Capability: Audit Logging

## What It Does

Records every user question, agent decisions, and outcome into the `audit_log` table for compliance and debugging.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| event_data | `dict` | Various nodes | yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| log_id | `UUID` | Inserted row; not shown to user |

## External Calls

| System | Operation | On Failure |
|---------|-----------|------------|
| app DB (PostgreSQL/SQLite) | `INSERT` into `audit_log` | If logging fails, write to local file as fallback and try again later; do NOT fail the user request |

## Business Rules

- Do not block the user response on successful DB write; fire‑and‑forget with a background task.
- Redact or omit raw data values in logs if flagged as sensitive (configurable).
- Include `timestamp`, `question`, `sql_generated`, `data_sources`, `latency_ms`, and any `error` or `confidence_flags`.
- In production, enable structured JSON logging to stdout for centralized collection.

## Success Criteria

- [ ] < 10 ms overhead on the critical path.
- [ ] ≥ 99.9 % of events successfully persisted (with fallback).
