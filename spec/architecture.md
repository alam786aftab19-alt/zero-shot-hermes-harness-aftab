# Architecture

## System Overview

The UP Police Data Analyst is a web-based AI agent that accepts natural language questions about crime data, generates and executes SQL queries (against uploaded CSV files and/or an on-premises MsSQL database), and returns visual charts with full transparency. It runs as a single FastAPI service with a static frontend served at `/app`. The agent uses LangGraph to orchestrate a deterministic multi-step reasoning pipeline: understand the question, infer schema from CSVs and DB metadata, generate a safe SQL query, execute it, and produce a chart. All data remains on-premises; no external API calls. The system is designed for single-turn interactions (< 60 seconds) with caching and query validation to protect the production database from load.

## Component Map

```
[User Browser]
    ↓ (HTTP)
[FastAPI Backend]
    ├─ LangGraph Agent
    │   ├─ Parse Question Node
    │   ├─ Schema Inference Node (CSV + DB metadata)
    │   ├─ SQL Generation Node
    │   ├─ Query Validator Node
    │   ├─ Query Executor Node (with Cache)
    │   └─ Chart Generator Node
    ├─ CSV Loader (in-memory DataFrames)
    ├─ Query Cache (Redis/SQLite/InMemory)
    ├─ MsSQL Connector (SQLAlchemy + pyodbc)
    └─ Audit Logger
    ↓ (HTML/JSON/Chart data)
[Static Frontend served at /app]
    ├─ index.html
    ├─ styles.css
    └─ app.js (fetch API, Chart.js)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| **API Layer** | FastAPI routes: `/chat` (POST), `/upload` (POST), `/health`; serves static frontend at `/app/` |
| **Agent Graph Layer** | LangGraph state machine; defines nodes, edges, and control flow; manages agent state per request |
| **Node Layer** | Individual processing steps: parse, plan, generate SQL, validate, execute, visualize |
| **Tool Layer** | Reusable utilities: CSV loader, SQL generator, chart renderer, cache client, DB connector, audit logger |
| **Storage Layer** | MsSQL via SQLAlchemy+pyodbc (read-only); CSV files stored temporarily in memory; cache store (configurable); audit logs |
| **Observability Layer** | Structured JSON logging, OpenTelemetry traces, metrics for latency/cache hits |

## Data Flow

1. **Trigger:** User opens `/app/`, uploads CSV files (optional), types a question, and submits.
2. **Upload handling:** Server receives CSV files; `CSVLoader` parses them into pandas DataFrames; stores in request-scoped memory with inferred schemas.
3. **Agent start:** LangGraph initializes state with question and available data sources (CSV schemas + MsSQL metadata if connected).
4. **Parse question:** LLM (local/on-prem) parses natural language into structured intent (what to retrieve, possible groupings/filters).
5. **Schema fusion:** Combine CSV schemas (from DataFrames) and MsSQL table metadata (from DB introspection) into a unified virtual schema description.
6. **SQL generation:** LLM produces a syntactically correct SQL query targeting the appropriate data source(s) (CSV or DB or join via external merge). The query includes reasoning annotations.
7. **Query validation:** `QueryValidator` checks: read-only, no destructive ops, estimated cost within limit, row limit enforced. If validation fails, agent flags uncertainty and returns best-effort alternative or safe fallback.
8. **Cache check:** Normalized query hash checked against cache. On hit, skip execution and use cached result.
9. **Query execution:** If cache miss, execute via `QueryExecutor` against the chosen backend (CSV via pandas, MsSQL via SQLAlchemy). Apply timeout (e.g., 30s). On timeout/failure, return partial/empty result with flag.
10. **Chart generation:** `ChartGenerator` selects appropriate chart type (bar, line, pie, scatter) based on query result shape and user question; creates Chart.js config or Plotly JSON.
11. **Response assembly:** Final state includes: answer text, SQL query, reasoning steps, chart data, cache hit/miss, confidence flags.
12. **Audit log:** Entire interaction (question, SQL, result summary, timestamps) written to audit store.
13. **Output:** FastAPI returns JSON with all artifacts; frontend renders SQL (syntax highlighted), reasoning (markdown), and chart.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| **MsSQL Server** | Primary production data source | If down, agent falls back to CSV-only mode with explicit "DB unavailable" flag in answer |
| **LLM (local/on-prem)** | Generates SQL and reasoning from natural language | If LLM unavailable, fallback to rule-based template matching (canned responses) with "limited capability" flag; returns generic guidance |
| **Cache (optional Redis/SQLite)** | Reduces DB load for repeated queries | If cache fails, continue without caching (log warning); performance degrades but system remains functional |
| **Static file serving** | Frontend delivery | Served by same FastAPI process; no external dependency |

## Stack

This project's concrete technology choices:

- **Language:** Python 3.11+
- **Agent framework:** LangGraph (state graph with nodes and conditional edges)
- **LLM provider + model:** Configurable; recommended on-prem or local LLM (e.g., Ollama-based Llama 3.1, or Step models via StepFun). Model name set via `LLM_MODEL` env var. Must support function/structured calling for tool use.
- **Backend:** FastAPI (async-capable, but agent graph is sync; use `run_in_threadpool` for heavy DB/CSV ops)
- **Database + ORM:** MsSQL via SQLAlchemy 2.0 (async not required) with pyodbc driver
- **Frontend:** Zero-build static (HTML + CSS + JavaScript); Chart.js for visualizations
- **Dependency management:** uv + pyproject.toml
- **Cache:** Configurable backend: Redis (production), SQLite (simple), or in-memory dict (dev). Controlled by `CACHE_BACKEND` env var.
- **Observability:** Structured logging (JSON) to stdout; OpenTelemetry via `opentelemetry-api`/`sdk`; traces exported to console or OTLP endpoint.

### Key libraries

| Library | Version | Purpose |
|---------|---------|---------|
| fastapi | ^0.110.0 | Web API and static file serving |
| uvicorn[standard] | ^0.29.0 | ASGI server |
| langgraph | ^0.2.0 | Agent graph orchestration |
| langchain-core | ^0.2.0 | LLM abstractions and tool utilities |
| sqlalchemy | ^2.0.0 | Database ORM and query building |
| pyodbc | ^5.0.0 | MsSQL DB-API driver |
| pandas | ^2.2.0 | CSV loading and in-memory querying |
| openai | ^1.15.0 | LLM client (works with any OpenAI-compatible API) |
| opentelemetry-api | ^1.24.0 | Observability traces |
| opentelemetry-sdk | ^1.24.0 | Trace recording |
| redis | ^5.0.0 | Optional cache backend |
| pydantic | ^2.7.0 | Settings and data validation |
| python-dotenv | ^1.0.0 | Config from `.env` |
| chart.js | (frontend) | Client-side chart rendering |

**Avoid:** Any cloud-only services (e.g., OpenAI API if data sovereignty required), heavyweight async frameworks beyond FastAPI's built-in, or external ETL pipelines. Do not use client-side frameworks (React/Vue) unless spec explicitly requires; stick to zero-build static for simplicity and reliability.

## Deployment Model

The application runs as a long-lived service on an on-premises server within the police network. Deployment is a single command:

```bash
uv run python -m src
```

The service binds to `0.0.0.0:8001` (configurable via `PORT`). It serves the frontend at `/app/` and the API at `/chat` and `/upload`. All configuration (DB connection string, LLM endpoint, cache settings) comes from environment variables or a `.env` file placed in the project root (gitignored). The service logs structured JSON to stdout; logs are collected by the system journal or a central log aggregator. No containers or orchestration are required in Phase 1, though Docker can be used for consistency in later phases.
