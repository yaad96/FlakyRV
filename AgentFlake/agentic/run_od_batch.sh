#!/usr/bin/env bash
# Run the 41 OD containers sequentially, one after another.
#
# Usage:
#   ./run_od_batch.sh                 # all 41
#   ./run_od_batch.sh 11 20           # containers 11..20 (1-indexed, inclusive)
#   ./run_od_batch.sh oddubbo1 ...    # named containers
#
# Environment:
#   AGENTFLAKE_PROMPT_VARIANT   generic (default here) | typed
#   SKIP_DONE=1                 skip containers that already have an archived run
#   MIN_FREE_GB=<n>             abort if free disk drops below this (default 15)
#   TIMEOUT_SECS=<n>            per-container wall-clock cap (default 1200)
#   KEEP_ZIPS=1                 keep every artefact zip (default: delete a zip
#                               once no remaining container in this run needs it)
#   BATCH_LOG_DIR               where per-container logs go
#
# Deliberately does NOT use `set -e`: one container failing must not stop the
# batch. Each container's stdout/stderr goes to its own log.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPROFLAKE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$REPROFLAKE_DIR/.." && pwd)"
CSV_FILE="$REPROFLAKE_DIR/test_config.csv"

# Without this, Python block-buffers stdout when redirected to a log file and
# the orchestrator's progress is invisible until it exits.
export PYTHONUNBUFFERED=1
export AGENTFLAKE_PROMPT_VARIANT="${AGENTFLAKE_PROMPT_VARIANT:-generic}"

MIN_FREE_GB="${MIN_FREE_GB:-15}"
TIMEOUT_SECS="${TIMEOUT_SECS:-1200}"

ALL=(
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

# --- select which containers to run -----------------------------------------
CONTAINERS=()
if (( $# == 0 )); then
  CONTAINERS=("${ALL[@]}")
elif (( $# == 2 )) && [[ "$1" =~ ^[0-9]+$ && "$2" =~ ^[0-9]+$ ]]; then
  from=$1; to=$2
  if (( from < 1 || to > ${#ALL[@]} || from > to )); then
    echo "ERROR: range $from..$to is outside 1..${#ALL[@]}"; exit 1
  fi
  for (( i = from - 1; i <= to - 1; i++ )); do CONTAINERS+=("${ALL[$i]}"); done
  echo "[batch] range $from..$to"
else
  CONTAINERS=("$@")
fi

TOTAL=${#CONTAINERS[@]}

zip_of()  { awk -F, -v c="$1" '$2==c {print $3; exit}' "$CSV_FILE"; }
free_gb() { df -BG --output=avail "$REPO_ROOT" 2>/dev/null | tail -1 | tr -dc '0-9'; }

# Ctrl-C must abort the whole batch, not just the container in flight.
trap 'echo; echo "[batch] interrupted - stopping."; exit 130' INT TERM

KEY_FILE="$REPO_ROOT/.anthropic_api_key"
if [[ ! -s "$KEY_FILE" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: no LLM API key available. Paste your Anthropic key into $KEY_FILE"
  exit 1
fi

avail=$(free_gb)
if [[ -n "$avail" ]] && (( avail < MIN_FREE_GB )); then
  echo "ERROR: only ${avail}G free on $REPO_ROOT; need >= ${MIN_FREE_GB}G."
  echo "       Free space or lower MIN_FREE_GB. Refusing to start: a full disk"
  echo "       silently voids every container instead of failing once."
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="${BATCH_LOG_DIR:-$REPO_ROOT/batch_logs/od_${AGENTFLAKE_PROMPT_VARIANT}_${STAMP}}"
mkdir -p "$LOG_DIR"

echo "=========================================="
echo "[batch] OD batch: $TOTAL containers"
echo "[batch] prompt variant : $AGENTFLAKE_PROMPT_VARIANT"
echo "[batch] free disk      : ${avail}G (min ${MIN_FREE_GB}G)"
echo "[batch] timeout/cont   : ${TIMEOUT_SECS}s"
echo "[batch] logs           : $LOG_DIR"
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

  avail=$(free_gb)
  if [[ -n "$avail" ]] && (( avail < MIN_FREE_GB )); then
    echo "[$n/$TOTAL] ABORT: only ${avail}G free (min ${MIN_FREE_GB}G)."
    echo "[batch] stopping so the remaining containers are not voided."
    break
  fi

  log="$LOG_DIR/${c}.log"
  start=$(date +%s)
  printf '[%d/%d] %s (%sG free) ... ' "$n" "$TOTAL" "$c" "$avail"

  timeout --signal=INT --kill-after=60 "$TIMEOUT_SECS" \
    "$SCRIPT_DIR/run_agentic_od.sh" "$c" > "$log" 2>&1
  rc=$?
  dur=$(( $(date +%s) - start ))

  # timeout leaves the docker container and any child processes behind.
  if (( rc == 124 || rc == 137 )); then
    docker rm -f "tm_${c//[^a-zA-Z0-9]/_}" > /dev/null 2>&1
    pkill -f "agentic_orchestrator.py $c" 2>/dev/null
  fi

  verdict="$(grep -h '^Final verdict:' "$log" 2>/dev/null | tail -1 | sed 's/^Final verdict: *//')"
  [[ -n "$verdict" ]] || verdict="(no verdict; rc=$rc)"

  if [[ $rc -eq 0 ]]; then
    passed=$((passed + 1))
    echo "done in ${dur}s - $verdict"
  elif (( rc == 124 )); then
    failed=$((failed + 1)); FAILED_LIST+=("$c (timeout)")
    echo "TIMEOUT after ${dur}s  (see $log)"
  else
    failed=$((failed + 1)); FAILED_LIST+=("$c")
    echo "EXIT $rc after ${dur}s - $verdict  (see $log)"
  fi

  # Drop this container's zip only when no container still to come needs it.
  # 17 zips cover the 41 containers (wildflynaming3a83b7b.zip alone serves 10),
  # so deleting per-container would force large re-downloads.
  if [[ "${KEEP_ZIPS:-0}" != "1" ]]; then
    z="$(zip_of "$c")"
    if [[ -n "$z" && -f "$REPROFLAKE_DIR/data/${z}.zip" ]]; then
      still_needed=0
      for (( j = i + 1; j < TOTAL; j++ )); do
        [[ "$(zip_of "${CONTAINERS[$j]}")" == "$z" ]] && { still_needed=1; break; }
      done
      if (( still_needed == 0 )); then
        rm -f "$REPROFLAKE_DIR/data/${z}.zip"
        echo "         (removed ${z}.zip - no remaining container needs it)"
      fi
    fi
  fi
done

echo "=========================================="
echo "[batch] finished: $(date '+%Y-%m-%d %H:%M:%S')"
echo "[batch] ran ok=$passed  failed=$failed  skipped=$skipped  of $TOTAL"
if (( ${#FAILED_LIST[@]} )); then
  echo "[batch] failures:"
  for c in "${FAILED_LIST[@]}"; do echo "   $c"; done
fi
echo "[batch] free disk now: $(free_gb)G"
echo "[batch] per-container logs: $LOG_DIR"
echo "[batch] results appended to: $REPO_ROOT/Complete_Containers_Summary.csv"
echo "=========================================="
