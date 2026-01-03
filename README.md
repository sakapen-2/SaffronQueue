# SaffronQueue

Mini job queue system:
- FastAPI API
- Redis queue + delayed retries (zset) + DLQ
- Postgres for job state
- JSON logs
- GitLab CI builds Docker images

## Run (local)
```bash
docker compose up --build
