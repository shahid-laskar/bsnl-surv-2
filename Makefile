.PHONY: dev test lint

dev:
	docker compose up -d

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check .
	cd backend && uv run mypy app
