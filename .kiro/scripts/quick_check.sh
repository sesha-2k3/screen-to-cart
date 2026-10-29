#!/usr/bin/env bash
# Stop hook: fast checks after each agent turn.
# Exit 0 -> stdout is added to the agent's context.
# Non-zero -> stderr is sent to the agent as an error to fix.
set -u
failed=0
report=""

if [ -f backend/pyproject.toml ]; then
  if ! out=$(cd backend && uv run ruff check . --quiet 2>&1); then
    failed=1; report+=$'\n[ruff]\n'"$out"
  fi
  out=$(cd backend && LLM_MODE=replay uv run pytest -q -x -m "not live" 2>&1)
  code=$?
  # exit code 5 = no tests collected yet, which is fine early on
  if [ $code -ne 0 ] && [ $code -ne 5 ]; then
    failed=1; report+=$'\n[pytest]\n'"$(echo "$out" | tail -n 30)"
  fi
fi

if [ -f extension/package.json ] && [ -d extension/node_modules ]; then
  if ! out=$(cd extension && pnpm exec tsc --noEmit 2>&1); then
    failed=1; report+=$'\n[tsc]\n'"$(echo "$out" | tail -n 30)"
  fi
fi

if [ $failed -ne 0 ]; then
  echo "Quick check failed. Fix these before moving on:$report" >&2
  exit 1
fi
echo "Quick check passed (ruff, offline tests, tsc)."
