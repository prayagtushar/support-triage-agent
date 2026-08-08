.PHONY: help up down db-shell migrate seed api ui test lint types check eval calibrate ablate coverage gate clean-state

COMPOSE := docker compose -f infra/docker-compose.yml

help:
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t22

up:  ## start Postgres
	$(COMPOSE) up -d db

down:  ## stop everything
	$(COMPOSE) down

db-shell:  ## psql into the local database
	docker exec -it triage-db psql -U postgres -d triage

migrate:  ## apply pending migrations
	cd api && uv run python scripts/migrate.py

seed:  ## submit demo tickets through the running API
	cd api && uv run python scripts/seed_demo.py

api:  ## run the API with reload
	cd api && uv run uvicorn app.main:app --reload

ui:  ## run the dashboard
	cd ui && bun run dev

test:  ## offline test suite
	cd api && uv run pytest -q

lint:  ## ruff
	cd api && uv run ruff check . && uv run ruff format --check .

types:  ## mypy
	cd api && uv run mypy app scripts

check: lint types test  ## everything CI runs

eval:  ## full eval suite, needs API keys and minutes
	cd api && uv run python scripts/run_evals.py

calibrate:  ## reliability diagram from the latest report
	cd api && uv run python scripts/plot_calibration.py

coverage:  ## where the golden set is too thin to support its claims
	cd api && uv run python scripts/golden_coverage.py

ablate:  ## does the judge earn its weight? offline, no keys, no cost
	cd api && uv run python scripts/ablate_judge.py

gate:  ## fail if the latest eval regressed against the baseline
	cd api && uv run python scripts/check_regression.py

clean-state:  ## wipe the database and rebuild the corpus from scratch
	$(COMPOSE) down -v
	$(COMPOSE) up -d db
	sleep 5
	cd api && uv run python scripts/migrate.py \
	  && uv run python scripts/load_corpus.py \
	  && uv run python scripts/gen_synthetic.py \
	  && uv run python scripts/gen_hinglish.py \
	  && uv run python scripts/embed_corpus.py
