#!/usr/bin/env bash
set -euo pipefail

RESULT_CONTAINER="${1:?Usage: $0 <result_container>}"

KEY_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/.anthropic_api_key"
if [[ ! -s "$KEY_FILE" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: no LLM API key is available. The agentic orchestrator requires one."
  echo "       Paste your Anthropic key into $KEY_FILE   (for claude-* models)"
  echo "       export OPENAI_API_KEY=sk-...                      (for gpt-* models)"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPROFLAKE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LLM_SCRIPTS="$REPROFLAKE_DIR/LLM Scripts"

DATA_DIR="$REPROFLAKE_DIR/data/$RESULT_CONTAINER"
STEPS_OUT_DIR="$DATA_DIR/Steps_Output_Files"

# Docker writes into the bind-mounted workspace as root. Hadoop/HBase tests
# create root-owned HDFS dirs there, which makes our later `cp` (step 9.5) and
# `rm -rf` (step 0 / cleanup) fail with Permission denied and abort the run.
# Hand ownership back using a throwaway root container before touching them.
reclaim_owner() {
  [[ -d "$DATA_DIR" ]] || return 0
  docker run --rm -u 0 -v "$DATA_DIR":/reclaim alpine \
    chown -R "$(id -u):$(id -g)" /reclaim > /dev/null 2>&1 || true
}

CSV="$REPROFLAKE_DIR/test_config.csv"

[[ -f "$CSV" ]] || { echo "ERROR: $CSV not found"; exit 1; }
ROW=$(awk -F',' -v rc="$RESULT_CONTAINER" '$2 == rc { print; exit }' "$CSV")
[[ -n "$ROW" ]] || { echo "ERROR: '$RESULT_CONTAINER' not in $CSV"; exit 1; }
IFS=',' read -r TEST_TYPE _RC ZIP MODULE POLLUTER VICTIM ITERATIONS CONFIG JAVA NONDEXSEED URL <<< "$ROW"

if [[ "$TEST_TYPE" != "id" ]]; then
  echo "ERROR: this script targets id only; got '$TEST_TYPE'."; exit 1
fi
if [[ -z "$NONDEXSEED" ]]; then
  echo "ERROR: ID container '$RESULT_CONTAINER' must have a NonDex seed in CSV."; exit 1
fi

case "$JAVA" in
  8)  IMAGE="flaky_base_jdk_8_id_cover_new";  DOCKERFILE="Dockerfile8.id" ;;
  11) IMAGE="flaky_base_jdk_11_id_cover_new"; DOCKERFILE="Dockerfile11.id" ;;
  17) IMAGE="flaky_base_jdk_17_id_cover_new"; DOCKERFILE="Dockerfile17.id" ;;
  *)  echo "ERROR: unsupported java=$JAVA"; exit 1 ;;
esac
PROJECT_KEY="$(printf '%s\n' "$MODULE" | tr '[:upper:]' '[:lower:]')"
if [[ "$PROJECT_KEY" == *hadoop* ]]; then
  IMAGE="flaky_base_jdk8_hadoop"
  DOCKERFILE="Dockerfile.hadoop"
fi
NONDEX_PLUGIN_VERSION="2.1.1"
if [[ "$JAVA" == "17" ]]; then
  NONDEX_PLUGIN_VERSION="2.1.7"
fi

DOCKER_PLATFORM_ARGS=()
if [[ -n "${AGENTIC_DOCKER_PLATFORM:-}" ]]; then
  DOCKER_PLATFORM_ARGS=(--platform "$AGENTIC_DOCKER_PLATFORM")
elif [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  DOCKER_PLATFORM_ARGS=(--platform linux/amd64)
fi
if ((${#DOCKER_PLATFORM_ARGS[@]})); then
  echo "[setup] Docker platform: ${DOCKER_PLATFORM_ARGS[*]}"
fi

if ((${#DOCKER_PLATFORM_ARGS[@]})) || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "[setup] Docker image '$IMAGE' not found — building from $DOCKERFILE"
  docker build "${DOCKER_PLATFORM_ARGS[@]}" -t "$IMAGE" -f "$REPROFLAKE_DIR/$DOCKERFILE" "$REPROFLAKE_DIR"
fi

CONTAINER="tm_${RESULT_CONTAINER//[^a-zA-Z0-9]/_}"
cleanup_container() {
  local rc=$?
  [[ "${KEEP_CONTAINER:-0}" == "1" ]] && return $rc
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  return $rc
}
trap cleanup_container EXIT

cat <<EOF
==========================================
[AGENTIC ID]
result_container : $RESULT_CONTAINER
victim           : $VICTIM
nondex seed      : $NONDEXSEED
java             : $JAVA  (image: $IMAGE)
container        : $CONTAINER
==========================================
EOF

if [[ "${KEEP_SOURCE:-0}" != "1" ]]; then
  if [[ -d "$DATA_DIR/Fixed" || -d "$DATA_DIR/Flaky" || -d "$DATA_DIR/Flakym2" || -d "$DATA_DIR/Flaky.pristine" || -d "$DATA_DIR/result" ]]; then
    reclaim_owner
    echo "[step 0 ] Cleaning mutated source dirs from previous run"
    rm -rf "$DATA_DIR/Fixed" "$DATA_DIR/Flaky" "$DATA_DIR/Flakym2" \
           "$DATA_DIR/Flaky.pristine" "$DATA_DIR/result"
  fi
fi

need_step1=0
for d in Flaky Flakym2; do [[ -d "$DATA_DIR/$d" ]] || need_step1=1; done
if (( need_step1 )); then
  ZIP_PATH="$REPROFLAKE_DIR/data/${ZIP}.zip"
  if [[ ! -f "$ZIP_PATH" ]]; then
    [[ -n "$URL" ]] || { echo "ERROR: $ZIP_PATH not found and URL empty"; exit 1; }
    mkdir -p "$REPROFLAKE_DIR/data"
    if   command -v curl >/dev/null; then curl -fL "$URL" -o "$ZIP_PATH"
    elif command -v wget >/dev/null; then wget "$URL" -O "$ZIP_PATH"
    else echo "ERROR: need curl or wget"; exit 1; fi
  fi
  if [[ ! -d "$DATA_DIR/Flaky" || ! -d "$DATA_DIR/Flakym2" ]]; then
    echo "[step 1a] Unzipping $ZIP_PATH"
    mkdir -p "$DATA_DIR"; unzip -o "$ZIP_PATH" -d "$DATA_DIR" >/dev/null
    if [[ -d "$DATA_DIR/$ZIP" ]]; then
      mv "$DATA_DIR/$ZIP/"* "$DATA_DIR/" 2>/dev/null || true
      rmdir "$DATA_DIR/$ZIP" 2>/dev/null || true
    fi
    # Keep the zip: step 0 wipes the extracted dirs each run, so the next
    # run re-extracts a pristine copy from here instead of re-downloading.
  fi
fi

echo "[step 2 ] Starting container '$CONTAINER'"
docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
M2_MOUNT_ARGS=()
if [[ -d "$DATA_DIR/Flakym2/.m2" ]]; then
  M2_MOUNT_ARGS=(--mount type=bind,source="$DATA_DIR/Flakym2/.m2",target=/root/.m2)
fi
docker run -d "${DOCKER_PLATFORM_ARGS[@]}" --name "$CONTAINER" \
  --mount type=bind,source="$DATA_DIR",target=/app/work \
  "${M2_MOUNT_ARGS[@]}" \
  "$IMAGE" tail -f /dev/null >/dev/null

MVNOPTS='-Ddependency-check.skip=true -Dgpg.skip=true -DfailIfNoTests=false -Dskip.installnodenpm -Dskip.npm -Dskip.yarn -Dlicense.skip -Dcheckstyle.skip -Drat.skip -Denforcer.skip -Danimal.sniffer.skip -Dmaven.javadoc.skip -Dfindbugs.skip -Dwarbucks.skip -Dmodernizer.skip -Dimpsort.skip -Dmdep.analyze.skip -Dpgpverify.skip -Dxml.skip -Dcobertura.skip=true -Dspotless.skip=true -Dspotless.check.skip=true -Dossindex.skip=true -Dmaven.bundle.plugin.skip=true -Dmaven.parallel.force=false'

NONDEX_RUNS="$ITERATIONS"
if (( NONDEX_RUNS > 10 )); then
  echo "[step 4d] capping NonDex runs at 10 (CSV says $ITERATIONS)"
  NONDEX_RUNS=10
fi

PREBUILD_SKIP_ARG="-Dmaven.test.skip=true"
PREBUILD_TARGET_ARGS="-pl '$MODULE' -am"
if [[ "$PROJECT_KEY" == *flink* ]]; then
  PREBUILD_SKIP_ARG="-DskipTests"
  PREBUILD_TARGET_ARGS="-pl flink-runtime,flink-test-utils-parent/flink-test-utils,'$MODULE' -am"
fi
echo "[step 4d] pre-build: mvn install $PREBUILD_SKIP_ARG"
docker exec "$CONTAINER" bash -c "
  set -e
  cd /app/work/Flaky
  mvn install $PREBUILD_SKIP_ARG $PREBUILD_TARGET_ARGS -q $MVNOPTS
"

echo "[step 4d] /app/work/Flaky -> /app/work/traces-fail (NonDex seed=$NONDEXSEED max-runs=$NONDEX_RUNS)"
docker exec "$CONTAINER" bash -c "
  set -e
  rm -rf /app/work/traces-fail; mkdir -p /app/work/traces-fail
  cd /app/work/Flaky
  mvn edu.illinois:nondex-maven-plugin:$NONDEX_PLUGIN_VERSION:nondex \
    -DnondexSeed=$NONDEXSEED -DnondexRuns=$NONDEX_RUNS \
    -pl '$MODULE' -Dtest='$VICTIM' \
    $MVNOPTS 2>&1 | tee /app/work/traces-fail/mvn.log || true
  grep 'nondexSeed=' /app/work/traces-fail/mvn.log \
    | sed -E 's/.*nondexSeed=([^[:space:]]+).*/\1/' \
    | awk '!seen[\$0]++' > /app/work/traces-fail/seeds.txt || true
"

echo "[sanity ] Verifying at least one NonDex iteration failed"
ITER_SUMMARIES=$(grep -E "Tests run:[[:space:]]+[0-9]+,[[:space:]]+Failures:[[:space:]]+[0-9]+,[[:space:]]+Errors:[[:space:]]+[0-9]+" \
                  "$DATA_DIR/traces-fail/mvn.log" 2>/dev/null || true)
if [[ -z "$ITER_SUMMARIES" ]]; then
  echo "ERROR: no Surefire summary in traces-fail/mvn.log"; exit 1
fi
TOTAL_TESTS=0; TOTAL_FAIL=0; TOTAL_ERR=0; FAIL_ITERS=0
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  t=$(sed -nE 's/.*Tests run:[[:space:]]+([0-9]+).*/\1/p' <<<"$line"); t=${t:-0}
  f=$(sed -nE 's/.*Failures:[[:space:]]+([0-9]+).*/\1/p'  <<<"$line"); f=${f:-0}
  e=$(sed -nE 's/.*Errors:[[:space:]]+([0-9]+).*/\1/p'    <<<"$line"); e=${e:-0}
  TOTAL_TESTS=$((TOTAL_TESTS + t)); TOTAL_FAIL=$((TOTAL_FAIL + f)); TOTAL_ERR=$((TOTAL_ERR + e))
  (( f + e >= 1 )) && FAIL_ITERS=$((FAIL_ITERS + 1))
done <<< "$ITER_SUMMARIES"
echo "[sanity ] Totals: Tests=$TOTAL_TESTS Failures=$TOTAL_FAIL Errors=$TOTAL_ERR  (failing iters=$FAIL_ITERS)"
if (( TOTAL_TESTS < 1 )); then echo "ERROR: NonDex executed 0 tests"; exit 1; fi
if (( TOTAL_FAIL + TOTAL_ERR < 1 )); then
  echo "ERROR: NonDex produced 0 failures across iterations — bug not reproduced"; exit 1
fi

mkdir -p "$STEPS_OUT_DIR"

reclaim_owner
echo "[step 9.5] snapshotting Flaky/ -> Flaky.pristine"
rm -rf "$DATA_DIR/Flaky.pristine"
cp -r "$DATA_DIR/Flaky" "$DATA_DIR/Flaky.pristine"

export NONDEXSEED NONDEX_RUNS NONDEX_PLUGIN_VERSION
echo "[agent ] launching agentic_orchestrator.py (max_iterations=${AGENTIC_MAX_ITERATIONS:-agentic_config.MAX_ITERATIONS})"
set +e
python3 "$SCRIPT_DIR/agentic_orchestrator.py" "$RESULT_CONTAINER" \
  --docker-container "$CONTAINER" \
  ${AGENTIC_MAX_ITERATIONS:+--max-iterations "$AGENTIC_MAX_ITERATIONS"} \
  ${AGENTIC_MODEL:+--model "$AGENTIC_MODEL"}
AGENT_RC=$?
set -e

if [[ "${KEEP_SOURCE:-0}" != "1" ]]; then
  rm -rf "$DATA_DIR/Flaky.pristine"
fi

echo
echo "=========================================="
echo "[AGENTIC ID] Done."
for f in run_summary.csv llm_context.txt \
         llm_response.json apply_report.json verify_after_fix.log \
         verify_after_fix.verdict agentic_conversation.json \
         agentic_iterations.jsonl; do
  if [[ -f "$STEPS_OUT_DIR/$f" ]]; then
    sz=$(wc -c < "$STEPS_OUT_DIR/$f" | tr -d ' ')
    printf "  %-30s  %s bytes\n" "$f" "$sz"
  fi
done
if [[ -f "$STEPS_OUT_DIR/verify_after_fix.verdict" ]]; then
  if [[ -f "$STEPS_OUT_DIR/run_verdict.txt" ]]; then
    echo "Final verdict: $(cat "$STEPS_OUT_DIR/run_verdict.txt")   (verification: $(cat "$STEPS_OUT_DIR/verify_after_fix.verdict" 2>/dev/null))"
  else
    echo "Final verdict: $(cat "$STEPS_OUT_DIR/verify_after_fix.verdict")"
  fi
fi
echo "=========================================="
# The run is archived under data/AGENTIC_FULL_RUNS/, so the workspace is now
# redundant scratch (Flakym2/ alone is ~150MB). Drop it once the summary above
# has been printed. Only ever fires when the orchestrator confirmed the archive.
ARCHIVED_MARKER="$STEPS_OUT_DIR/.archived_to"
if [[ "${KEEP_SOURCE:-0}" != "1" && -f "$ARCHIVED_MARKER" ]]; then
  ARCHIVED_TO="$(cat "$ARCHIVED_MARKER")"
  if [[ -d "$ARCHIVED_TO" ]]; then
    echo "[cleanup] archived to $ARCHIVED_TO - removing workspace $DATA_DIR"
    reclaim_owner
    rm -rf "$DATA_DIR" || echo "[cleanup] WARNING: could not remove $DATA_DIR"
  else
    echo "[cleanup] archive dir missing ($ARCHIVED_TO) - keeping $DATA_DIR"
  fi
fi

exit $AGENT_RC
