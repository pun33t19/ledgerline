#!/usr/bin/env bash
# Regenerates testdata/mcp/*.jsonl: raw JSON-RPC traffic between demo-client
# and each demo server over stdio. Phase 2 replays these through the proxy and
# expects them to pass through unchanged, so they must be deterministic.
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --quiet
bin=.venv/bin
out=testdata/mcp
mkdir -p "$out"

"$bin/demo-client" --wire "$out/weather-stdio.jsonl" \
  --call get_weather --args '{"location":"Pune, IN","unit":"celsius"}' \
  -- "$bin/demo-weather" >/dev/null

"$bin/demo-client" --wire "$out/poisoned-stdio.jsonl" \
  --call add --args '{"a":2,"b":3,"sidenote":"FAKE_API_KEY=demo-not-a-real-key"}' \
  -- "$bin/demo-poisoned" >/dev/null 2>&1

"$bin/demo-client" --wire "$out/rugpull-stdio.jsonl" \
  --call get_fact_of_the_day --repeat 4 \
  -- "$bin/demo-rugpull" --after 3 >/dev/null

"$bin/demo-client" --legacy --wire "$out/weather-stdio-legacy.jsonl" \
  --call get_weather --args '{"location":"Pune, IN","unit":"celsius"}' \
  -- "$bin/demo-weather" >/dev/null

echo "captured: $(ls "$out"/*.jsonl | tr '\n' ' ')"
