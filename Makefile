SHELL := /bin/bash
.DEFAULT_GOAL := help

GO      ?= go
PY      ?= python3
BIN     := bin
COMMIT  := $(shell git rev-parse --short HEAD 2>/dev/null || echo nogit)

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-22s\033[0m %s\n",$$1,$$2}'

.PHONY: proto
proto: ## Generate Go/Python stubs from proto/csc.proto
	@echo "TODO: protoc invocation"

.PHONY: build
build: ## Build all Go services
	$(GO) build -o $(BIN)/ ./cmd/...

.PHONY: test
test: ## Go tests (race) + Python tests
	$(GO) test -race ./...
	$(PY) -m pytest intelligence/tests -q

.PHONY: lint
lint: ## Static analysis
	$(GO) vet ./...
	@command -v ruff >/dev/null && ruff check intelligence analysis || echo "ruff not installed, skipping"

.PHONY: determinism
determinism: ## Gate: same seed must reproduce workload + fault schedule
	@echo "TODO: phase 4 gate"

.PHONY: replay
replay: ## Gate: fork 5 branches from one state, measure dispersion band
	@echo "TODO: phase 5 gate -- critical path"

.PHONY: train calibrate
train: ## Train the temporal predictor
	$(PY) -m intelligence.training.train --config experiments/configs/model.yaml
calibrate: ## Fit conformal calibration on the calibration split
	$(PY) -m intelligence.training.calibrate --config experiments/configs/calibration.yaml

.PHONY: experiment-smoke experiment-main
experiment-smoke: ## Tiny run set for CI
	$(PY) experiments/runners/run.py --profile smoke
experiment-main: ## Full run set (long)
	$(PY) experiments/runners/run.py --profile main

.PHONY: analyze figures tables
analyze: ## metrics + statistics + validation gate
	$(PY) analysis/metrics.py
	$(PY) analysis/statistics.py
	$(PY) analysis/validate_results.py
figures: analyze ## Regenerate every figure from results_long.csv
	$(PY) analysis/figures.py
tables: analyze ## Regenerate every table from results_long.csv
	$(PY) analysis/tables.py

.PHONY: paper
paper: figures tables ## Build the manuscript
	cd paper && latexmk -pdf main.tex

.PHONY: reproduce
reproduce: build test train calibrate experiment-main analyze figures tables paper ## Full pipeline
	@echo "Reproduced at commit $(COMMIT)"

.PHONY: clean
clean:
	rm -rf $(BIN) gen
