#!/usr/bin/env bash
# Preserve Bend's exact output/status while retaining the real proof verdict.
set -u
log=$(mktemp "$ACCEPTANCE_EVIDENCE/bend-call.XXXXXX.log")
"$ACCEPTANCE_REAL_BEND" "$@" >"$log" 2>&1
code=$?
printf '%s\n' "$code" >"$log.exit"
printf '%q ' "$@" >"$log.args"
printf '\n' >>"$log.args"
if [ "${1:-}" = PROOF.bend ]; then
  cp "$log" "$ACCEPTANCE_EVIDENCE/proof.log"
  printf '%s\n' "$code" >"$ACCEPTANCE_EVIDENCE/proof.exit"
fi
cat "$log"
exit "$code"
