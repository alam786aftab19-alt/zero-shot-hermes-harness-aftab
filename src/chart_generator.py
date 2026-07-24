"""Chart generation utilities."""
from __future__ import annotations

import json

from src.llm.client import LLMClient, load_prompt
from typing import List, Dict, Any


def generate_chart(question: str, result_data: List[Dict[str, Any]], reasoning: str = None) -> Dict[str, Any]:
    """
    Generate a Plotly chart configuration given the result data and question.
    Returns a Plotly figure dict (with 'data' and 'layout').
    """
    client = LLMClient()
    system = load_prompt("create_chart")
    result_str = json.dumps(result_data, indent=2)
    user = f"Result data:\n{result_str}\n\nUser question: {question}"
    if reasoning:
        user += f"\nReasoning: {reasoning}"
    response = client.complete(system, user, max_tokens=2048)
    # Strip code fences if present
    json_str = response.strip()
    if json_str.startswith("```json"):
        json_str = json_str[7:]
    if json_str.endswith("```"):
        json_str = json_str[:-3]
    json_str = json_str.strip()
    config = json.loads(json_str)
    return config
