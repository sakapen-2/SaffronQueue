import uuid
import logging
from datetime import datetime, timezone
from .ui import router as ui_router
from fastapi.responses import PlainTextResponse

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import text

from .db import Base, engine, SessionLocal
from .models import Job, JobStatus
from .schemas import JobCreate, JobOut
from .settings import settings
from .redis_client import get_redis
from .logging_utils import setup_logging

setup_logging(settings.log_level)
log = logging.getLogger("api")

app = FastAPI(title="SaffronQueue API", version="0.2.0")
app.include_router(ui_router)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.middleware("http")
async def request_id_mw(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.get("/healthz")
def healthz(request: Request):
    log.info("health ok", extra={"request_id": request.state.request_id, "event": "healthz"})
    return {"ok": True}

@app.get("/readyz")
def readyz(request: Request, db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    r = get_redis()
    r.ping()
    log.info("ready ok", extra={"request_id": request.state.request_id, "event": "readyz"})
    return {"ready": True}

@app.post("/jobs", response_model=JobOut, status_code=201)
def create_job(req: JobCreate, request: Request, db: Session = Depends(get_db)):
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        status=JobStatus.queued,
        payload=req.payload,
        max_attempts=req.max_attempts,
        attempts=0,
    )
    db.add(job)
    db.commit()

    r = get_redis()
    r.lpush(settings.job_queue, job_id)  # queue
    log.info(
        "job queued",
        extra={"request_id": request.state.request_id, "job_id": job_id, "event": "job_queued"},
    )

    return JobOut(
        id=job.id,
        status=job.status.value,
        payload=job.payload,
        result=job.result,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        last_error=job.last_error,
    )

@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, request: Request, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    log.info(
        "job fetched",
        extra={"request_id": request.state.request_id, "job_id": job_id, "event": "job_get"},
    )
    return JobOut(
        id=job.id,
        status=job.status.value,
        payload=job.payload,
        result=job.result,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        last_error=job.last_error,
    )
@app.get("/jobs/{job_id}/checksum", response_class=PlainTextResponse)
def download_checksum(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    if job.status != JobStatus.succeeded or not job.result:
        raise HTTPException(status_code=409, detail="job not finished yet")

    body = f"{job.result}  job:{job.id}\n"

    resp = PlainTextResponse(body)
    resp.headers["Content-Disposition"] = f'attachment; filename="{job.id}.sha256"'
    return resp
