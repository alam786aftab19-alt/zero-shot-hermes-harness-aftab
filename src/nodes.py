"""Graph node implementations for the agent."""
from __future__ import annotations

import json
import structlog
from typing import Any, Dict

import pandas as pd
from pandasql import sqldf

from src.chart_generator import generate_chart_config
from src.llm.client import LLMClient, load_prompt

log = structlog.get_logger()


def prepare_schema(state: Dict[str, Any]) -> Dict[str, Any]:
    """Create a textual description of the available DataFrames."""
    log.info("node.start", node="prepare_schema", run_id=state.get("run_id"))
    dataframes: Dict[str, pd.DataFrame] = state.get("dataframes", {})
    schema_lines = []
    for name, df in dataframes.items():
        cols = ", ".join(df.columns)
        schema_lines.append(f"Table `{name}`: columns -> {cols}")
    schema = "\n".join(schema_lines)
    log.info("node.done", node="prepare_schema", run_id=state.get("run_id"), schema=schema)
    return {"schema": schema}


def generate_sql(state: Dict[str, Any]) -> Dict[str, Any]:
    """Use LLM to generate SQL and reasoning based on schema and question."""
    log.info("node.start", node="generate_sql", run_id=state.get("run_id"))
    question = state.get("question", "")
    schema = state.get("schema", "")
    client = LLMClient()
    system = load_prompt("generate_sql")
    user = f"Database schema:\n{schema}\n\nQuestion: {question}"
    try:
        response = client.complete(system, user, max_tokens=2048)
        parsed = json.loads(response)
        reasoning = parsed.get("reasoning", "")
        sql = parsed.get("sql", "")
    except Exception as e:
        log.error("node.error", node="generate_sql", run_id=state.get("run_id"), error=str(e))
        return {"error": f"Failed to generate SQL: {e}"}
    log.info("node.done", node="generate_sql", run_id=state.get("run_id"), sql=sql)
    return {"reasoning": reasoning, "sql_query": sql}


def execute_query(state: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the generated SQL against the DataFrames using pandasql."""
    log.info("node.start", node="execute_query", run_id=state.get("run_id"))
    sql = state.get("sql_query", "")
    dataframes: Dict[str, pd.DataFrame] = state.get("dataframes", {})
    if not sql:
        log.warning("node.skip", node="execute_query", run_id=state.get("run_id"), reason="no_sql")
        return {"error": "No SQL query to execute"}
    try:
        # pandasql expects a dict of DataFrames as the local environment
        result_df: pd.DataFrame = sqldf(sql, {**dataframes})
        # Convert to list of dicts for JSON serialization
        result = result_df.to_dict(orient="records")
        log.info("node.done", node="execute_query", run_id=state.get("run_id"), rows=len(result))
        return {"query_result": result}
    except Exception as e:
        log.error("node.error", node="execute_query", run_id=state.get("run_id"), error=str(e), exc_info=True)
        return {"error": f"Query execution failed: {e}"}


def generate_chart(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Plotly chart configuration based on the query result and question."""
    log.info("node.start", node="generate_chart", run_id=state.get("run_id"))
    question = state.get("question", "")
    result = state.get("query_result", [])
    schema = state.get("schema", "")
    try:
        chart_config = generate_chart_config(question, result, schema)
        log.info("node.done", node="generate_chart", run_id=state.get("run_id"), chart_type=chart_config.get("data", [{}])[0].get("type"))
        return {"chart_config": chart_config}
    except Exception as e:
        log.error("node.error", node="generate_chart", run_id=state.get("run_id"), error=str(e))
        return {"error": f"Failed to generate chart: {e}"}


def finalize(state: Dict[str, Any]) -> Dict[str, Any]:
    """Finalize the state with a completed status."""
    log.info("node.finalize", run_id=state.get("run_id"))
    return {"status": "completed"}


def handle_error(state: Dict[str, Any]) -> Dict[str, Any]:
    """Handle errors by marking the status as failed."""
    log.error("node.error", node="handle_error", run_id=state.get("run_id"), error=state.get("error"))
    return {"status": "failed"}
