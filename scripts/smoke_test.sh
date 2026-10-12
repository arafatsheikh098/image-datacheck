#!/usr/bin/env bash
# Smoke test for a freshly built wheel. Mirrors what CI runs in the
# "install in a clean venv and run the CLI" job.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WHEEL="$(ls dist/*.whl | head -1)"
if [ -z "$WHEEL" ]; then
  echo "No wheel found; run 'python -m build' first." >&2
  exit 1
fi

VENV="$(mktemp -d)/idc-smoke"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet "$WHEEL"

"$VENV/bin/imagedatacheck" --version
"$VENV/bin/imagedatacheck" --help > /dev/null
# The demo dataset is intentionally broken; we just want to confirm the
# CLI runs end-to-end. --fail-on=never keeps the exit code 0.
"$VENV/bin/imagedatacheck" scan examples/demo --quiet --fail-on=never

rm -rf "$VENV"
echo "smoke test passed"
