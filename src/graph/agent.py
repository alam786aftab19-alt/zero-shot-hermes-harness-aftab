"""Graph assembly — StateGraph compiled once at import."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.graph.edges import make_router
from src.graph.nodes import (
    load_csv,
    parse_question,
    plan_query,
    generate_sql,
    execute_query,
    create_chart,
    handle_error,
    finalize,
)
from src.graph.state import AgentState


def _build_graph():
    g = StateGraph(AgentState)
    g.add_node("load_csv", load_csv)
    g.add_node("parse_question", parse_question)
    g.add_node("plan_query", plan_query)
    g.add_node("generate_sql", generate_sql)
    g.add_node("execute_query", execute_query)
    g.add_node("create_chart", create_chart)
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)

    g.set_entry_point("load_csv")

    nodes = ["load_csv", "parse_question", "plan_query", "generate_sql", "execute_query", "create_chart"]
    for i, node in enumerate(nodes):
        next_node = nodes[i+1] if i+1 < len(nodes) else "finalize"
        g.add_conditional_edges(
            node,
            make_router(next_node),
            {next_node: next_node, "handle_error": "handle_error"}
        )

    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()


agentic_ai = _build_graph()
