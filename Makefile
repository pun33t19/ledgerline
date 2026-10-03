# Ledgerline developer tasks. Run `make help` for a list.
# All Python runs through uv, which manages the virtualenv in .venv.

UV ?= uv

.PHONY: guide help install web-install web-types web-build web-ci e2e ui test lint fmt typecheck vuln fixtures fixtures-check demo ci

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

web-install: ## Install the UI's npm dependencies (web/)
	cd web && npm ci

web-types: ## Regenerate the UI's TypeScript types from the Python API
	$(UV) run python scripts/export_openapi.py
	cd web && npm run types

web-build: ## Build the UI into src/ledgerline/api/static (served by `ledgerline ui`)
	cd web && npm run build

web-ci: web-types ## UI checks: generated types up to date, lint, type check, unit tests, build
	git diff --exit-code -- web/src/api/schema.d.ts
	cd web && npm run lint && npm run typecheck && npm test && npm run build

e2e: web-build ## Browser tests against the real `ledgerline ui` (needs `npx playwright install chromium` once)
	cd web && npm run e2e

ui: web-build ## Build the UI and open the Attack Simulation Lab
	$(UV) run ledgerline ui

guide: ## Build the beginner's guide PDF (docs/guide/Ledgerline-Guide.pdf)
	$(UV) run --group guide python docs/guide/build_guide.py

ci: lint typecheck test ## Everything CI runs except vuln and fixtures
