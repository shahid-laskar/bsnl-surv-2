# Runbook

## Deployment
1. Start infrastructure: `docker compose up -d`
2. Run database migrations: `docker compose exec fastapi alembic upgrade head`

## Troubleshooting
- **MediaMTX not streaming**: Check `docker compose logs mediamtx`
- **Workers failing**: Check Kafka topic configuration via `http://localhost:8080` (Kafka UI)
