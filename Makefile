# Ledgerline developer tasks. Run `make help` for a list.
# All Python runs through uv, which manages the virtualenv in .venv.

UV ?= uv

.PHONY: guide help install test lint fmt typecheck vuln fixtures fixtures-check demo ci

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## Create .venv and install Ledgerline with dev tools
	$(UV) sync

test: ## Run the test suite
	$(UV) run pytest

lint: ## Check lint and formatting
	$(UV) run ruff check .
	$(UV) run ruff format --check .

fmt: ## Format code and apply safe lint fixes
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

typecheck: ## Run mypy in strict mode
	$(UV) run mypy

vuln: ## Check dependencies for known vulnerabilities
	$(UV) run pip-audit --skip-editable

fixtures: ## Regenerate testdata/mcp wire fixtures
	./scripts/capture-fixtures.sh

fixtures-check: fixtures ## Fail if regenerated fixtures differ from the committed ones
	git diff --exit-code -- testdata/mcp
	@test -z "$$(git ls-files --others --exclude-standard testdata/mcp)" || (echo "untracked fixtures:"; git ls-files --others --exclude-standard testdata/mcp; exit 1)

demo: ## Run the demo for a phase (PHASE=N)
	@test -n "$(PHASE)" || (echo "usage: make demo PHASE=N" && exit 1)
	./demos/phase$(PHASE).sh

guide: ## Build the beginner's guide PDF (docs/guide/Ledgerline-Guide.pdf)
	$(UV) run --group guide python docs/guide/build_guide.py

ci: lint typecheck test ## Everything CI runs except vuln and fixtures
