from fastapi import APIRouter, File, UploadFile
from pathlib import Path
import uuid
from src.api._common import ok
from src.csv_loader import UPLOAD_DIR

router = APIRouter()

@router.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)) -> dict:
    dataset_id = uuid.uuid4().hex
    dataset_dir = UPLOAD_DIR / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    saved_filenames = []
    for file in files:
        if not file.filename:
            continue
        safe_name = Path(file.filename).name
        dest = dataset_dir / safe_name
        content = await file.read()
        with dest.open("wb") as f:
            f.write(content)
        saved_filenames.append(safe_name)
    return ok({"dataset_id": dataset_id, "files": saved_filenames})
