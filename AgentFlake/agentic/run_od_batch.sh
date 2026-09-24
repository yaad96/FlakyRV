#!/usr/bin/env bash
# Run the 41 OD containers sequentially, one after another.
#
# Usage:
#   ./run_od_batch.sh
#
# Environment:
#   AGENTFLAKE_PROMPT_VARIANT   generic (default here) | typed
#   SKIP_DONE=1                 skip containers that already have an archived run
#   BATCH_LOG_DIR               where per-container logs go
#                               (default: <repo>/batch_logs/od_<variant>_<stamp>)
#
# Deliberately does NOT use `set -e`: one container failing must not stop the
# batch. Each container's stdout/stderr goes to its own log; this script prints
# only one progress line per container plus a summary at the end.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPROFLAKE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$REPROFLAKE_DIR/.." && pwd)"

export AGENTFLAKE_PROMPT_VARIANT="${AGENTFLAKE_PROMPT_VARIANT:-generic}"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${BATCH_LOG_DIR:-$REPO_ROOT/batch_logs/od_${AGENTFLAKE_PROMPT_VARIANT}_${STAMP}}"
mkdir -p "$LOG_DIR"

CONTAINERS=(
  shardingsphereelasticjobelasticjoblitecore23a2ab6
  jnrposixd9f3f84
  dubbodubborpcdubborpcapiba89f441
  shardingsphereelasticjobelasticjoblitecore4b9afa4
  wikidatatoolkitwdtkutil10f9711
  ACCUMULO-2102_testSetInstance_HdfsZooInstance_HostsGiven
  dubbodubborpcdubborpcdubboaa9f16e
  wildflynaming3a83b7b1
  marineapi0a1f309
  ormlitecore59309e5
  oddubbo1
  oduniversalgcodesender1
  oduniversalgcodesender2
  oduniversalgcodesender3
  odshardingsphereelasticjob1
  marineapi0a1f308
  ACCUMULO-2102_testSetInstance_HdfsZooInstance_InstanceGiven
  ormlitecore59309e6
  wildflynaming3a83b7b21
  dubbodubborpcdubborpcapiba89f44
  shardingsphereelasticjobelasticjoblitecore23a2ab5
  ormlitecore59309e10
  wildflynaming3a83b7b20
  dubbodubborpcdubborpcdubbo628ad771
  ACCUMULO-2102_testSetInstance_HdfsZooInstance_Explicit
  shardingsphereelasticjobelasticjoblitecore90e3a7f
  ACCUMULO-2102_testSetInstance_HdfsZooInstance_Implicit
  dubbodubborpcdubborpcdubbo628ad77
  wildflynaming3a83b7b19
  wildflynaming3a83b7b18
  wildflynaming3a83b7b17
  wikidatatoolkitwdtkutil10f9712
  wildflynaming3a83b7b13
  wildflynaming3a83b7b12
  wildflynaming3a83b7b11
  wildflynaming3a83b7b10
  ormlitecore59309e90
  ormlitecore59309e89
  ormlitecore59309e88
  ormlitecore59309e59
  ormlitecore59309e60
)

TOTAL=${#CONTAINERS[@]}

# Ctrl-C must abort the whole batch, not just the container in flight.
trap 'echo; echo "[batch] interrupted - stopping."; exit 130' INT TERM

KEY_FILE="$REPO_ROOT/.anthropic_api_key"
if [[ ! -s "$KEY_FILE" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: no LLM API key available. Paste your Anthropic key into $KEY_FILE"
  exit 1
fi

echo "=========================================="
echo "[batch] OD batch: $TOTAL containers"
echo "[batch] prompt variant : $AGENTFLAKE_PROMPT_VARIANT"
echo "[batch] logs           : $LOG_DIR"
echo "[batch] summary csv    : $REPO_ROOT/Complete_Containers_Summary.csv"
echo "[batch] started        : $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

passed=0; failed=0; skipped=0
declare -a FAILED_LIST=()

for i in "${!CONTAINERS[@]}"; do
  c="${CONTAINERS[$i]}"
  n=$((i + 1))

  if [[ "${SKIP_DONE:-0}" == "1" ]]; then
    runs_dir="$REPROFLAKE_DIR/data/AGENTIC_FULL_RUNS/${c}_runs"
    if [[ -d "$runs_dir" ]] && compgen -G "$runs_dir/*/run_*" > /dev/null; then
      echo "[$n/$TOTAL] $c - already archived, skipping"
      skipped=$((skipped + 1))
      continue
    fi
  fi

  log="$LOG_DIR/${c}.log"
  start=$(date +%s)
  printf '[%d/%d] %s ... ' "$n" "$TOTAL" "$c"

  "$SCRIPT_DIR/run_agentic_od.sh" "$c" > "$log" 2>&1
  rc=$?
  dur=$(( $(date +%s) - start ))

  verdict="$(grep -h '^Final verdict:' "$log" 2>/dev/null | tail -1 | sed 's/^Final verdict: *//')"
  [[ -n "$verdict" ]] || verdict="(no verdict; rc=$rc)"

  if [[ $rc -eq 0 ]]; then
    passed=$((passed + 1))
    echo "done in ${dur}s - $verdict"
  else
    failed=$((failed + 1))
    FAILED_LIST+=("$c")
    echo "EXIT $rc after ${dur}s - $verdict  (see $log)"
  fi
done

echo "=========================================="
echo "[batch] finished: $(date '+%Y-%m-%d %H:%M:%S')"
echo "[batch] ran ok=$passed  nonzero-exit=$failed  skipped=$skipped  of $TOTAL"
if (( ${#FAILED_LIST[@]} )); then
  echo "[batch] nonzero exit for:"
  for c in "${FAILED_LIST[@]}"; do echo "   $c"; done
fi
echo "[batch] per-container logs: $LOG_DIR"
echo "[batch] results appended to: $REPO_ROOT/Complete_Containers_Summary.csv"
echo "=========================================="
