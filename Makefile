.PHONY: help up down db-shell migrate run demo seed seed-local api ui test lint types check eval calibrate ablate coverage ui-evals readme-metrics degraded gate clean-state voice-audio voice-bench domain-corpus

COMPOSE := docker compose -f infra/docker-compose.yml

help:
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | expand -t22

up:  ## start Postgres, waiting until it accepts connections
	$(COMPOSE) up -d --wait db

down:  ## stop everything
	$(COMPOSE) down

db-shell:  ## psql into the local database
	docker exec -it triage-db psql -U postgres -d triage

migrate:  ## apply pending migrations
	cd api && uv run python scripts/migrate.py

run: up migrate  ## database, API and dashboard in one command; ctrl-c stops both
	@echo
	@echo "  api   http://localhost:8000"
	@echo "  ui    http://localhost:5173"
	@echo
	@trap 'kill 0' INT TERM; \
	$(MAKE) api & \
	$(MAKE) ui & \
	wait

demo:  ## database, corpus, embeddings and a seeded queue, from nothing
	$(MAKE) up
	$(MAKE) migrate
	cd api && uv run python scripts/load_corpus.py
	cd api && uv run python scripts/gen_synthetic.py
	cd api && uv run python scripts/gen_hinglish.py
	cd api && uv run python scripts/embed_corpus.py
	$(MAKE) seed-local

seed:  ## submit demo tickets through the running API
	cd api && uv run python scripts/seed_demo.py

api:  ## run the API with reload
	cd api && uv run uvicorn app.main:app --reload

ui:  ## run the dashboard
	cd ui && bun run dev

test:  ## offline test suite (api + dashboard)
	cd api && uv run pytest -q
	cd ui && bun run test

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

ui-evals:  ## regenerate the dashboard's eval data from the latest report
	cd api && uv run python scripts/export_ui_evals.py

readme-metrics:  ## rewrite the README's metrics block from the same export
	cd api && uv run python scripts/export_readme_metrics.py

seed-local:  ## run the golden set through the pipeline into the local queues
	cd api && uv run python scripts/seed_local.py

ablate:  ## does the judge earn its weight? offline, no keys, no cost
	cd api && uv run python scripts/ablate_judge.py

domain-corpus:  ## generate and embed a corpus for a generated desk: make domain-corpus D=tech
	cd api && uv run python scripts/gen_domain_corpus.py --domain $(D)
	cd api && uv run python scripts/embed_corpus.py

voice-audio:  ## synthesise the golden set as speech, once; cached after that
	cd api && uv run python scripts/voice_bench.py --audio-only

voice-bench:  ## time to first audio, every arm. serial by design, so it takes ~45 min
	cd api && uv run python scripts/voice_bench.py

degraded:  ## report runs that finished but did not work
	cd api && uv run python scripts/check_degraded.py

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
