#!/usr/bin/env bash
# Phase 0 has no runtime behaviour yet; the demo is that the toolchain and CI checks pass.
set -euo pipefail
cd "$(dirname "$0")/.."
go version
make ci
echo "Phase 0 OK: toolchain, lint and tests pass."
