#!/usr/bin/env bash
# Run the 41 ID containers sequentially, one after another.
#
# Usage:
#   ./run_id_batch.sh                 # all 41
#   ./run_id_batch.sh 11 20           # containers 11..20 (1-indexed, inclusive)
#   ./run_id_batch.sh oddubbo1 ...    # named containers
#
# Environment:
#   AGENTFLAKE_PROMPT_VARIANT   generic (default here) | typed
#   SKIP_DONE=1                 skip containers that already have an archived run
#   MIN_FREE_GB=<n>             abort if free disk drops below this (default 15)
#   TIMEOUT_SECS=<n>            per-container wall-clock cap (default 4200)
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
TIMEOUT_SECS="${TIMEOUT_SECS:-4200}"

ALL=(
  commonslang1163e17testReflectionHashCodeExcludeFields
  jsonschemacore7dbae50multipleSchemaDepViolation
  scimonoscimonoclient7487ec5testCreateDefaultIdentityFilter3
  fastjson97ee7b6test_for_issue5
  apollojavaapolloopenapi5344bc4testFindItemsByNamespace
  crane4jcrane4jcoreb73311aget
  graylog2servergraylog2server27269f2summarizeUsersReturnsListOfUsersIfCurrentUserIsNull
  ednjava2d37e22testPrettyPrinting
  elideelidecore5c39308testHiddenFields
  castlejavaa5e9ef9minimalContextAsJson
  idservicecombea50142swagger
  idflink1c06b74btable
  idhbaseb162d1aserver
  idhivestnd1
  idjbpmcase1
  dubbodubbocommon690d397testGetAllDeclaredAnnotations
  ecoschemacatalogstore95ee43btestCorrectRemoveOfVersionWithNoOriginKey
  bladebladecoree925deatestAddStatics
  avrolangjavaavro7fd098atestRecord
  furyfurycore68ca4bftestTraverseExpression
  SCB-2692
  karatekaratecore935f0a8testBeanConversion
  OpenRefinemaina68ba3bserializeListFacet
  oktahookssdkjavahooks9187787createUserTest
  shenyushenyuadmin6bfb86btestBuildHandle1
  graylog2servergraylog2server036bdb5serializePrefixOnly
  graylog2servergraylog2serverf169d54serializeInteger
  dubbodubbocommon83c466etestGetMetaAnnotations
  elideelidecore80439b6writeSingleIncluded
  ecoschemacatalogstore95ee43btestRemove22
  castlejavaa5e9ef9fullBuilderJson6
  bladebladecoreaa32ce9testRouteMatcher
  bytebuddybytebuddydepe997263testNonGenericParameter
  cloudstackpluginsnetworkelementsopendaylightadec811gsonNeutronPortMarshalingTest1
  castlejavaa5e9ef9jsonSerialized18
  crane4jcrane4jcore679c3f8process
  cloudstackpluginsnetworkelementstungstendf4cd2alistTungstenNetworkTest
  adyenjavaapilibraryb8a8de5testPaymentsRequestWithXidAndCavv
  nacoscommon2c5c85ctestGetMap3
  jerseymediajsonjackson1b99237testDisabledModule
  nifinificommonsnifirecord7823156testAliasConflictingAliasValues
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
LOG_DIR="${BATCH_LOG_DIR:-$REPO_ROOT/batch_logs/id_${AGENTFLAKE_PROMPT_VARIANT}_${STAMP}}"
mkdir -p "$LOG_DIR"

echo "=========================================="
echo "[batch] ID batch: $TOTAL containers"
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
    "$SCRIPT_DIR/run_agentic_id.sh" "$c" > "$log" 2>&1
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
  # 38 zips cover the 41 ID containers, so sharing is rare (castle-java=.=a5e9ef9
  # serves 3) and most zips are dropped right after their container finishes.
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
