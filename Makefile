.PHONY: help up down migrate seed test api-shell clean

help:
	@echo "Available commands:"
	@echo "  make migrate     - Run Alembic migrations"
	@echo "  make seed        - Add seed data"
	@echo "  make test        - Run tests"
	@echo "  make api-shell   - Open API shell"
	@echo "  make clean       - Clean temporary files"

migrate:
	cd backend && alembic upgrade head

migrate-create:
	cd backend && alembic revision --autogenerate -m "$(MSG)"

seed:
	cd backend && python -m app.scripts.seed

test:
	cd backend && pytest -v

api-shell:
	cd backend && python -c "from app.db.session import SessionLocal; from app.db import models; db = SessionLocal(); import IPython; IPython.embed()"

clean:
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	rm -rf backend/.pytest_cache
	rm -rf frontend/.next
	rm -rf frontend/node_modules/.cache
