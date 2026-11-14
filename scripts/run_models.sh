#!/usr/bin/env bash
# Full multi-model sweep. Requires API keys in the environment.
# Do not invent results — only run when keys exist.
set -euo pipefail

# Configurable model list (provider:model_id)
MODELS=(
  "anthropic:claude-haiku-4-5-20251001"
  "openai:gpt-4o-mini"
  "google:gemini-3.8-flash"
)

MAX_COST_USD="${MAX_COST_USD:-25}"
TASKS="${TASKS:-all}"
TRIALS="${TRIALS:-3}"

for m in "${MODELS[@]}"; do
  provider="${m%%:*}"
  case "$provider" in
    anthropic) keyvar=ANTHROPIC_API_KEY ;;
    openai) keyvar=OPENAI_API_KEY ;;
    google) keyvar=GOOGLE_API_KEY ;;
    *) echo "unknown provider $provider"; exit 1 ;;
  esac
  if [[ -z "${!keyvar:-}" ]]; then
    echo "skip $m ($keyvar not set)"
    continue
  fi
  safe="${m//[:\/]/_}"
  echo "Running $m ..."
  paybench run --agent llm --model "$m" --tasks "$TASKS" --trials "$TRIALS" \
    --max-cost-usd "$MAX_COST_USD" --out "results/llm_${safe}" || true
done

echo "TODO(real-run): aggregate with paybench report / paybench site once runs finish"
