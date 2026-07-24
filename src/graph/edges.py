"""Conditional routing functions."""
from __future__ import annotations

from src.graph.state import AgentState


def make_router(next_node: str):
    """Returns a router function that goes to next_node if no error, else handle_error."""
    def router(state: AgentState) -> str:
        if state.get("error"):
            return "handle_error"
        return next_node
    return router
