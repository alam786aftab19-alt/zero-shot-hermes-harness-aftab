# Data Model

> Defines the application's own persistent data structures (not the police DB). These support caching, audit, and file metadata.

---

## Storage Technology

- **Primary DB**: SQLite (development) · PostgreSQL (production) via SQLAlchemy Core + asyncpg.
- **Why**: Lightweight, serverless for dev; PostgreSQL scales for concurrent audit/cache in production. The external MsSQL database is accessed read-only via pyodbc; it is NOT the app's primary DB.

## Entities

### Entity: `cached_query`

Stores query results to reduce DB load. TTL-based eviction.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | yes | Primary key |
| sql_hash | String(64) | yes | SHA256 of normalized SQL |
| sql_text | Text | yes | The exact SQL executed |
| result_json | JSON | yes | Serialized table (list of rows) |
| row_count | Integer | yes | Number of rows returned |
| created_at | DateTime | yes | Timestamp |
| expires_at | DateTime | yes | TTL expiry |
| csv_schemas_json | JSON | no | Snapshot of CSV schemas used (if any) |
| db_metadata_json | JSON | no | Snapshot of MsSQL schema/table/column metadata used |

### Entity: `audit_log`

Audit trail for every user question and agent action.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | yes | Primary key |
| timestamp | DateTime | yes | When the event occurred |
| user_id | String | no | Optional authenticated user identifier |
| question | Text | yes | The original user question |
| sql_generated | Text | no | SQL produced by the agent |
| data_sources | JSON | yes | List of sources used (CSV file IDs, MsSQL connection string hash) |
| result_preview | Text | no | Short preview (first few rows) |
| chart_config | JSON | no | Chart configuration if generated |
| confidence_flags | JSON | no | E.g., `{"low_confidence": true, "reason": "...`} |
| latency_ms | Integer | no | Total processing time |
| error | Text | no | Any error message if failed |

### Entity: `uploaded_file`

Metadata for CSV uploads; actual file stored on disk in `data/uploads/` with a UUID filename.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | UUID | yes | Primary key |
| original_filename | String | yes | User-provided name |
| stored_path | String | yes | Absolute path on server |
| upload_time | DateTime | yes | When uploaded |
| mime_type | String | yes | Expected `text/csv` |
| size_bytes | Integer | yes | File size |
| column_schema_json | JSON | yes | Inferred column names and types |

## Relationships

- `cached_query` has no foreign keys; it is keyed by `sql_hash`.
- `audit_log` references `uploaded_file.id` if the query used uploaded CSVs (many-to-one). This is optional; if no uploads, NULL.
- `uploaded_file` is independent; no cascade delete (files may be retained for audit).

## Data Lifecycle

- **Uploaded files**: kept for at least 90 days or until manually purged. Not auto-deleted.
- **Cache entries**: TTL 24 h by default. Eviction job runs every hour to remove expired rows.
- **Audit logs**: retained indefinitely (compliance). No automatic deletion.
- **Migrations**: Alembic manages schema changes. `alembic upgrade head` runs on container start.

## Sensitive Data

- `audit_log.user_id` may contain officer identifiers; treat as PII.
- `uploaded_file` original filenames could contain sensitive names; store only metadata, not exposing the original name in UI beyond initial upload confirmation.
- All data stays on-prem; no external telemetry.
