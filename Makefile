.PHONY: up down migrate revision test lint fmt e2e

up:
	docker compose up -d

down:
	docker compose down

migrate:
	docker compose exec api alembic upgrade head

revision:
	docker compose exec api alembic revision --autogenerate -m "$(m)"

test:
	docker compose exec api pytest -q

lint:
	docker compose exec api sh -c "ruff check app && mypy app/domain app/application"
	cd frontend && npm run lint && npm run typecheck

fmt:
	docker compose exec api ruff format app
	cd frontend && npm run format

e2e:
	cd frontend && npx playwright test
