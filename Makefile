SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

.DEFAULT_GOAL := help

# Docker
PROJECT := hm-contextual-search-f3d5
LOCATION := europe-west1
REGISTRY := llm-ar-dev
IMAGE_NAME ?= conversational-search
VERSION ?= latest
DOCKERFILE ?= Dockerfile
IMG := $(IMAGE_NAME):$(VERSION)
ACTION ?=

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk -F ':.*##' '{gsub(/^[[:space:]]+/, "", $$2); printf "  %-20s %s\n", $$1, $$2}'

install: ## Install base dependencies
	uv sync --no-editable --no-dev

install-all: ## Install all dependencies
	uv sync --all-groups

build: ## Build the project package
	uv build

test: ## Run tests with coverage
	uv run pytest -vv --cov --disable-warnings

format: ## Format code
	uv run ruff format
	uv run ruff check

typecheck: ## Run type checker
	uv run mypy src tests

lint: ## Lint with pylint
	uv run pylint -j 4 src tests

docker-bp: ## Build and push Docker image (override with DOCKERFILE, IMAGE_NAME, VERSION)
	@if [[ -z "$(IMAGE_NAME)" || -z "$(VERSION)" || -z "$(DOCKERFILE)" ]]; then \
	  echo "Usage: make docker-bp DOCKERFILE=path/to/Dockerfile IMAGE_NAME=<image-name> VERSION=<tag>"; \
	  exit 1; \
	fi
	docker build -f $(DOCKERFILE) -t $(LOCATION)-docker.pkg.dev/$(PROJECT)/$(REGISTRY)/$(IMG) .
	docker push $(LOCATION)-docker.pkg.dev/$(PROJECT)/$(REGISTRY)/$(IMG)

run-tf: scripts/run_terraform.sh ## Run Terraform script e.g. make run-tf ACTION=destroy
	./scripts/run_terraform.sh $(ACTION)

gc-build: cloudbuild.yaml ## Run Google Cloud Build e.g. make gc-build DOCKERFILE=./docker/vllm/Dockerfile REGISTRY=llm-ar-dev
	@if [[ -z "$(DOCKERFILE)" ]]; then \
	  echo "Usage: make gc-build DOCKERFILE=./docker/vllm/Dockerfile REGISTRY=llm-ar-dev"; \
	  exit 1; \
	fi
	gcloud builds submit --config cloudbuild.yaml \
		--substitutions=_LOCATION=$(LOCATION),_REGISTRY=$(REGISTRY),_DOCKERFILE=$(DOCKERFILE) \
		.

clean: ## Clean caches, coverage, build, and terraform artifacts
	rm -rf dist build
	find . \( -name "__pycache__" -o -name ".mypy_cache" -o -name ".pytest_cache" -o -name ".ruff_cache" -o -name "*.egg-info" -o -name ".ipynb_checkpoints" -o -name ".terraform" -o -name "charts" \) -exec rm -rf {} +
	find . \( -name "*.pyc" -o -name ".coverage" -o -name "coverage.xml" -o -name "*.tfplan" \) -delete

precommit: format lint typecheck test ## Run pre-commit checks (format, lint, typecheck, test)

all: ## Install, lint and test
	$(MAKE) install
	$(MAKE) lint
	$(MAKE) test

.PHONY: help install install-all build test format typecheck lint docker-bp run-tf gc-build clean precommit all