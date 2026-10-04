"""B's HTTP route. C mounts it in the app:

    from app.scoring.router import router
    app.include_router(router)

Inside the backend (scan on delivery) call app.scoring.analyze.analyze(message)
directly instead of going through HTTP.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.detection.ingest import parse_eml
from app.detection.router import MAX_UPLOAD_BYTES
from app.schemas import Message
from app.schemas import Assessment
from app.scoring.analyze import analyze

router = APIRouter()


@router.post("/api/analyze", response_model=Assessment)
async def analyze_upload(file: UploadFile = File(...)) -> Assessment:
    """An uploaded .eml ("Is this safe?"): A's signals + ML + fusion + explanation."""
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="This file is too large for an email (the limit is 10 MB).")
    try:
        message = parse_eml(raw)
    except ValueError as exc:  # parse_eml raises this for files that are not email
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return analyze(message)


@router.post("/api/analyze/message", response_model=Assessment)
def analyze_message(message: Message) -> Assessment:
    """An already parsed Message as JSON (for the UI's paste box or other services)."""
    return analyze(message)
