"""FastAPI application for the UP Police Data Analyst agent."""
from __future__ import annotations

import io
import os
import uuid
from typing import Dict, List

import pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

from src.graph import run_agent
from src.csv_loader import load_multiple_csvs

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

app = FastAPI(title="UP Police Data Analyst")

# In-memory session store (for Phase 1; not for production)
SESSIONS: Dict[str, Dict] = {}


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


@app.post("/upload")
async def upload_csv(files: List[UploadFile] = File(...)):
    """
    Upload one or more CSV files. Returns a session_id that must be used in subsequent /chat calls.
    """
    session_id = uuid.uuid4().hex
    logger.info("upload.start", session_id=session_id, file_count=len(files))

    dataframes = {}
    for file in files:
        content = await file.read()
        try:
            # Decode bytes if needed
            if isinstance(content, bytes):
                file_obj = io.BytesIO(content)
            else:
                file_obj = io.StringIO(content)
            df = pd.read_csv(file_obj)
        except Exception as e:
            logger.error("upload.parse_error", session_id=session_id, filename=file.filename, error=str(e))
            raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {file.filename}") from e

        table_name = os.path.splitext(file.filename)[0].replace(" ", "_").lower()
        dataframes[table_name] = df
        logger.debug("upload.file_loaded", session_id=session_id, filename=file.filename, rows=len(df), columns=list(df.columns))

    SESSIONS[session_id] = {"dataframes": dataframes}
    logger.info("upload.complete", session_id=session_id)
    return {"session_id": session_id}


class ChatRequest(BaseModel):
    session_id: str
    question: str


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Send a natural language question about the uploaded CSV data.
    Returns sql, reasoning, and chart_config.
    """
    logger.info("chat.start", session_id=request.session_id, question=request.question)
    session = SESSIONS.get(request.session_id)
    if not session:
        logger.warning("chat.session_not_found", session_id=request.session_id)
        raise HTTPException(status_code=404, detail="Session not found; upload CSV first")

    initial_state = {
        "run_id": uuid.uuid4().hex,
        "session_id": request.session_id,
        "question": request.question,
        "dataframes": session["dataframes"],
    }

    try:
        result_state = run_agent(initial_state)
    except Exception as e:
        logger.exception("chat.agent_error", session_id=request.session_id)
        return JSONResponse(
            status_code=200,
            content={
                "status": "failed",
                "error": str(e),
                "sql": None,
                "reasoning": None,
                "chart_config": None,
            },
        )

    response = {
        "status": result_state.get("status", "failed"),
        "sql": result_state.get("sql_query"),
        "reasoning": result_state.get("reasoning"),
        "chart_config": result_state.get("chart_config"),
        "error": result_state.get("error"),
    }
    logger.info("chat.complete", session_id=request.session_id, status=response["status"])
    return response


@app.get("/health")
async def health():
    """Simple health check."""
    return {"status": "ok"}
