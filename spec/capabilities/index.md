# Capabilities Index

This agent is composed of the following discrete capabilities:

1. [CSV Upload](csv_upload.md) – Accept and validate multiple CSV files.
2. [MsSQL Connection](mssql_connection.md) – Connect to a large MsSQL database in read‑only mode with connection pooling.
3. [SQL Generation](sql_generation.md) – Translate natural language into safe, parameterized SQL.
4. [Query Validation](query_validation.md) – Ensure generated SQL is read‑only, within row limits, and does not mutate data.
5. [Cache Lookup](query_validation.md#caching) – Reuse prior results to reduce DB load (integrated in validation).
6. [Chart Generation](chart_generation.md) – Convert tabular results into Plotly chart specifications.
7. [Audit Logging](audit_logging.md) – Record every question, action, and outcome for compliance.

All capabilities are orchestrated by a LangGraph state machine (see `agent.md`).
