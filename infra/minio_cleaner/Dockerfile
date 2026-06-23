# infra/minio_cleaner/Dockerfile
#
# Scheduled job: deletes objects in MinIO older than RETENTION_DAYS.
# Runs once per loop, sleeps, repeats — no cron daemon needed since this
# is the container's whole job (restart: unless-stopped in compose keeps
# it alive; the script itself loops forever).

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --no-cache-dir minio==7.*

COPY infra/minio_cleaner/clean.py /app/clean.py

CMD ["python", "/app/clean.py"]
