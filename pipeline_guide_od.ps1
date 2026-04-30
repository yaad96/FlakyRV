# =============================================================================
# GUIDE PIPELINE: Generalized OD Flaky Test
# =============================================================================
# Strictly follows ReproFlake_Valg_Run_Guide_v2.docx.md, Steps 0-10.
# Self-contained for any OD test -- just fill in STEP 0 config.
#
# Usage:
#   1. Fill in the STEP 0 variables from a test_config.csv row (test_type=od)
#   2. Run: .\pipeline_guide_od.ps1
#
# Supports: od, britle (both use polluter + victim)
# Does NOT support: td, id, unclassified, nio
# =============================================================================

$ErrorActionPreference = "Continue"

# =============================================================================
# STEP 0 -- Config from CSV row
# =============================================================================
$TEST_TYPE  = "od"
$NAME       = "dubbodubborpcdubborpcdubbo5ea6b331"
$ZIP_NAME   = "dubbodubborpcdubborpcdubbo5ea6b33"
$MODULE     = "dubbo-rpc/dubbo-rpc-dubbo"
$POLLUTER   = "org.apache.dubbo.rpc.protocol.dubbo.DubboProtocolTest#testDubboProtocol"
$VICTIM     = "org.apache.dubbo.rpc.protocol.dubbo.DubboProtocolTest#testDubboProtocolWithMina"
$ITERATIONS = 3
$JAVA_VER   = "8"
$URL        = "https://zenodo.org/records/18474558/files/dubbodubborpcdubborpcdubbo5ea6b33.zip"


# Image selection based on java version (Guide Step 2 table)
if ($JAVA_VER -eq "11") {
    $IMAGE      = "flaky_base_jdk11"
    $DOCKERFILE = "Dockerfile"
} else {
    $IMAGE      = "flaky_base_jdk8_od_cov"
    $DOCKERFILE = "Dockerfile.od"
}

$REPROFLAKE = "f:\Valg\ReproFlake"
$VALG       = "f:\Valg"
$BASE       = "$REPROFLAKE\data\$NAME"
$ZIP_PATH   = "$REPROFLAKE\data\$ZIP_NAME.zip"
$CNAME      = "my_test"

# Validate config
if ($NAME -match "^marineapi" -or $POLLUTER -match "SentenceFactory") {
    Write-Host "WARNING: Config still has marineapi values. Did you update STEP 0?" -ForegroundColor Yellow
    Write-Host 'Press Enter to continue anyway, or Ctrl+C to abort and edit.'
    Read-Host
}

Write-Host "===== STEP 0: Config =====" -ForegroundColor Cyan
Write-Host "  Test type:  $TEST_TYPE"
Write-Host "  Name:       $NAME"
Write-Host "  ZIP:        $ZIP_NAME"
Write-Host "  Module:     $MODULE"
Write-Host "  Polluter:   $POLLUTER"
Write-Host "  Victim:     $VICTIM"
Write-Host "  Java:       $JAVA_VER"
Write-Host "  Image:      $IMAGE"

# =============================================================================
# STEP 1 -- Download and Extract the ZIP
# =============================================================================
Write-Host "`n===== STEP 1: Download and Extract =====" -ForegroundColor Cyan

if (!(Test-Path $ZIP_PATH)) {
    Write-Host "Downloading from $URL ..."
    Invoke-WebRequest -Uri $URL -OutFile $ZIP_PATH
    Write-Host "Downloaded: $ZIP_PATH"
} else {
    Write-Host "ZIP already exists: $ZIP_PATH"
}

if (!(Test-Path "$BASE\Flaky")) {
    Write-Host "Extracting..."
    if (!(Test-Path $BASE)) { New-Item -ItemType Directory -Path $BASE | Out-Null }
    Expand-Archive -Path $ZIP_PATH -DestinationPath $BASE -Force
    $inner = Get-ChildItem $BASE -Directory | Where-Object { $_.Name -eq $ZIP_NAME -or $_.Name -eq $NAME } | Select-Object -First 1
    if ($inner -and $inner.Name -ne "Flaky") {
        Move-Item "$($inner.FullName)\*" $BASE -Force
        Remove-Item $inner.FullName -Recurse -Force
    }
    Write-Host "Extracted to: $BASE"
} else {
    Write-Host "Already extracted: $BASE\Flaky"
}

# =============================================================================
# STEP 2 -- Start the Docker Container
# =============================================================================
Write-Host "`n===== STEP 2: Start Docker Container =====" -ForegroundColor Cyan

Write-Host "Building image: $IMAGE from $DOCKERFILE ..."
docker build -t $IMAGE -f "$REPROFLAKE\$DOCKERFILE" $REPROFLAKE
if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }

docker rm -f $CNAME 2>&1 | Out-Null
docker run -d --name $CNAME `
  --mount "type=bind,source=$BASE\Flaky,target=/app/source" `
  --mount "type=bind,source=$BASE\Flakym2\.m2,target=/root/.m2" `
  $IMAGE tail -f /dev/null
if ($LASTEXITCODE -ne 0) { throw "Failed to start container" }
Write-Host "Container $CNAME started."

# =============================================================================
# STEP 3 -- Run Flaky Order WITHOUT Valg
# =============================================================================
Write-Host "`n===== STEP 3: Flaky Order - no TraceMOP =====" -ForegroundColor Cyan

$step3Script = @"
#!/bin/bash
cd /app/source
MODULE="$MODULE"
POLLUTER="$POLLUTER"
VICTIM="$VICTIM"
MVNOPTS="-DfailIfNoTests=false -Dgpg.skip=true -Dcheckstyle.skip -Drat.skip -Denforcer.skip -Dmaven.javadoc.skip"

mvn clean install -DskipTests -pl "`$MODULE" -am `$MVNOPTS

pass=0; fail=0; err=0
for i in `$(seq 1 $ITERATIONS); do
    result=`$(mvn -pl "`$MODULE" test -Dsurefire.runOrder=testorder \
      -Dtest="`$POLLUTER,`$VICTIM" `$MVNOPTS 2>&1 | grep "Tests run:" | tail -1)
    f=`$(echo "`$result" | awk -F'Failures: ' '{print `$2}' | awk -F',' '{print `$1}')
    e=`$(echo "`$result" | awk -F'Errors: ' '{print `$2}' | awk -F',' '{print `$1}')
    if [[ "`$f" == "0" && "`$e" == "0" ]]; then ((pass++))
    elif [[ "`$e" -gt "0" ]]; then ((err++))
    else ((fail++)); fi
    echo "Round `$i: F=`$f E=`$e"
done
printf "Summary:\nPasses: %d\nFailures: %d\nErrors: %d\n" `$pass `$fail `$err | tee /app/source/flaky-summary.txt
"@

$tmp = "$env:TEMP\run_step3.sh"
[System.IO.File]::WriteAllText($tmp, $step3Script.Replace("`r`n", "`n"))
docker cp $tmp ${CNAME}:/tmp/run_step3.sh
docker exec $CNAME bash /tmp/run_step3.sh

Write-Host "`nStep 3 complete."

# =============================================================================
# STEP 4 -- Run Clean Order WITHOUT Valg
# =============================================================================
Write-Host "`n===== STEP 4: Clean Order - no TraceMOP =====" -ForegroundColor Cyan

$step4Script = @"
#!/bin/bash
cd /app/source
MODULE="$MODULE"
VICTIM="$VICTIM"
MVNOPTS="-DfailIfNoTests=false -Dgpg.skip=true -Dcheckstyle.skip -Drat.skip -Denforcer.skip -Dmaven.javadoc.skip"

pass=0; fail=0; err=0
for i in `$(seq 1 $ITERATIONS); do
    result=`$(mvn -pl "`$MODULE" test \
      -Dtest="`$VICTIM" `$MVNOPTS 2>&1 | grep "Tests run:" | tail -1)
    f=`$(echo "`$result" | awk -F'Failures: ' '{print `$2}' | awk -F',' '{print `$1}')
    e=`$(echo "`$result" | awk -F'Errors: ' '{print `$2}' | awk -F',' '{print `$1}')
    if [[ "`$f" == "0" && "`$e" == "0" ]]; then ((pass++))
    elif [[ "`$e" -gt "0" ]]; then ((err++))
    else ((fail++)); fi
    echo "Round `$i: F=`$f E=`$e"
done
printf "Summary:\nPasses: %d\nFailures: %d\nErrors: %d\n" `$pass `$fail `$err | tee /app/source/clean-summary.txt
"@

$tmp = "$env:TEMP\run_step4.sh"
[System.IO.File]::WriteAllText($tmp, $step4Script.Replace("`r`n", "`n"))
docker cp $tmp ${CNAME}:/tmp/run_step4.sh
docker exec $CNAME bash /tmp/run_step4.sh

Write-Host "`nStep 4 complete."

# =============================================================================
# STEP 5 -- Copy TraceMOP
# =============================================================================
Write-Host "`n===== STEP 5: Copy TraceMOP =====" -ForegroundColor Cyan

docker cp "$VALG\experiments\tracemop.jar" ${CNAME}:/tmp/tracemop.jar
Write-Host "TraceMOP JAR copied."

# =============================================================================
# STEP 6 (Updated) -- Run WITH Valg -- Maven Extension Approach
# =============================================================================
Write-Host "`n===== STEP 6: TraceMOP Traces =====" -ForegroundColor Cyan

Write-Host "Building Maven extension..."
docker exec $CNAME mkdir -p /tmp/ext-build
docker cp "$VALG\scripts\javamop-extension\pom.xml" ${CNAME}:/tmp/ext-build/pom.xml
docker cp "$VALG\scripts\javamop-extension\src"     ${CNAME}:/tmp/ext-build/src
docker exec $CNAME bash -c "cd /tmp/ext-build && mvn package -DskipTests -q"
if ($LASTEXITCODE -ne 0) { throw "Maven extension build failed" }

Write-Host "Installing TraceMOP agent into Maven local repo..."
docker exec $CNAME bash -c "cd /app/source && mvn install:install-file -Dfile=/tmp/tracemop.jar -DgroupId=javamop-agent -DartifactId=javamop-agent -Dversion=1.0 -Dpackaging=jar"
if ($LASTEXITCODE -ne 0) { throw "TraceMOP agent install failed" }

Write-Host "Running TraceMOP traces..."

$step6Script = @"
#!/bin/bash
cd /app/source
MODULE="$MODULE"
POLLUTER="$POLLUTER"
VICTIM="$VICTIM"
EXT="/tmp/ext-build/target/javamop-extension-1.0.jar"
MVNOPTS="-DfailIfNoTests=false -Dgpg.skip=true -Dcheckstyle.skip -Drat.skip -Denforcer.skip -Dmaven.javadoc.skip"

export TRACEDB_CONFIG_PATH="/tmp/.trace-db.config"
printf "db=memory\ndumpDB=false\n" > "`${TRACEDB_CONFIG_PATH}"
export RVMLOGGINGLEVEL=UNIQUE

echo "=== FLAKY ORDER WITH TRACEMOP ==="
rm -rf /app/source/traces-flaky
mkdir -p /app/source/traces-flaky
export TRACEDB_PATH=/app/source/traces-flaky

if [ -n "`$POLLUTER" ]; then
  CUSTOM_SUREFIRE="/root/.m2/repository/org/apache/maven/plugins/maven-surefire-plugin/3.0.0-M8-SNAPSHOT"
  if [ -d "`$CUSTOM_SUREFIRE" ]; then
    export SUREFIRE_VERSION=3.0.0-M8-SNAPSHOT
    RUN_ORDER="testorder"
  else
    unset SUREFIRE_VERSION
    RUN_ORDER="alphabetical"
  fi
  mvn surefire:test \
    -Dmaven.ext.class.path="`${EXT}" \
    -pl "`$MODULE" -Dsurefire.runOrder=`$RUN_ORDER \
    -Dtest="`$POLLUTER,`$VICTIM" \
    `$MVNOPTS 2>&1 | tee /app/source/tracemop-flaky.log
else
  unset SUREFIRE_VERSION
  mvn surefire:test \
    -Dmaven.ext.class.path="`${EXT}" \
    -pl "`$MODULE" \
    -Dtest="`$VICTIM" \
    `$MVNOPTS 2>&1 | tee /app/source/tracemop-flaky.log
fi

echo "=== CLEAN ORDER WITH TRACEMOP ==="
rm -rf /app/source/traces-clean
mkdir -p /app/source/traces-clean
export TRACEDB_PATH=/app/source/traces-clean

# Unset custom Surefire -- clean run is victim alone, no testorder needed
unset SUREFIRE_VERSION

mvn surefire:test \
  -Dmaven.ext.class.path="`${EXT}" \
  -pl "`$MODULE" \
  -Dtest="`$VICTIM" \
  `$MVNOPTS 2>&1 | tee /app/source/tracemop-clean.log
"@

$tmp = "$env:TEMP\run_step6.sh"
[System.IO.File]::WriteAllText($tmp, $step6Script.Replace("`r`n", "`n"))
docker cp $tmp ${CNAME}:/tmp/run_step6.sh
docker exec $CNAME bash /tmp/run_step6.sh

Write-Host "`nVerifying instrumentation..."
docker exec $CNAME bash -c "echo 'traces-flaky:' && wc -l /app/source/traces-flaky/unique-traces.txt /app/source/traces-flaky/locations.txt 2>/dev/null; echo 'traces-clean:' && wc -l /app/source/traces-clean/unique-traces.txt /app/source/traces-clean/locations.txt 2>/dev/null"

Write-Host "`nStep 6 complete."

# =============================================================================
# STEP 7 -- Results Summary
# =============================================================================
Write-Host "`n===== STEP 7: Results =====" -ForegroundColor Cyan
Write-Host "  $BASE\Flaky\flaky-summary.txt"
Write-Host "  $BASE\Flaky\clean-summary.txt"
Write-Host "  $BASE\Flaky\traces-flaky"
Write-Host "  $BASE\Flaky\traces-clean"

# =============================================================================
# STEP 8B -- Location Analysis
# =============================================================================
Write-Host "`n===== STEP 8B: Location Analysis =====" -ForegroundColor Cyan

$comparePy = "$env:TEMP\compare-traces-official.py"
if (!(Test-Path $comparePy)) {
    Invoke-WebRequest -Uri "https://raw.githubusercontent.com/SoftEngResearch/tracemop/master/scripts/compare-traces.py" -OutFile $comparePy
}

docker cp $comparePy                                   ${CNAME}:/tmp/compare-traces-official.py
docker cp "$VALG\scripts\events_encoding_id.txt"       ${CNAME}:/tmp/events_encoding_id.txt
docker cp "$REPROFLAKE\patch_compare.py"               ${CNAME}:/tmp/patch_compare.py
docker cp "$REPROFLAKE\analyze_locations.py"           ${CNAME}:/tmp/analyze_locations.py

docker exec $CNAME python3 /tmp/patch_compare.py

docker exec $CNAME python3 /tmp/analyze_locations.py `
  | Tee-Object -FilePath "$BASE\step_8_B.txt"

Write-Host "Saved: $BASE\step_8_B.txt"

# =============================================================================
# STEP 8C -- Full Trace Comparison
# =============================================================================
Write-Host "`n===== STEP 8C: Full Trace Comparison =====" -ForegroundColor Cyan

docker exec -w /tmp $CNAME python3 compare-traces-official.py `
  /app/source/traces-flaky `
  /app/source/traces-clean `
  false `
  | Tee-Object -FilePath "$BASE\step_8_C_official.txt"

docker exec $CNAME python3 /tmp/analyze_locations.py `
  | Tee-Object -FilePath "$BASE\step_8_C_naive.txt"

Write-Host "`n--- Quick summary ---"
$official = "$BASE\step_8_C_official.txt"
if (Test-Path $official) {
    $flakyOnly = (Select-String -Path $official -Pattern "is in actual.*but not expected" | Measure-Object).Count
    $cleanOnly = (Select-String -Path $official -Pattern "is in expected.*but not actual" | Measure-Object).Count
    $freqDiffs = (Select-String -Path $official -Pattern "frequency is" | Measure-Object).Count
    Write-Host "  Flaky-only traces: $flakyOnly"
    Write-Host "  Clean-only traces: $cleanOnly"
    Write-Host "  Frequency diffs:   $freqDiffs"
}

# =============================================================================
# STEP 9 -- Generate LLM-Ready Trace Summary
# =============================================================================
Write-Host "`n===== STEP 9: LLM Trace Summary =====" -ForegroundColor Cyan

Push-Location $REPROFLAKE
py -3 generate_llm_summary.py $NAME
Pop-Location

if (Test-Path "$BASE\llm_trace_summary.txt") {
    Write-Host "Created: $BASE\llm_trace_summary.txt"
} else {
    Write-Host "WARNING: llm_trace_summary.txt not created" -ForegroundColor Yellow
}

# =============================================================================
# STEP 10 -- Assemble Full LLM Context
# =============================================================================
Write-Host "`n===== STEP 10: Assemble LLM Context =====" -ForegroundColor Cyan

Push-Location $REPROFLAKE
py -3 assemble_llm_context.py $NAME
Pop-Location

if (Test-Path "$BASE\llm_context.txt") {
    Write-Host "Created: $BASE\llm_context.txt"
} else {
    Write-Host "WARNING: llm_context.txt not created" -ForegroundColor Yellow
}

# =============================================================================
# STEP 11 -- Send Context to LLM (OpenAI GPT-4o)
# =============================================================================
Write-Host "`n===== STEP 11: Call OpenAI API =====" -ForegroundColor Cyan

Push-Location $REPROFLAKE
py -3 call_llm.py $NAME
Pop-Location

if (Test-Path "$BASE\llm_response.json") {
    Write-Host "Created: $BASE\llm_response.json"
} else {
    Write-Host "WARNING: llm_response.json not created" -ForegroundColor Yellow
}

# =============================================================================
# CLEANUP
# =============================================================================
Write-Host "`n===== Cleanup =====" -ForegroundColor Cyan
docker rm -f $CNAME 2>&1 | Out-Null
Write-Host "Container $CNAME removed."

# =============================================================================
# DONE
# =============================================================================
Write-Host "`n===== PIPELINE COMPLETE =====" -ForegroundColor Green
Write-Host ""
Write-Host "Output files:"
Write-Host "  Step 3:  $BASE\Flaky\flaky-summary.txt"
Write-Host "  Step 4:  $BASE\Flaky\clean-summary.txt"
Write-Host "  Step 6:  $BASE\Flaky\traces-flaky"
Write-Host "           $BASE\Flaky\traces-clean"
Write-Host "  Step 8B: $BASE\step_8_B.txt"
Write-Host "  Step 8C: $BASE\step_8_C_official.txt"
Write-Host "  Step 9:  $BASE\llm_trace_summary.txt"
Write-Host "  Step 10: $BASE\llm_context.txt"
Write-Host "  Step 11: $BASE\llm_response.json"
