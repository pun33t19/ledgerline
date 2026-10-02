#!/usr/bin/env bash
# Phase 0 has no runtime behaviour; the demo is that the toolchain and checks pass.
set -euo pipefail
cd "$(dirname "$0")/.."
uv --version
make install ci
echo "Phase 0 OK: toolchain, lint, type checks and tests pass."
