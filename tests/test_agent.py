"""Unit tests for the agent's nodes and utilities."""
import io
import json
from unittest.mock import MagicMock

import pandas as pd
import pytest
from pydantic import BaseModel

from src.csv_loader import load_csv, load_multiple_csvs
from src.nodes import (
    prepare_schema,
    generate_sql,
    execute_query,
    generate_chart,
)
from src.llm.client import LLMClient


# Mock LLMClient for tests that need deterministic responses
class MockLLMClient(LLMClient):
    def __init__(self, response: str):
        self._response = response
        self.provider_name = "mock"
        self.model = "mock-model"

    def complete(self, system, user, max_tokens=None):
        return self._response


@pytest.fixture
def mock_llm(monkeypatch):
    """Fixture to replace LLMClient with a mock returning a fixed response."""
    def _mock(response: str):
        monkeypatch.setattr("src.nodes.LLMClient", lambda: MockLLMClient(response))
    return _mock


def test_load_csv():
    csv_content = "col1,col2\n1,a\n2,b\n3,c"
    file_obj = io.StringIO(csv_content)
    table_name, df = load_csv(file_obj, "test.csv")
    assert table_name == "test"
    assert list(df.columns) == ["col1", "col2"]
    assert len(df) == 3
    assert df["col1"].tolist() == [1, 2, 3]


def test_load_multiple_csvs():
    files = [
        ("first.csv", io.StringIO("a,b\n1,2\n3,4")),
        ("second.csv", io.StringIO("c,d\n5,6\n7,8")),
    ]
    tables = load_multiple_csvs(files)
    assert set(tables.keys()) == {"first", "second"}
    assert tables["first"].shape == (2, 2)
    assert tables["second"]["c"].tolist() == [5, 7]


def test_prepare_schema():
    df1 = pd.DataFrame({"x": [1], "y": [2]})
    df2 = pd.DataFrame({"name": ["Alice"], "age": [30]})
    state = {"dataframes": {"table1": df1, "table2": df2}}
    new_state = prepare_schema(state)
    schema = new_state["schema"]
    assert "table1" in schema
    assert "x" in schema and "y" in schema
    assert "table2" in schema
    assert "name" in schema and "age" in schema


def test_generate_sql(mock_llm):
    mock_response = json.dumps({
        "reasoning": "We need total per category.",
        "sql": "SELECT category, COUNT(*) as cnt FROM data GROUP BY category"
    })
    mock_llm(mock_response)
    state = {
        "question": "Count records by category",
        "schema": "data: columns -> category, value"
    }
    new_state = generate_sql(state)
    assert new_state.get("sql_query") == "SELECT category, COUNT(*) as cnt FROM data GROUP BY category"
    assert new_state.get("reasoning") == "We need total per category."
    assert "error" not in new_state


def test_generate_sql_parse_error(mock_llm):
    mock_llm("Not JSON")
    state = {"question": "anything", "schema": "t: col"}
    new_state = generate_sql(state)
    assert "error" in new_state
    assert "Failed to generate SQL" in new_state["error"]


def test_execute_query():
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    state = {
        "dataframes": {"t": df},
        "sql_query": "SELECT a FROM t WHERE a > 1",
    }
    new_state = execute_query(state)
    assert "error" not in new_state
    result = new_state["query_result"]
    assert len(result) == 2
    assert result[0]["a"] == 2
    assert result[1]["a"] == 3


def test_execute_query_invalid_sql():
    state = {
        "dataframes": {"t": pd.DataFrame({})},
        "sql_query": "INVALID SQL STATEMENT",
    }
    new_state = execute_query(state)
    assert "error" in new_state
    assert "failed" in new_state["error"].lower()


def test_generate_chart(mock_llm):
    chart_cfg = {
        "data": [{"type": "bar", "x": ["A", "B"], "y": [1, 2]}],
        "layout": {"title": "Test Chart"},
    }
    mock_llm(json.dumps(chart_cfg))
    state = {
        "question": "Show a bar chart",
        "query_result": [{"x": "A", "y": 1}, {"x": "B", "y": 2}],
        "schema": "t: x, y",
    }
    new_state = generate_chart(state)
    assert "error" not in new_state
    assert new_state["chart_config"] == chart_cfg


def test_generate_chart_invalid_json(mock_llm):
    mock_llm("not json")
    state = {
        "question": "anything",
        "query_result": [],
        "schema": "",
    }
    new_state = generate_chart(state)
    assert "error" in new_state
    assert "Failed to generate chart" in new_state["error"]
