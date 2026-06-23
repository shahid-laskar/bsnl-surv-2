# infra/workers/status_monitor/Dockerfile
FROM sarvanetra-worker-base:latest

WORKDIR /app

COPY status_consumer.py /app/status_consumer.py

EXPOSE 8084

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8084/health || exit 1

CMD ["python", "-m", "status_consumer"]
