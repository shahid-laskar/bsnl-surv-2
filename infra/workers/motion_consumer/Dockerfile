# infra/workers/motion_consumer/Dockerfile
# Build from repo root, AFTER building the base image:
#   docker build -f infra/workers/base/Dockerfile -t sarvanetra-worker-base:latest .
#   docker build -f infra/workers/motion_consumer/Dockerfile -t sarvanetra-motion-consumer:latest .
#
# In docker-compose, the `build.context`/`build.dockerfile` below assumes
# compose builds sarvanetra-worker-base itself via a `worker-base` service
# (see docker-compose.yml) so this just FROMs the tagged image — no manual
# two-step build needed when running `docker compose up --build`.

FROM sarvanetra-worker-base:latest

WORKDIR /app

COPY motion_consumer.py /app/motion_consumer.py

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8081/health || exit 1

CMD ["python", "-m", "motion_consumer"]
