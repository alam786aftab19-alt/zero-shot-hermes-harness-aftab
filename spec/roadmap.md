# Roadmap

## What This Agent Does

The UP Police Data Analyst agent is a single-turn, low-latency AI assistant that enables police personnel to analyze crime data by asking natural language questions. It accepts multiple CSV file uploads and connects to a large on-premises Microsoft SQL Server database. The agent generates appropriate SQL queries (with reasoning), executes them, and produces visual charts to answer user questions—all within 60 seconds. It operates entirely on-premises to ensure data security, minimizes database load through intelligent caching and query optimization, and always shows its work (SQL queries, reasoning) while providing best-guess answers with uncertainty flags when data is incomplete. The agent never asks clarifying questions, making it suitable for quick, frictionless analysis.

## Who Uses It

- **Primary users:** Police officers, analysts, and investigators in the Uttar Pradesh Police department.
- **Use case:** Rapid exploratory data analysis of crime statistics, incident reports, and related datasets. Users need to quickly derive insights without writing SQL or using complex BI tools.
- **Context:** On-premise environment with existing large MsSQL databases containing years of crime data, plus ad-hoc CSV uploads for supplemental or temporary datasets.

## Core Problem Being Solved

Manual data analysis in police workflows is slow and requires SQL expertise or reliance on pre-built dashboards that can't answer ad-hoc questions. Analysts spend hours writing and tuning queries, and resource constraints limit direct DB access to prevent overload. This agent bridges the gap: it gives non-technical personnel the power to ask natural language questions and get immediate, charted answers while protecting the production database from inefficient queries through caching, query validation, and rate limiting.

## Success Criteria

- [ ] Users receive charted answers to natural language questions within 60 seconds (p95 latency)
- [ ] System never crashes the database: query load reduced via caching and validation
- [ ] All data stays on-premises; no external API calls (LLM can be local or on-prem)
- [ ] Every answer includes the SQL query and reasoning steps (full transparency)
- [ ] Uncertain answers are flagged with confidence indicators
- [ ] Zero clarifying questions asked; agent provides best-effort answers immediately
- [ ] Audit trail logs all queries, user inputs, and results for compliance

## What This Agent Does NOT Do (Out of Scope)

- Learn from previous interactions (no memory/session state beyond single turn)
- Write to or modify the database (read-only access only)
- Support multi-turn conversations or follow-up questions
- Provide definitive legal advice or predictions (only data analysis)
- Handle real-time streaming data or live feeds
- Replace official reports or sanctioned BI dashboards
- Perform complex statistical modeling or machine learning inference
- Access external internet/cloud services (fully on-prem)

## Key Constraints

- **Latency:** < 60 seconds end-to-end for 95% of queries
- **Database load:** Must not degrade production DB performance; aggressive caching and query optimization
- **Data sovereignty:** All processing on-prem; no data exfiltration
- **Accuracy:** Must flag uncertain answers; never pretend certainty when schema mismatch or insufficient data
- **Single-turn:** No follow-up clarification questions; provide best guess immediately
- **Audit:** All user inputs, generated SQL, and results must be logged for compliance

## Phases of Development

**Phase 1 is the smallest first-time-right user-testable win.** It must work perfectly the first time the user tests it — zero rough edges on the tested path. Its backend is minimal but REAL on the one core path (no fake data on the tested path). Its frontend is visually complete: real UI for the one working path PLUS clearly-labelled NON-FUNCTIONAL stubs for everything coming later. Each later phase wires those stubs into real functionality, one increment at a time.

### Phase 1 — CSV Upload + Query + Chart MVP

- **Goal:** Smallest working end-to-end: user uploads one or more CSV files, asks a question, agent analyzes the CSVs (in-memory), generates SQL-like queries against them, and returns a chart. This proves the agent loop, UI, and chart generation without touching the MsSQL DB.
- **Independent slices (parallel build units):**
  - `backend-api` (backend) — FastAPI endpoints for CSV upload and chat completion; Phase 1 only handles CSV data; deps: none
  - `agent-graph` (backend) — LangGraph agent with nodes: parse_question, plan_query, generate_sql, execute_query (on CSV), create_chart; deps: none
  - `frontend-ui` (frontend) — Single-page app at `/app/` with file upload control, chat input, and chart display; support multiple CSV upload and chat; deps: none
- **Key surfaces / files:**
  - Backend: `src/main.py`, `src/graph.py`, `src/nodes.py`, `src/csv_loader.py`, `src/chart_generator.py`
  - Frontend: `frontend/public/index.html`, `frontend/public/styles.css`, `frontend/public/app.js`
  - Tests: `tests/test_phase1_e2e.py`, `tests/test_agent.py`
- **Gate command:** `uv run pytest tests/test_phase1_e2e.py -m phase1`
- **How the user tests it (handoff seed):**
  1. Start: `uv run python -m src` (server on port 8001)
  2. Open: `http://localhost:8001/app/`
  3. Upload 1-2 sample CSV files (e.g., crime_data.csv)
  4. Ask: "Show me total incidents by district as a bar chart"
  5. Expected: Within 30 seconds, see the generated SQL query, reasoning steps, and a bar chart rendering
  6. Note: MsSQL connection is a stub (marked "Coming soon"); CSV-only path is real

### Phase 2 — MsSQL Integration with Caching and Load Reduction

- **Goal:** Wire the MsSQL connection with query caching, validation, and load reduction features. The agent now connects to the production database (alongside CSVs) and intelligently caches results to minimize DB load while maintaining <1 min latency.
- **Independent slices (parallel build units):**
  - `mssql-connector` (backend) — SQLAlchemy + pyodbc driver; connection pooling; query timeout; read-only credentials; deps: none
  - `query-cache` (backend) — Redis or in-memory cache layer (configurable) with TTL; cache key by normalized query; metrics; deps: none
  - `query-validator` (backend) — Pre-execution validation: estimated cost, row count limits, forbidden operations; safe query patterns; deps: none
  - `cache-ui` (frontend) — Show cache hits/misses; optionally display cached query indicator; deps: frontend-ui
- **Key surfaces / files:**
  - Backend: `src/db/mssql.py`, `src/cache/engine.py`, `src/cache/validator.py`, `src/config.py`
  - Config: `.env` additions (MSSQL_CONNECTION_STRING, CACHE_TTL, CACHE_ENABLED, MAX_QUCOST_MS)
  - Tests: `tests/test_mssql_connection.py`, `tests/test_cache.py`, `tests/test_validator.py`, `tests/test_phase2_e2e.py`
- **Gate command:** `uv run pytest tests/test_phase2_e2e.py -m phase2`
- **How the user tests it (handoff seed):**
  1. Start: `uv run python -m src` (ensure `.env` has MSSQL_CONNECTION_STRING pointing to test DB)
  2. Open: `http://localhost:8001/app/`
  3. Upload a CSV (optional) or ask directly: "How many crimes were reported last month in Prayagraj?"
  4. Expected: See the SQL generated, reasoning steps, and either a cached result indicator (if same query repeated) or a fresh DB query result with chart. Total time < 60 seconds.
  5. Verify: Invalid or expensive queries are blocked with a friendly error message, not a DB crash.

### Phase 3 — Observability, Audit Logging, and Polish

- **Goal:** Add structured logging, OpenTelemetry traces, audit logs, and production hardening. Ensure all system behavior is observable and compliant. Polish UI/UX and error messages.
- **Independent slices (parallel build units):**
  - `observability` (backend) — OpenTelemetry integration; span per node; structured JSON logs; deps: none
  - `audit-logger` (backend) — Log every user input, generated SQL, execution plan, result summary, and confidence flags to audit table/file; deps: none
  - `error-handling` (backend) — Graceful fallbacks when DB is slow/offline; best-effort answers with uncertainty flags; deps: none
  - `ui-polish` (frontend) — Loading states, error displays, query preview, copy-to-clipboard for SQL; deps: frontend-ui, cache-ui
- **Key surfaces / files:**
  - Backend: `src/telemetry.py`, `src/audit.py`, `src/error_handling.py`
  - Frontend: updates to `app.js` for loading spinners, error banners, SQL code blocks
  - Tests: `tests/test_observability.py`, `tests/test_audit.py`
- **Gate command:** `uv run pytest -m phase3`
- **How the user tests it (handoff seed):**
  1. Start server and open UI
  2. Ask questions that trigger various scenarios (cache hit, cache miss, validation error, DB timeout)
  3. Expected: All actions produce structured logs readable in console; audit trail recorded; UI shows clear loading/error states; answers include uncertainty flags when appropriate

### Phase 4 — Performance Tuning and Scaling

- **Goal:** Optimize for high concurrency and large datasets. Tune cache strategies, connection pool sizing, query parallelism, and ensure consistent sub-60-second performance under load.
- **Independent slices (parallel build units):**
  - `performance-tuning` (backend) — Benchmark and tune: cache TTL optimization, connection pool max size, query plan caching, async execution where beneficial; deps: none
  - `load-testing` (backend) — Simulate concurrent users; measure p95 latency; identify bottlenecks; deps: none
  - `scaling-config` (backend) — Configuration profiles for dev/staging/prod; resource limits; deps: none
- **Key surfaces / files:**
  - Config: `src/config.py` extended; `pyproject.toml` tool configurations
  - Tests: `tests/benchmarks/`, `tests/load/`
- **Gate command:** `uv run pytest -m phase4 && tests/load/run_smoke.sh`
- **How the user tests it (handoff seed):**
  1. Run load test script; observe p95 latency remains < 60 seconds under 10 concurrent users
  2. Run benchmark suite; no single query exceeds 30 seconds on production-sized dataset
  3. Verify cache hit rates > 70% for repeated similar queries

---

## Future Enhancements (Out of Current Scope)

- Multi-turn conversation memory
- Export to PDF/Excel
- Advanced visualizations (heatmaps, geographic maps)
- Natural language to dashboard generation
- Integration with external data sources (APIs, other DBs)
- Role-based access control (RBAC) and row-level security
- Query suggestion and autocomplete
- Scheduled report generation
