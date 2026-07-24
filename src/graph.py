"""LangGraph definition and execution for the agent."""
from __future__ import annotations

from typing import Dict, Any

from langgraph.graph import StateGraph, END

from src.nodes import (
    prepare_schema,
    generate_sql,
    execute_query,
    generate_chart,
    finalize,
    handle_error,
)


class AgentState(dict):
    """
    TypedDict-like state class for the graph.
    Fields (all optional):
      - run_id: str
      - session_id: str
      - question: str
      - dataframes: dict[str, pd.DataFrame]
      - schema: str
      - sql_query: str
      - reasoning: str
      - query_result: list[dict]
      - chart_config: dict
      - error: str | None
      - status: str
    This class is a subclass of dict for convenience; LangGraph treats it as a mutable mapping.
    """


def _route_if_error(state: AgentState) -> str:
    """Route to error handling if state contains an error."""
    if state.get("error"):
        return "handle_error"
    # Otherwise, the calling code will decide the specific next node.
    # This function is used as a generic conditional; we will provide specific mapping.
    return "next"


# Build the graph
graph = StateGraph(AgentState)

graph.add_node("prepare_schema", prepare_schema)
graph.add_node("generate_sql", generate_sql)
graph.add_node("execute_query", execute_query)
graph.add_node("generate_chart", generate_chart)
graph.add_node("finalize", finalize)
graph.add_node("handle_error", handle_error)

graph.set_entry_point("prepare_schema")


# Conditional edges after each node
def after_schema(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "generate_sql"


def after_sql(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "execute_query"


def after_execute(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "generate_chart"


def after_chart(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "finalize"


graph.add_conditional_edges("prepare_schema", after_schema, {
    "generate_sql": "generate_sql",
    "handle_error": "handle_error"
})
graph.add_conditional_edges("generate_sql", after_sql, {
    "execute_query": "execute_query",
    "handle_error": "handle_error"
})
graph.add_conditional_edges("execute_query", after_execute, {
    "generate_chart": "generate_chart",
    "handle_error": "handle_error"
})
graph.add_conditional_edges("generate_chart", after_chart, {
    "finalize": "finalize",
    "handle_error": "handle_error"
})

graph.add_edge("handle_error", END)
graph.add_edge("finalize", END)

# Compile the graph
compiled_graph = graph.compile()


def run_agent(initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the agent with the given initial state.

    Args:
        initial_state: A dictionary containing at least 'question' and 'dataframes'.
                       May also include 'session_id', etc.

    Returns:
        The final state dictionary after the graph completes.
    """
    # Ensure run_id is present
    if "run_id" not in initial_state:
        import uuid
        initial_state["run_id"] = uuid.uuid4().hex
    # Invoke the graph synchronously
    return compiled_graph.invoke(initial_state)
