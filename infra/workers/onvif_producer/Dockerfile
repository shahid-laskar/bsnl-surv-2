# infra/workers/onvif_producer/Dockerfile
#
# Note: onvif_producer.py is a PRODUCER, not a consumer — it does not extend
# BaseKafkaConsumer (there's nothing to consume/commit/DLQ; it publishes to
# Kafka). It still builds FROM the shared worker base for the common deps
# and health-server pattern, but needs its own extra packages: aiohttp
# (async ONVIF SOAP calls) and asyncpg (direct camera_master queries).

FROM sarvanetra-worker-base:latest

WORKDIR /app

RUN pip install --no-cache-dir aiohttp==3.* asyncpg==0.30.*

COPY onvif_producer.py /app/onvif_producer.py

EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8082/health || exit 1

CMD ["python", "-m", "onvif_producer"]
