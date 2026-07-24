# API

The agent exposes a minimal HTTP API and serves a static frontend at `/app`. All endpoints produce/consume JSON. The API is stateless; each request is self-contained.

## Base URL

```
http://localhost:8001
```

(Production may use HTTPS; configure via `SSL_CERT`/`SSL_KEY` env vars.)

## Endpoints

### `POST /upload`

Upload CSV files for analysis. Files are stored temporarily in memory (not persisted to disk beyond the request lifecycle).

**Request:** `multipart/form-data` with field `files` (multiple).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | file (CSV) | No (but at least one needed for CSV-only queries) | One or more CSV files. Encoding: UTF-8. Max size: 10MB per file. |

**Response:** `200 OK`

```json
{
  "uploaded": [
    { "filename": "crime_data.csv", "rows": 15000, "columns": ["id", "date", "district", "offense"] }
  ]
}
```

The server does not return a session ID; the files are associated with the subsequent `/chat` request via a multipart body (see below). Alternatively, the client can send files directly in the `/chat` request; both patterns are supported. This endpoint is optional but convenient for UX: the user can upload once then ask multiple questions about the same CSVs during the same browser session. The server keeps uploaded files in an in-memory dict keyed by a temporary token in a cookie (or simply per-request upload). For simplicity, implement per-request uploads only (no persistence across requests). The `/upload` endpoint is a convenience that returns immediately; the chat request should include the same files again.

---

### `POST /chat`

Main agent endpoint. Accepts a natural language question and optionally CSV files, returns a complete answer with SQL, reasoning, chart, and result table.

**Request:** `multipart/form-data` (to allow both question and file uploads in one call) OR `application/json` with `question` only (DB-only query). Recommended: always send as multipart to be uniform.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | Yes | Natural language question about the data. |
| `files` | file (CSV) | No | One or more CSV files to analyze alongside the DB. |
| `user_id` | string | No | Opaque user identifier for audit logging (if not provided, `"anonymous"`). |

**Response:** `200 OK` on success; `4xx` on client error (e.g., no question); `5xx` on server error.

**Success payload (200):**

```json
{
  "run_id": "abc123",
  "answer": "Total incidents in 2023 were 45,231, with theft being the most common offense.",
  "sql": "SELECT district, COUNT(*) as incident_count FROM db.crime_data WHERE YEAR(date) = 2023 GROUP BY district ORDER BY incident_count DESC",
  "reasoning": "The user asked for total incidents. I filtered to 2023 and grouped by district to show distribution.",
  "chart": {
    "type": "bar",
    "data": {
      "labels": ["District A", "District B", "District C"],
      "datasets": [{ "label": "Incident count", "data": [12000, 9800, 7500] }]
    },
    "cache_hit": false
  },
  "result": {
    "columns": ["district", "incident_count"],
    "rows": [["District A", 12000], ["District B", 9800], ["District C", 7500]],
    "row_count": 3
  },
  "confidence": ["high"],
  "latency_ms": 42300,
  "warnings": []
}
```

**Error payload (4xx/5xx):**

```json
{
  "error": true,
  "code": "validation_error",
  "message": "No question provided.",
  "details": null,
  "run_id": "abc123"
}
```

Common error codes:
- `validation_error`: Request missing required fields.
- `unsafe_query`: The generated SQL was rejected by validator.
- `db_unavailable`: Cannot connect to MsSQL.
- `llm_error`: LLM provider failed to respond.
- `timeout`: Query or LLM call exceeded time limit.
- `internal_error`: Unexpected exception.

---

### `GET /health`

Simple health check for load balancers.

**Response:** `200 OK`

```json
{
  "status": "ok",
  "timestamp": "2025-12-19T10:30:00Z",
  "dependencies": {
    "database": "ok" | "down",
    "llm": "ok" | "down",
    "cache": "ok" | "down" | "disabled"
  }
}
```

The health check attempts a lightweight DB query (`SELECT 1`) if DB is configured and an LLM ping (list models or simple completion) to report status.

---

## Authentication & Rate Limiting

Phase 1: No auth. Phase 2: Optional API key via `X-API-Key` header; validate against a list in env `API_KEYS`. Rate limiting: 60 requests per minute per IP (configurable), deployed via `slowapi` or similar middleware.

## Error Handling & Observability

All server errors (5xx) are logged with `run_id`, request summary, and stack trace (in development). OTel traces are created per request; trace ID included in response header `X-Trace-Id`.

## Frontend Delivery

Static files are served from the `frontend/public/` directory relative to the server root at `/app`. The single-page app makes `fetch` calls to `/chat` (multipart/form-data) and updates the DOM with the response.

- `GET /app/` → returns `index.html`
- `GET /app/styles.css`
- `GET /app/app.js`

No other routes under `/app` are used.
