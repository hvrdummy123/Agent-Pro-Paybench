#!/usr/bin/env bash
set -euo pipefail
shopt -s nullglob
runs=(results/*/)
args=()
for r in "${runs[@]}"; do
  if [[ -f "${r}episodes.jsonl" ]]; then
    args+=(--runs "$r")
  fi
done
if [[ ${#args[@]} -eq 0 ]]; then
  echo "No results/*/episodes.jsonl found. Run baselines first."
  exit 1
fi
paybench site "${args[@]}" --out site
echo "Wrote site/"
