# infra/workers/base/Dockerfile
#
# Shared base image for all Kafka workers (motion_consumer, onvif_producer,
# status_monitor, upload_worker). Each worker's own Dockerfile is FROM this
# image — one place for shared deps, one place for the shared base_consumer.py
# and app/ package, so the four workers can't drift the way the Python files
# did before being rewritten against BaseKafkaConsumer.
#
# Build from the repo root:
#   docker build -f infra/workers/base/Dockerfile -t sarvanetra-worker-base:latest .

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps shared by all workers (curl for healthchecks; build-essential
# only if any pinned wheel needs compiling — drop this if everything has
# prebuilt wheels for slim/3.12 to keep the image smaller).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Shared Python dependencies across all workers. Worker-specific extras
# (e.g. minio, tenacity for upload_worker; aiohttp for onvif_producer)
# are installed in each worker's own Dockerfile layer on top of this.
COPY infra/workers/base/requirements.txt /app/requirements-base.txt
RUN pip install --no-cache-dir -r requirements-base.txt

# Code shared by every worker: the BaseKafkaConsumer class and the app/
# package (settings, models) the workers import from.
COPY workers/base_consumer.py /app/workers/base_consumer.py
COPY app /app/app
RUN touch /app/workers/__init__.py /app/__init__.py