# Ledgerline developer tasks. Run `make help` for a list.

GO       ?= go
PKGS     := ./...
VERSION  ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo v0.0.0-dev)
LDFLAGS  := -X github.com/pun33t19/ledgerline/internal/version.Version=$(VERSION)

.PHONY: help test test-short lint fmt vet vuln tidy build demo ci

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

test: ## Run all tests with the race detector
	$(GO) test -race -count=1 $(PKGS)

test-short: ## Run fast tests only
	$(GO) test -short $(PKGS)

lint: ## Run golangci-lint
	golangci-lint run

fmt: ## Format code
	golangci-lint fmt

vet: ## Run go vet
	$(GO) vet $(PKGS)

vuln: ## Check dependencies for known vulnerabilities
	$(GO) run golang.org/x/vuln/cmd/govulncheck@latest $(PKGS)

tidy: ## Tidy go.mod/go.sum
	$(GO) mod tidy

build: ## Build all binaries into ./bin
	$(GO) build -ldflags "$(LDFLAGS)" -o bin/ $(PKGS)

demo: ## Run the demo for the current phase (PHASE=N)
	@test -n "$(PHASE)" || (echo "usage: make demo PHASE=N" && exit 1)
	./demos/phase$(PHASE).sh

ci: vet lint test ## Everything CI runs (except govulncheck)
