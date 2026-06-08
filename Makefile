.PHONY: dev-backend dev-frontend build up down test dev-realtime build-realtime up-realtime down-realtime

dev-backend:
	PYTHONPATH=. uvicorn variants.classic.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm install && npm run dev

build:
	docker compose -f infra/docker/classic/docker-compose.yml build

up:
	docker compose -f infra/docker/classic/docker-compose.yml up

down:
	docker compose -f infra/docker/classic/docker-compose.yml down

test:
	PYTHONPATH=. python -m pytest tests/ -v

dev-realtime:
	PYTHONPATH=. uvicorn variants.realtime.main:app --reload --host 0.0.0.0 --port 8001

build-realtime:
	docker compose -f infra/docker/realtime/docker-compose.yml build

up-realtime:
	docker compose -f infra/docker/realtime/docker-compose.yml up

down-realtime:
	docker compose -f infra/docker/realtime/docker-compose.yml down
