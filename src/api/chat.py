from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from src.api._common import ok, api_error
from src.db.models import RunRow
from src.db.session import get_session
from src.graph.runner import run_agent
import json

router = APIRouter()

class ChatRequest(BaseModel):
    dataset_id: str
    question: str

@router.post("/chat")
def chat(req: ChatRequest, session: Session = Depends(get_session)) -> dict:
    try:
        run_id = run_agent(dataset_id=req.dataset_id, question=req.question)
    except Exception as e:
        return api_error("agent_failed", str(e), 500)
    run = session.get(RunRow, run_id)
    if run is None:
        return api_error("run_not_found", f"Run {run_id} not found", 404)
    if run.status == "failed":
        return ok({
            "run_id": run_id,
            "status": "failed",
            "error_message": run.error_message,
        })
    try:
        result = json.loads(run.output_text) if run.output_text else {}
    except json.JSONDecodeError:
        result = {"raw_output": run.output_text}
    return ok({
        "run_id": run_id,
        "status": run.status,
        **result,
        "provider": run.provider,
        "model": run.model,
    })
