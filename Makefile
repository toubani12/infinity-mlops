SHELL := /bin/bash

ENV_FILE := $(firstword $(wildcard infra/env/.env) infra/env/.env.example)
COMPOSE := docker compose -f infra/docker-compose.yml --env-file $(ENV_FILE)
INFRA_SERVICES := kafka postgres minio mlflow
PYTHON_PROJECTS := libs/contracts apps/fastapi-ml services/drift-monitor services/agents-langgraph pipelines
WEB_PROJECT := apps/frontend-next

export UV_SYSTEM_CERTS ?= 1

.PHONY: help up up-apps down reset logs ps topics test lint fmt seed minikube e2e-demo k8s-validate

help:
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-13s %s\n", $$1, $$2}'

up: ## start Kafka, PostgreSQL, MinIO and MLflow, create buckets and topics
	$(COMPOSE) up -d --wait --wait-timeout 180 $(INFRA_SERVICES)
	$(COMPOSE) run --rm kafka-init

up-apps: up ## build and start the application services on top of the infra
	$(COMPOSE) --profile apps up -d --build

down: ## stop every container, keep volumes
	$(COMPOSE) --profile apps down --remove-orphans

reset: ## stop every container and delete the volumes
	$(COMPOSE) --profile apps down --remove-orphans --volumes

logs: ## follow logs, optionally for one service: make logs s=mlflow
	$(COMPOSE) --profile apps logs -f --tail=100 $(s)

ps: ## show containers and health
	$(COMPOSE) --profile apps ps -a

topics: ## create missing topics, re-apply retention and describe them
	$(COMPOSE) run --rm kafka-init
	$(COMPOSE) exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe

test: ## run the tests of every Python project that has a pyproject.toml
	@set -e; for dir in $(PYTHON_PROJECTS); do \
		if [ -f $$dir/pyproject.toml ]; then echo "== $$dir"; (cd $$dir && uv run pytest -q); fi; \
	done

lint: ## ruff on Python projects, eslint on the dashboard when present
	@set -e; for dir in $(PYTHON_PROJECTS); do \
		if [ -f $$dir/pyproject.toml ]; then echo "== $$dir"; \
			(cd $$dir && uv run ruff check . && uv run ruff format --check .); fi; \
	done
	@if [ -f $(WEB_PROJECT)/package.json ]; then echo "== $(WEB_PROJECT)"; (cd $(WEB_PROJECT) && npm run lint); fi

fmt: ## format Python projects with ruff
	@set -e; for dir in $(PYTHON_PROJECTS); do \
		if [ -f $$dir/pyproject.toml ]; then (cd $$dir && uv run ruff check --fix . && uv run ruff format .); fi; \
	done

seed: ## send demo transactions through the backend when the seed script exists
	@if [ -f scripts/seed-transactions.py ]; then uv run scripts/seed-transactions.py; \
	else echo "scripts/seed-transactions.py does not exist yet"; fi

minikube: ## start minikube and deploy the minikube overlay
	@if [ -f scripts/bootstrap-minikube.sh ]; then bash scripts/bootstrap-minikube.sh; \
	else echo "scripts/bootstrap-minikube.sh does not exist yet"; exit 1; fi

e2e-demo: ## run the short end-to-end scenario against the current kubectl context (after make minikube)
	bash scripts/e2e/demo-short.sh

k8s-validate: ## render the kustomize base and both overlays
	@test -f k8s/overlays/minikube/secrets.env || cp k8s/overlays/minikube/secrets.env.example k8s/overlays/minikube/secrets.env
	@set -e; for dir in k8s/base k8s/overlays/minikube k8s/overlays/ci-kind; do \
		echo "== $$dir"; kubectl kustomize $$dir > /dev/null; \
	done
