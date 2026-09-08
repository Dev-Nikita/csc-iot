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
TAGS ?=

build: ## Build all Go services (make build TAGS=nats for the NATS transport)
	$(GO) build -tags "$(TAGS)" -o $(BIN)/ ./cmd/...

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
	$(GO) test -race -run 'Determin|SameSeed|Diverge' ./internal/... -v

.PHONY: replay
replay: build ## M2: reconstruct a prefix and execute every candidate action
	./$(BIN)/csc-replay -seed 42 -scenario F1 -measure-s 60 -horizon 60 \
	  -anchors 60,70,80,90,100,110,120,130,140,150 -reps 2 -out data/raw/replay

.PHONY: check-stale
check-stale: ## Fail if superseded terminology reappears in the manuscript
	cd paper && $(PY) check_stale.py && $(PY) check_citations.py

.PHONY: check-stack
check-stack: ## Refuse reportable runs on a development substrate
	$(PY) check_reportable_stack.py

.PHONY: deps-adapters
deps-adapters: ## Fetch the modules the restricted build environment cannot reach
	$(GO) get github.com/nats-io/nats.go
	$(GO) get github.com/nats-io/nats-server/v2
	$(GO) mod tidy
	@echo "adapter modules fetched; go.mod and go.sum updated -- commit them"

.PHONY: docker-preflight
docker-preflight: ## Catch the image/go.mod mismatch before a five-minute build
	@req=$$(awk '/^go /{print $$2; exit}' go.mod); \
	img=$$(awk -F= '/^ARG GO_VERSION/{print $$2}' deploy/go.Dockerfile); \
	echo "go.mod requires go $$req; image base is golang:$$img-alpine"; \
	test -f go.sum || { echo "go.sum missing -- run: go mod tidy"; exit 1; }; \
	case "$$req" in "$$img"*) : ;; *) \
	  echo ""; \
	  echo "MISMATCH. go.mod asks for $$req, deploy/go.Dockerfile builds on $$img."; \
	  echo "`go get` rewrites the go directive to the toolchain that ran it."; \
	  echo "Either bump GO_VERSION in deploy/go.Dockerfile, or build with:"; \
	  echo "  docker compose build --build-arg GO_VERSION=$${req%%.*}.$$(echo $$req | cut -d. -f2)"; \
	  echo ""; exit 1 ;; esac

.PHONY: audit
audit: ## Invariants that have each been silently reverted at least once
	scripts/audit_repo.sh

.PHONY: check-modfile
check-modfile: ## go.mod and go.sum are machine-generated and easy to clobber
	@grep -q 'nats-io/nats.go' go.mod || { \
	  echo ""; \
	  echo "go.mod has lost its adapter requirements."; \
	  echo "This happens when an archive extracted over the repo carries its own"; \
	  echo "go.mod -- it has happened once in this project already."; \
	  echo ""; \
	  echo "  make deps-adapters      # go.sum is usually intact; this restores go.mod"; \
	  echo ""; \
	  exit 1; }
	@test -f go.sum || { echo "go.sum missing -- run: go mod tidy"; exit 1; }
	@echo "go.mod: $$(awk '/^go /{print $$2}' go.mod), adapters required, go.sum present"

.PHONY: check-adapter-deps
check-adapter-deps: ## Fail with an instruction rather than a raw module error
	@$(GO) list -m github.com/nats-io/nats.go >/dev/null 2>&1 || { \
	  echo ""; \
	  echo "The NATS and gRPC adapters are behind build tags and their modules"; \
	  echo "are not in go.mod yet. They were written in an environment that"; \
	  echo "cannot reach proxy.golang.org, so they have never been compiled."; \
	  echo ""; \
	  echo "  make deps-adapters"; \
	  echo ""; \
	  echo "then re-run make local-validate. Expect the first build to surface"; \
	  echo "real compile errors in nats.go / grpc.go: that is the point of this"; \
	  echo "step, and fixing them is A1b."; \
	  echo ""; \
	  exit 1; }

.PHONY: local-validate
local-validate: audit check-modfile check-adapter-deps ## A1b gate: run on the target host, with modules and root
	@echo "== 1. development substrate =="
	$(GO) build ./... && $(GO) vet ./... && $(GO) test -race ./...
	@echo "== 2. adapters that cannot be built in the restricted environment =="
	$(GO) test -tags=nats -race ./internal/bus/
	@echo "   (gRPC is optional -- see internal/rpc/grpc.go; the framed adapter"
	@echo "    already satisfies the typed-RPC boundary the paper claims)"
	@echo "== 3. topology =="
	@$(MAKE) --no-print-directory docker-preflight
	docker compose up --build -d && sleep 10 && docker compose ps
	@echo "== 4. kernel impairment on device-to-gateway egress only =="
	scripts/netem_smoke.sh
	@echo "== 5. RPC deadline and fallback =="
	$(GO) test -race -run Deadline ./internal/rpc/
	@echo "== 6. stack identity =="
	$(GO) run ./cmd/csc-stackstamp -bus tcp -bus-version a1a-1
	@echo ""
	@echo "The next check is EXPECTED to fail on the development stack: the"
	@echo "stdlib broker and application-layer impairment are not reportable."
	@echo "Run 'make stack-nats' for the transport a reported measurement needs."
	@echo ""
	-$(PY) check_reportable_stack.py

.PHONY: up-nats
up-nats: ## Bring up the reportable topology (NATS transport)
	docker compose down --remove-orphans 2>/dev/null || true
	docker compose -f docker-compose.nats.yml up --build -d
	@sleep 10
	docker compose -f docker-compose.nats.yml ps

.PHONY: netem-nats
netem-nats: ## Verify impairment on the NATS stack, then remove it
	COMPOSE="docker compose -f docker-compose.nats.yml" scripts/netem_smoke.sh

.PHONY: netem-apply
netem-apply: ## Apply impairment and LEAVE it in place for the stack stamp
	KEEP=1 COMPOSE="docker compose -f docker-compose.nats.yml" scripts/netem_smoke.sh

.PHONY: deploy
deploy: ## Sync to a Linux host and audit it there: make deploy HOST=cybernord
	scripts/deploy_to_host.sh "$(or $(HOST),cybernord)" "$(or $(DEST),~/csc-iot)"

.PHONY: m2prime-local
m2prime-local: build ## Prefix-equality check on the local process topology (no Docker)
	scripts/m2prime_smoke.sh

.PHONY: m2prime-nats
m2prime-nats: ## Prefix-equality check against the running NATS stack
	@# -tags=nats is not optional here: without it the binary refuses the
	@# transport by name, which is the guard doing its job on the wrong target.
	@stack_id="$$($(PY) check_reportable_stack.py --print-stack-id)"; \
	  revision="$$(git rev-parse --short HEAD 2>/dev/null || sed -n '1p' SOURCE_REVISION)"; \
	  run="$$(date -u +%Y%m%dT%H%M%SZ)"; out="data/raw/smoke-nats/$$run/anchor.json"; \
	  mkdir -p "$$(dirname "$$out")"; \
	  $(GO) run -tags=nats ./cmd/csc-orchestrator -bus nats://127.0.0.1:4222 -bus-impl nats \
	    -nodes gw00,gw01,edge00,edge01,edge02,ctl,dev-sim \
	    -anchor 4 -epochs 6 -timeout 90s -runtime-stack-id "$$stack_id" \
	    -git-commit "$$revision" -out "$$out"; \
	  $(PY) analysis/check_anchor.py "$$out"

.PHONY: m2prime-nats-matrix
m2prime-nats-matrix: ## Reportable 30x3x10 M2' (requires validated NATS stack)
	$(MAKE) build TAGS=nats
	STACK_ID="$$($(PY) check_reportable_stack.py --print-stack-id)" scripts/m2prime_nats_matrix.sh

.PHONY: stack-nats
stack-nats: netem-apply ## Apply impairment, stamp, and validate the NATS stack
	COMPOSE_FILE=docker-compose.nats.yml $(GO) run ./cmd/csc-stackstamp \
	  -bus nats \
	  -bus-version "$$(docker compose -f docker-compose.nats.yml exec -T nats nats-server -v 2>/dev/null | tr -d '\r' || echo unknown)" \
	  -transport-hash "$$(python3 -c 'import hashlib; print(hashlib.sha256(b"nats-core-pubsub;jetstream=false").hexdigest()[:16])' )" \
	  -netem-service device-sim
	$(PY) check_reportable_stack.py
	@echo "REPORTABLE_STACK_VALIDATED"

.PHONY: train calibrate
train: ## Train the temporal predictor
	$(PY) -m intelligence.training.train --config experiments/configs/model.yaml
calibrate: ## Fit conformal calibration on the calibration split
	$(PY) -m intelligence.training.calibrate --config experiments/configs/calibration.yaml

.PHONY: experiment-smoke experiment-main
experiment-smoke: build ## Phase A acceptance: 100 devices, F1, threshold controller
	@rm -rf data/raw/F1-B1_threshold-seed042 experiments/manifests/F1-B1_threshold-seed042.json
	./$(BIN)/csc-sim -seed 42 -scenario F1 -devices 100 -measure-s 60 \
	  -out data/raw -manifests experiments/manifests
	@echo "--- rerun at the same seed: the determinism digest must match ---"
	./$(BIN)/csc-sim -seed 42 -scenario F1 -devices 100 -measure-s 60 \
	  -out /tmp/csc-smoke-verify -manifests /tmp/csc-smoke-verify
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
paper: figures tables check-stale ## Build the manuscript
	cd paper && latexmk -pdf main.tex

.PHONY: reproduce
reproduce: build test train calibrate experiment-main analyze figures tables paper ## Full pipeline
	@echo "Reproduced at commit $(COMMIT)"

.PHONY: clean
clean:
	rm -rf $(BIN) gen
