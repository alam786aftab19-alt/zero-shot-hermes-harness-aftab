"""AgentState — the TypedDict flowing through the graph."""
from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    dataset_id: str
    question: str
    dataframes: dict  # table name -> pandas DataFrame
    schemas: str  # formatted schema description
    reasoning: str
    plan: str
    sql_query: str
    query_result: list[dict]  # result rows as dictionaries
    chart_config: dict
    provider: str
    model: str
    status: str
    error: str | None
    output_text: str  # final JSON output for persistence
