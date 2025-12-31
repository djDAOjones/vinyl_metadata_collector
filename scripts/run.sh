#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -d .venv ]]; then
  echo "Virtual environment (.venv) not found. Run scripts/deploy_environment_and_run.sh first." >&2
  exit 1
fi

source .venv/bin/activate

if [[ -f ../list_in.xlsx ]]; then
  INPUT_PATH="../list_in.xlsx"
elif [[ -f ../list_in.csv ]]; then
  INPUT_PATH="../list_in.csv"
else
  echo "Unable to find ../list_in.xlsx or ../list_in.csv" >&2
  exit 1
fi

windsurf-discogs \
  --input "$INPUT_PATH" \
  --output ./list_out.csv \
  --token-file ../discogs_personal_access_token

printf '\nRun complete. Output file: %s\n' "$PROJECT_ROOT/list_out.csv"
