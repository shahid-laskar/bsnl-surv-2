# infra/workers/upload_worker/Dockerfile
FROM sarvanetra-worker-base:latest

WORKDIR /app

# Extra deps on top of the shared base — only upload_worker needs these.
RUN pip install --no-cache-dir minio==7.* tenacity==9.*

COPY upload_worker.py /app/workers/upload_worker.py

EXPOSE 8083

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8083/health || exit 1

CMD ["python", "-m", "upload_worker"]