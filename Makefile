.PHONY: install run test lint format typecheck migrate migration seed openapi up down cleanup

install:
	pip install -r requirements-dev.txt

run:
	uvicorn app.main:app --reload

test:
	pytest --cov=app --cov-report=term-missing

lint:
	ruff check .

format:
	black .

typecheck:
	mypy app

migrate:
	alembic upgrade head

migration:
	alembic revision --autogenerate -m "$(m)"

seed:
	python scripts/seed.py

openapi:
	python scripts/export_openapi.py

cleanup:
	python scripts/cleanup_tokens.py

up:
	docker compose up --build

down:
	docker compose down
