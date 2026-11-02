# Convenience targets for local development (see docs/development.md)
.PHONY: setup db migrate seed api web test test-backend test-web e2e lint up

setup:
	cd backend && uv venv .venv && uv pip install --python .venv/bin/python -e '.[dev]'
	cd frontend && npm install

migrate:
	cd backend && .venv/bin/alembic upgrade head

seed:
	cd backend && .venv/bin/python -m app.cli seed-demo

api:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

web:
	cd frontend && npm run dev

test: test-backend test-web

test-backend:
	cd backend && .venv/bin/pytest -q tests ../companion/tests

test-web:
	cd frontend && npx tsc --noEmit && npm test

e2e:
	cd frontend && npm run build && npm run e2e

lint:
	cd backend && .venv/bin/ruff check app tests ../companion

up:
	docker compose up --build
