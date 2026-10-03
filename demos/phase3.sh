#!/usr/bin/env bash
# Phase 3 demo: the Attack Simulation Lab in your browser.
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --quiet
if [[ ! -d web/node_modules ]]; then
  echo "Installing the UI's dependencies (first run only)..."
  (cd web && npm ci --silent)
fi
make -s web-build >/dev/null

cat <<'TXT'

Opening the Ledgerline Lab. Things to try:

  1. Run "Silent rug pull": the left side leaks the fake secret, the right side is
     stopped by "Check before every call". Click entries to inspect raw messages.
  2. Switch "Check before every call" off and press "Run with these controls":
     now the attack succeeds on both sides.
  3. Run "Rug pull" and open "What the model reads": the changed description is
     highlighted, and Ledgerline hides it from the model.
  4. Run "Tool poisoning": an honest limit; pinning approved the poisoned tool.
  5. Open "Coverage": which control stops which attack, measured by replaying
     each attack with one control switched off at a time.

Press Ctrl+C here to stop the Lab.
TXT
exec uv run ledgerline ui
