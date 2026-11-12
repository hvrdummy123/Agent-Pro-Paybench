#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
paybench run --agent oracle --tasks all --out results/oracle_all
paybench run --agent null --tasks all --out results/null_all
paybench run --agent naive --tasks all --out results/naive_all
paybench run --agent random --tasks all --out results/random_all
paybench report results/oracle_all
paybench site --runs results/oracle_all --runs results/null_all --runs results/naive_all --runs results/random_all --out site
echo "Baselines complete. Open site/index.html"
