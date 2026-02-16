FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml /app/
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .

COPY worker.py /app/worker.py
COPY db.py /app/db.py
COPY models.py /app/models.py
COPY settings.py /app/settings.py
COPY redis_client.py /app/redis_client.py
COPY logging_utils.py /app/logging_utils.py

CMD ["python", "-u", "worker.py"]
