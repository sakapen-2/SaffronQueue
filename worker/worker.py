import hashlib
import logging
import random
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db import SessionLocal, Base, engine
from models import Job, JobStatus
from settings import settings
from redis_client import get_redis
from logging_utils import setup_logging

setup_logging(settings.log_level)
log = logging.getLogger("worker")

Base.metadata.create_all(bind=engine)

def utcnow():
    return datetime.now(timezone.utc)

def compute_result(payload: str) -> str:
    """
    کار fake ولی واقعی‌نما:
    - کمی delay تصادفی
    - هش payload به عنوان نتیجه
    - گاهی هم خطا برای تست retry
    """
    time.sleep(random.uniform(0.2, 1.2))
    # 15% احتمال خطای عمدی برای تست retry
    if random.random() < 0.15:
        raise RuntimeError("simulated random failure")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def move_due_delayed(r):
    """
    delayed jobs: ZSET (score=unix_ts)
    هر بار jobs که موعدش رسیده رو از zset بیرون می‌کشه و می‌فرسته تو queue
    """
    now = time.time()
    due = r.zrangebyscore(settings.job_delayed, 0, now, start=0, num=50)
    if not due:
        return 0
    pipe = r.pipeline()
    for job_id in due:
        pipe.zrem(settings.job_delayed, job_id)
        pipe.lpush(settings.job_queue, job_id)
    pipe.execute()
    return len(due)

def reliable_pop(r, timeout=5):
    """
    BRPOPLPUSH:
    از انتهای queue برمی‌داره و می‌ذاره تو processing
    تا اگر worker کرش کرد job گم نشه.
    """
    return r.brpoplpush(settings.job_queue, settings.job_processing, timeout=timeout)

def ack_processing(r, job_id: str):
    # remove ONE occurrence from processing
    r.lrem(settings.job_processing, 1, job_id)

def handle_job(db: Session, r, job_id: str):
    job = db.get(Job, job_id)
    if not job:
        log.warning("job not found in db", extra={"job_id": job_id, "event": "job_missing_db"})
        return

    # اگر قبلاً تمام شده، فقط ack کن (idempotency)
    if job.status in (JobStatus.succeeded, JobStatus.failed):
        log.info("job already finished, ack", extra={"job_id": job_id, "event": "job_already_done"})
        return

    job.status = JobStatus.running
    job.started_at = utcnow()
    db.commit()

    try:
        result = compute_result(job.payload)
        job.result = result
        job.status = JobStatus.succeeded
        job.finished_at = utcnow()
        job.last_error = None
        db.commit()
        log.info("job succeeded", extra={"job_id": job_id, "event": "job_succeeded"})
        return

    except Exception as e:
        job.attempts += 1
        job.last_error = str(e)

        if job.attempts >= job.max_attempts:
            job.status = JobStatus.failed
            job.finished_at = utcnow()
            db.commit()

            r.lpush(settings.job_dlq, job_id)
            log.error("job moved to dlq", extra={"job_id": job_id, "event": "job_dlq"}, exc_info=True)
            return

        # backoff: 2^attempts seconds (cap=60s)
        delay = min(60, 2 ** job.attempts)
        run_at = time.time() + delay
        job.status = JobStatus.queued
        db.commit()

        r.zadd(settings.job_delayed, {job_id: run_at})
        log.warning(
            f"job failed, retry scheduled in {delay}s",
            extra={"job_id": job_id, "event": "job_retry_scheduled"},
            exc_info=True,
        )
        return

def main():
    r = get_redis()
    log.info("worker started", extra={"event": "worker_start"})

    while True:
        try:
            moved = move_due_delayed(r)
            if moved:
                log.info(f"moved {moved} delayed jobs", extra={"event": "delayed_moved"})

            job_id = reliable_pop(r, timeout=5)
            if not job_id:
                time.sleep(settings.worker_poll_seconds)
                continue

            with SessionLocal() as db:
                handle_job(db, r, job_id)

            ack_processing(r, job_id)

        except Exception:
            log.error("worker loop error", extra={"event": "worker_loop_error"}, exc_info=True)
            time.sleep(2)

if __name__ == "__main__":
    main()
