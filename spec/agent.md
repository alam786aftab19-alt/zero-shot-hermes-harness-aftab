# Agent

This project uses an agent framework (LangGraph) to orchestrate the reasoning and tool use. The agent operates in a single-turn fashion; each request creates a fresh graph execution with its own state.

## Agent Architecture Pattern

**Chosen:** Graph (LangGraph) — The agent follows a multi-step pipeline with conditional edges (e.g., validation failure → fallback; cache hit → skip execution; error → handle_error). This enables clear separation of concerns, checkpointing (not strictly needed but supported), and easy addition of nodes in later phases. The graph is compiled once at startup and invoked per user request.

## LLM Provider & Model

The agent uses a single LLM provider for all generation steps. The provider and model are configurable via environment variables to support on-premise deployments.

| Agent / Node | Provider | Model ID | Rationale |
|--------------|----------|----------|-----------|
| All LLM nodes (parse, SQL gen, chart type selection) | Configurable (e.g., StepFun, Ollama, LocalAI) | `step-3.5-flash` or `llama3.1:70b` (example) | Must be capable of structured output (JSON or tool calls). Latency-critical: need < 5s per LLM call. On-prem ensures data sovereignty. |

**Fallback behaviour:** If the LLM API is unreachable or returns an error, the agent switches to a rule-based stub: simple keyword matching to pre-defined query templates. The answer is returned with a `confidence: "low"` and `fallback: true` flag. The graph continues without raising a fatal error.

**Prompt strategy:** Each node uses a separate, focused system prompt. All prompts are stored in `src/prompts/`. The agent uses structured JSON output modes (no plain text). For nodes that call tools (e.g., `execute_query`), the LLM is not used; those are code functions. Only reasoning and generation nodes call the LLM.

## Tools & Tool Calling

The agent orchestrates both LLM nodes and direct function calls. These are the "tools" the graph uses:

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `load_csv` | Parse uploaded CSV files into pandas DataFrames; infer column types and sample values | List of file paths or UploadFile objects | Dict: `{filename: {columns: [...], sample_rows: [...], dtypes: {...}}}` | Temporary in-memory storage; no DB write |
| `get_db_metadata` | Introspect MsSQL database: list tables, columns, types, primary/foreign keys | Connection string (from config) | Dict: `{table_name: {columns: [...], dtypes: {...}}}` | Read-only DB query |
| `generate_sql` (LLM node) | Given question, schema description, and optional cache hint, produce a SQL query and reasoning | `question`, `schemas` (CSV + DB), `cache_key` (optional) | `{sql: str, reasoning: str, target_source: "csv"|"mssql"|"both"}` | None (pure generation) |
| `validate_query` | Check if SQL is read-only, within row limits, and estimated cost acceptable | `sql`, `dialect` | `{valid: bool, reason: str}` | None |
| `get_cache` | Look up cached result for normalized query hash | `query_hash` | `{hit: bool, result: DataFrame|None, chart_data: dict|None}` | None |
| `execute_query` | Run SQL against chosen backend (CSV via pandas `.query()` or MsSQL via SQLAlchemy) | `sql`, `target_source` | `{columns: [...], rows: [...], row_count: int, execution_time_ms: int}` | DB/CSV read |
| `set_cache` | Store query result and chart config in cache with TTL | `query_hash`, `result`, `chart_data`, `ttl` | `{stored: bool}` | Cache write |
| `generate_chart` (LLM node) | Given result set and question, pick chart type and configuration | `columns`, `rows`, `question` | `{chart_type: "bar"|"line"|"pie"|"scatter", config: dict (Chart.js format)}` | None |
| `log_audit` | Write audit record to DB/file | `user_id`, `question`, `sql`, `result_summary`, `confidence_flags`, `latency_ms` | None | Audit append |

**Tool selection strategy:** The graph nodes directly call these tools in sequence; there is no LLM-based tool selection. The flow is deterministic: parse → schema → generate SQL → validate → cache → execute → chart → finalize. LLM is only used inside the `generate_sql` and `generate_chart` nodes. This keeps the graph predictable and fast.

**Tool failure handling:** Each function raises a descriptive exception on failure. The node that calls it catches exceptions and writes `state["error"]`. The graph then routes to `handle_error` node. Non-fatal failures (e.g., cache miss, validation fail) are handled within the node by setting flags and continuing; only hard failures (DB down, LLM unreachable) trigger error routing.

## Agent State

The full state type (TypedDict) used by the graph:

```python
class AgentState(TypedDict):
    # Identity & context
    run_id: str                          # UUID for this request
    received_at: float                   # Unix timestamp
    user_id: str | None                  # From auth header if any (optional)

    # Input
    question: str                        # User's natural language question
    csv_files: list[UploadFile] | None   # Uploaded files (only at start)
    csv_schemas: dict | None             # Populated by load_csv: {filename: {...}}
    use_mssql: bool                      # Whether DB connection is configured

    # Pipeline data (populated progressively)
    db_metadata: dict | None             # From get_db_metadata if use_mssql
    combined_schema: dict | None         # Unified virtual schema (CSV + DB)
    reasoning: str | None                # Reasoning from generate_sql node
    sql: str | None                      # Generated SQL query
    target_source: str | None            # "csv", "mssql", or "both"
    validation: dict | None              # {valid: bool, reason: str}
    cache_key: str | None                # SHA256 of normalized SQL
    cache_hit: bool                      # Did we use cached result?
    result: dict | None                  # {columns: [...], rows: [...], row_count: int}
    chart_config: dict | None            # Chart.js or Plotly config
    confidence_flags: list[str]          # e.g., "uncertain_schema", "fallback_llm", "cache_stale"

    # Control
    error: str | None                    # Set by any node on fatal failure
    checkpoint: str | None              # Last completed node name
    latency_ms: int | None              # Total duration set at end
```

## Nodes / Steps

### `node_load_csv`

**Reads from state:** `csv_files`
**Writes to state:** `csv_schemas`, `received_at`
**LLM call:** No
**External calls:** File I/O (CSV parsing)
**Behaviour:** For each uploaded CSV, use pandas to read the first 100 rows; infer column types and collect sample values. Store in `csv_schemas`. If no files, `csv_schemas` remains None. On error, set `state["error"]` with details.

---

### `node_get_db_metadata`

**Reads from state:** `use_mssql`
**Writes to state:** `db_metadata`
**LLM call:** No
**External calls:** MsSQL via SQLAlchemy (reads information_schema)
**Behaviour:** If `use_mssql` is true and DB connection is configured, introspect: list all user tables, columns, data types, primary/foreign keys. Build a nested dict. Cache this metadata in-process for the lifetime of the server (reuse across requests). On failure (DB down/credentials invalid), set `state["error"]` and route to error; also set `use_mssql = false` for this request to fall back to CSV-only.

---

### `node_infer_schema`

**Reads from state:** `csv_schemas`, `db_metadata`, `question`
**Writes to state:** `combined_schema`
**LLM call:** No (pure data fusion)
**External calls:** None
**Behaviour:** Merge `csv_schemas` and `db_metadata` into a single virtual schema description the LLM will later use to generate SQL. The format is a dict: `{source: {tables/dfs: {columns: [...], types: {...}}}}`. If both sources have a table/df with same name, disambiguate with prefixes (e.g., `csv.mytable` vs `db.mytable`). The schema should include column names and simple type hints (string, integer, float, datetime). This node prepares the context for the SQL generation LLM.

---

### `node_generate_sql`

**Reads from state:** `question`, `combined_schema`
**Writes to state:** `sql`, `reasoning`, `target_source`
**LLM call:** Yes — prompt includes system message and the question + schema. Model instructed to output JSON: `{sql: str, reasoning: str, target_source: "csv"|"mssql"|"both"}`.
**External calls:** LLM provider API
**Behaviour:** The LLM generates a syntactically correct SQL query (T-SQL dialect for MsSQL; pandas `.query()` syntax for CSV) that answers the question. It must read-only, include a LIMIT if no grouping, and prefer aggregations where appropriate. It also produces a short reasoning paragraph explaining how it interpreted the question and chose tables/columns. If the LLM call fails, the exception is caught; the node sets a `fallback_sql` (very simple pattern, e.g., `SELECT COUNT(*) FROM <first_table>`) and sets `confidence_flags` to include `"fallback_llm"`.

---

### `node_validate_query`

**Reads from state:** `sql`, `target_source`
**Writes to state:** `validation`
**LLM call:** No
**External calls:** For MsSQL: parse query with sqlparse and optionally call `EXPLAIN` (or `SET SHOWPLAN_TEXT ON`) to estimate cost; for CSV: lightweight syntax check only.
**Behaviour:**
- Ensure read-only: only `SELECT` allowed; reject `INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.
- Enforce `TOP`/`LIMIT` or `SET ROWCOUNT` if not present; add implicit `TOP 1000` for MsSQL to cap rows.
- Check for dangerous patterns (e.g., cross joins without filters that could explode). If found, mark invalid and suggest safer alternative.
- For MsSQL: optionally run `SET STATISTICS IO, TIME OFF; SET SHOWPLAN_TEXT ON; <sql>` to get estimated row reads; if estimate > `MAX_ESTIMATED_ROWS` (config), reject.
- Result stored in `validation: {valid: bool, reason: str}`. If invalid, the graph may still proceed with a fallback or return error to user; Phase 1 treats invalid as a flag and tries a simpler query.

---

### `node_check_cache`

**Reads from state:** `sql`, `target_source`
**Writes to state:** `cache_hit`, `cache_key`
**LLM call:** No
**External calls:** Cache store (Redis/SQLite/in-memory)
**Behaviour:** Compute a deterministic hash of `(sql, target_source, maybe schema_version)`. Look up in cache. If hit and result is not stale, populate `state["result"]` and `state["chart_config"]` from cache, and set `cache_hit = true`. If miss, `cache_hit = false` and `result` remains None. On cache error (e.g., Redis down), log and continue without caching.

---

### `node_execute_query`

**Reads from state:** `sql`, `target_source`, `validation`
**Writes to state:** `result` (if not cached), `execution_time_ms`
**LLM call:** No
**External calls:** CSV (pandas) or MsSQL (SQLAlchemy)
**Behaviour:**
- If `cache_hit` is true, skip execution (result already set).
- Else, execute the SQL with a timeout (e.g., 30 seconds). Use `pandas.read_sql` for CSV: load CSV into a temporary DataFrame and run `pandas.read_sql(sql, conn)` where conn is a SQLite in-memory DB for pandas? Actually simpler: converting CSV -> pandas, then filter with `.query()` for pandas syntax; but easier: load CSVs into SQLite in-memory for true SQL support. For Phase 1, we can use DuckDB or SQLite in-memory to run SQL on CSVs. That unifies query execution. Recommended: use DuckDB in-memory — can query CSVs directly with SQL. That's simpler.
- For MsSQL: use SQLAlchemy engine to execute; fetch results in batches if large.
- After execution, build result dict: `{columns: list of column names, rows: list of row dicts (limit to 1000 rows for charting), row_count: total rows (may be approximate)}`
- If timeout or error, set `state["error"]` and also possibly partial `result` if some rows retrieved. Add confidence flag `"query_timeout"`.

---

### `node_generate_chart`

**Reads from state:** `result`, `question`, `sql`
**Writes to state:** `chart_config`
**LLM call:** Yes — picks chart type and axis mapping.
**External calls:** None (chart config only; actual rendering is frontend)
**Behaviour:** The LLM node inspects the result shape (number of columns, types) and the original question to select an appropriate chart type from {bar, line, pie, scatter, table}. It then produces a Chart.js configuration object: `{type: "bar", data: {labels: [...], datasets: [{label: "...", data: [...]}]}}`. The configuration must be pure JSON without executable code. If the result is empty or unsuitable for charting, returns a "no chart" marker and reasoning. On LLM failure, fallback to rule-based: if 1 dimension + 1 metric => bar; time series => line; single category distribution => pie.

---

### `node_finalize_response`

**Reads from state:** All relevant fields
**Writes to state:** Nothing; assembles final response dict.
**LLM call:** No
**External calls:** `log_audit`
**Behaviour:** Build the final JSON response to the user:
```json
{
  "answer": "<text summary generated optionally; if empty, just 'Here are the results'>",
  "sql": "...",
  "reasoning": "...",
  "chart": { ...chart_config..., "cache_hit": boolean },
  "result": { "columns": [...], "rows": [...], "row_count": int },
  "confidence": ["medium"], // e.g., "high", "medium", "low"
  "warnings": [], // e.g., "approximate row count", "data from CSV only (DB unavailable)"
}
```
Also calls `log_audit` to write an immutable audit record. Set `state["latency_ms"]`. Return response to API layer.

---

### `node_handle_error`

**Reads from state:** `error`, `run_id`, `question`
**Writes to state:** None (terminates)
**LLM call:** Optional — can generate user-friendly error message from the error string.
**External calls:** `log_audit`
**Behaviour:** When any node sets `state["error"]`, the graph routes here. This node creates a user-safe error response (no stack traces). It may include partial results if available. Categories: `validation_error`, `db_unavailable`, `llm_error`, `cache_error`, `timeout`. The response JSON includes `"error": true, "message": "...", "details": "...", "suggestions": [...]`. Logs the failure with full context. The graph ends after this node.

## Graph / Flow Topology

```
START
  │
  ▼
node_load_csv ──(error)──► node_handle_error ──► END
  │
  ▼
node_get_db_metadata ──(error)──► node_handle_error ──► END
  │
  ▼
node_infer_schema
  │
  ▼
node_generate_sql ──(error)──► node_handle_error ──► END
  │
  ▼
node_validate_query
  │
  ▼
node_check_cache ──(cache_hit)──► node_finalize_response ──► END
  │
  ▼ (cache_miss)
node_execute_query ──(error)──► node_handle_error ──► END
  │
  ▼
node_generate_chart ──(error)──► node_handle_error ──► END
  │
  ▼
node_finalize_response ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `node_load_csv` | `state["error"] is not None` | `node_handle_error` |
| `node_get_db_metadata` | `state["error"] is not None` | `node_handle_error` |
| `node_generate_sql` | `state["error"] is not None` | `node_handle_error` |
| `node_validate_query` | (always proceed; invalid sets flag, not error unless unrecoverable) |
| `node_check_cache` | `state["cache_hit"] == True` | `node_finalize_response` (skips execute & chart, but chart already cached) |
| `node_check_cache` | `state["cache_hit"] == False` | `node_execute_query` |
| `node_execute_query` | `state["error"] is not None` | `node_handle_error` |
| `node_generate_chart` | `state["error"] is not None` | `node_handle_error` |

**Notes:**
- The cache stores both the result set and the chart config, so on a cache hit we skip execution AND chart generation.
- Validation failures do not route to error; they set `validation.valid = false` and the agent continues (may still execute if not dangerous, or may fallback to a safe query in `node_generate_sql` via re-prompt? For simplicity, Phase 1 & 2 treat validation as a warning and execute with row limit enforced by the executor if it's read-only but expensive. In Phase 3, we may add a reformulation node.

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph state (in-memory dict) | All intermediate data (CSV DataFrames, SQL, results, chart config) |
| **Across runs** | None (single-turn only) | No user history or preferences |
| **Conversation** | None | Each request is independent |

**Context window management:** Not applicable (single LLM call per node; no long conversation). Prompts are small (< 4K tokens) because schema descriptions are concise.

## Human-in-the-Loop Checkpoints

Not applicable. The agent is fully automated per request and never pauses for human input. It must produce an answer (or error) within the turn.

## Error Handling & Recovery

**Node-level:** Each node catches its own exceptions. On expected failures (e.g., file parse error, DB connection failure, LLM API error), it sets `state["error"]` with an error code and message. Unexpected exceptions are logged with stack trace and also set `state["error"]`.

**Graph-level (`handle_error` node):**
- Reads: `state["error"]`, `state["run_id"]`
- Calls `log_audit` with error details.
- Produces a user-friendly JSON response:
  ```json
  {
    "error": true,
    "code": "db_unavailable",
    "message": "The database is currently unreachable. Try again later or use CSV-only queries.",
    "partial": { ...partial state if any... }
  }
  ```
- Terminates graph.

**Resume / retry strategy:** No resume; each request is independent. Clients can retry the same question.

**Partial failure:** If a non-critical part fails (e.g., cache unavailable, chart generation fails), the node sets a confidence flag but does not set `error`. The graph continues to `finalize_response` with partial output (e.g., result table but no chart, or default chart).

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | One trace per request, one span per node (LangGraph automatically creates spans if OTel is configured). Include `run_id` in all spans. | OpenTelemetry SDK with console exporter (Phase 1), OTLP in Phase 3 |
| **LLM calls** | Prompt tokens, completion tokens, latency, model, and exceptions | Structured log entry per LLM call (JSON) |
| **Tool calls** | Function name, inputs, output size, latency, success/error | Structured log entry; also in OTel span attributes |
| **Cache** | hit/miss counts, key, TTL | Log and metrics (Prometheus later) |
| **Run outcome** | HTTP status, total duration, final error code, confidence flags | Structured log at response time; audit DB record |
| **Audit** | Immutable record per request: `run_id`, `user_id`, `question`, `sql`, `result_row_count`, `latency_ms`, `confidence_flags`, `timestamp` | Append-only table in MsSQL (or separate audit DB) |

## Concurrency Model

- **Run isolation:** Each HTTP request spawns a fresh LangGraph execution with its own state dict. No shared mutable state between requests. CSV file handles are per-request.
- **Parallel nodes within a run:** None in Phase 1; the graph is linear with error branches. In later phases, nodes like `get_db_metadata` and `load_csv` could technically run in parallel, but gains are minimal. If added, they would be preceded by a `Parallel` node in LangGraph.
- **Checkpointing:** Not needed (single-turn). LangGraph's checkpointing can be disabled.

## Graph Assembly (`src/graph.py`)

```python
from langgraph.graph import StateGraph, END
from .nodes import (
    node_load_csv,
    node_get_db_metadata,
    node_infer_schema,
    node_generate_sql,
    node_validate_query,
    node_check_cache,
    node_execute_query,
    node_generate_chart,
    node_finalize_response,
    node_handle_error,
)

def build_graph() -> CompiledStateGraph:
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("load_csv", node_load_csv)
    graph.add_node("get_db_metadata", node_get_db_metadata)
    graph.add_node("infer_schema", node_infer_schema)
    graph.add_node("generate_sql", node_generate_sql)
    graph.add_node("validate_query", node_validate_query)
    graph.add_node("check_cache", node_check_cache)
    graph.add_node("execute_query", node_execute_query)
    graph.add_node("generate_chart", node_generate_chart)
    graph.add_node("finalize_response", node_finalize_response)
    graph.add_node("handle_error", node_handle_error)

    # Entry point
    graph.set_entry_point("load_csv")

    # Linear flow with error checks
    graph.add_conditional_edges(
        "load_csv",
        lambda s: "handle_error" if s.get("error") else "get_db_metadata",
    )
    graph.add_conditional_edges(
        "get_db_metadata",
        lambda s: "handle_error" if s.get("error") else "infer_schema",
    )
    graph.add_edge("infer_schema", "generate_sql")
    graph.add_conditional_edges(
        "generate_sql",
        lambda s: "handle_error" if s.get("error") else "validate_query",
    )
    graph.add_edge("validate_query", "check_cache")
    graph.add_conditional_edges(
        "check_cache",
        lambda s: "finalize_response" if s.get("cache_hit") else "execute_query",
    )
    graph.add_conditional_edges(
        "execute_query",
        lambda s: "handle_error" if s.get("error") else "generate_chart",
    )
    graph.add_conditional_edges(
        "generate_chart",
        lambda s: "handle_error" if s.get("error") else "finalize_response",
    )
    graph.add_edge("finalize_response", END)
    graph.add_edge("handle_error", END)

    return graph.compile()
```

The compiled graph is a singleton created at app startup and reused for all requests. State is freshly created per request by the API endpoint.
