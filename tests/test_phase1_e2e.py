"""E2E test for Phase 1: CSV upload + chat → sql, reasoning, chart_config."""
import os

import pytest
from fastapi.testclient import TestClient

from src.main import app

# Skip if no LLM provider key is present
def has_llm_key():
    try:
        from src.config.settings import Settings
        s = Settings()
        return bool(s.openai_api_key or s.anthropic_api_key or s.google_api_key)
    except Exception:
        return False

pytestmark = pytest.mark.skipif(
    not has_llm_key(),
    reason="No LLM API keys found in .env; set OPENAI_API_KEY or ANTHROPIC_API_KEY"
)

CSV_CONTENT = """district,incidents
North,10
South,15
East,5
West,20
"""

def test_phase1_e2e():
    client = TestClient(app)
    # Upload CSV
    files = [("files", ("crime.csv", CSV_CONTENT, "text/csv"))]
    response = client.post("/upload", files=files)
    assert response.status_code == 200, f"Upload failed: {response.text}"
    session_id = response.json()["session_id"]
    assert session_id

    # Ask question
    question = "Show me total incidents by district as a bar chart"
    chat_response = client.post("/chat", json={"session_id": session_id, "question": question})
    assert chat_response.status_code == 200, f"Chat failed: {chat_response.text}"
    data = chat_response.json()

    # Basic assertions
    assert "sql" in data and data["sql"], "SQL should be non-empty"
    assert "reasoning" in data and data["reasoning"], "Reasoning should be non-empty"
    assert "chart_config" in data and data["chart_config"], "Chart config should be non-empty"
    # Ensure it's a dict with expected structure
    chart_cfg = data["chart_config"]
    assert isinstance(chart_cfg, dict)
    assert "data" in chart_cfg and isinstance(chart_cfg["data"], list)
    assert "layout" in chart_cfg

    # Ensure status is completed if no error
    status = data.get("status")
    assert status == "completed", f"Expected completed, got {status} with error: {data.get('error')}"
