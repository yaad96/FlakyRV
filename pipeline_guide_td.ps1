# =============================================================================
# GUIDE PIPELINE: Generalized TD Flaky Test
# =============================================================================
# For TD (test-dependency) tests where FlakyCodeChange.patch and
# FixedCodeChange.patch exist in the ZIP.
#
# Approach:
#   - FlakyCodeChange = Flaky + FlakyCodeChange.patch -> guaranteed FAIL
#   - FixedCodeChange = Flaky + FixedCodeChange.patch -> guaranteed PASS
#   - TraceMOP on FlakyCodeChange -> traces-flaky
#   - TraceMOP on FixedCodeChange -> traces-clean
#   - Compare traces -> LLM context
#
# Why this differs from OD:
#   - No polluter (TD flakiness is timing/state dependent, polluter unknown)
#   - Flaky folder alone may NOT reproduce the failure
#   - FlakyCodeChange.patch introduces the timing bug deterministically
#   - Two separate containers needed (different source code)
#
# Usage:
#   1. Fill in STEP 0 from a test_config.csv row (test_type=td)
#   2. Run: .\pipeline_guide_td.ps1
# =============================================================================

$ErrorActionPreference = "Continue"

# =============================================================================
# STEP 0 -- Config from CSV row
# =============================================================================
$TEST_TYPE  = "td"
$NAME       = "CURATOR-681"
$ZIP_NAME   = "CURATOR-681"
$MODULE     = "curator-recipes"
$VICTIM     = "org.apache.curator.framework.recipes.locks.TestInterProcessMutex#testReentrantSingleLock"
$ITERATIONS = 3
$JAVA_VER   = "8"
$URL        = "https://zenodo.org/records/18474558/files/CURATOR-681.zip"


# TD uses flaky_base_jdk8 (no custom Surefire needed -- no testorder)
if ($JAVA_VER -eq "11") {
    $IMAGE      = "flaky_base_jdk11"
    $DOCKERFILE = "Dockerfile"
} else {
    $IMAGE      = "flaky_base_jdk8"
    $DOCKERFILE = "Dockerfile"
}

$REPROFLAKE = "f:\Valg\ReproFlake"
$VALG       = "f:\Valg"
$BASE       = "$REPROFLAKE\data\$NAME"
$ZIP_PATH   = "$REPROFLAKE\data\$ZIP_NAME.zip"

# Validate
if ($NAME -match "^COLLECTIONS" -or $VICTIM -match "EmptyProperties") {
    Write-Host "WARNING: Config still has COLLECTIONS-812 values. Did you update STEP 0?" -ForegroundColor Yellow
    Write-Host 'Press Enter to continue anyway, or Ctrl+C to abort and edit.'
    Read-Host
}

Write-Host "===== STEP 0: Config =====" -ForegroundColor Cyan
Write-Host "  Test type:  $TEST_TYPE"
Write-Host "  Name:       $NAME"
Write-Host "  ZIP:        $ZIP_NAME"
Write-Host "  Module:     $MODULE"
Write-Host "  Victim:     $VICTIM"
Write-Host "  Java:       $JAVA_VER"
Write-Host "  Image:      $IMAGE"
Write-Host "  NOTE: TD test - no polluter. Using FlakyCodeChange/FixedCodeChange patches."

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

# Verify patches exist
if (!(Test-Path "$BASE\FlakyCodeChange.patch")) { throw "FlakyCodeChange.patch not found in $BASE" }
if (!(Test-Path "$BASE\FixedCodeChange.patch")) { throw "FixedCodeChange.patch not found in $BASE" }
Write-Host "Patches verified: FlakyCodeChange.patch, FixedCodeChange.patch"

# =============================================================================
# STEP 2 -- Build image and create patched folders
# =============================================================================
Write-Host "`n===== STEP 2: Build Image + Create Patched Folders =====" -ForegroundColor Cyan

Write-Host "Building image: $IMAGE from $DOCKERFILE ..."
docker build -t $IMAGE -f "$REPROFLAKE\$DOCKERFILE" $REPROFLAKE
if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }

# Create FlakyCodeChange and FixedCodeChange using a temp container
Write-Host "Creating patched folders..."
docker rm -f prep_container 2>&1 | Out-Null
docker run -d --name prep_container `
  --mount "type=bind,source=$BASE,target=/data" `
  $IMAGE tail -f /dev/null
if ($LASTEXITCODE -ne 0) { throw "Failed to start prep container" }

$prepScript = @'
#!/bin/bash
cd /data

# FlakyCodeChange = Flaky + FlakyCodeChange.patch (guaranteed FAIL)
if [ ! -f FlakyCodeChange/pom.xml ]; then
    echo "Creating FlakyCodeChange/ from Flaky/ + FlakyCodeChange.patch"
    rm -rf FlakyCodeChange
    cp -r Flaky FlakyCodeChange
    patch -p1 -d FlakyCodeChange < FlakyCodeChange.patch || echo "WARN: patch had issues"
else
    echo "FlakyCodeChange/ already has content, skipping"
fi

# FixedCodeChange = Flaky + FixedCodeChange.patch (guaranteed PASS)
if [ ! -f FixedCodeChange/pom.xml ]; then
    echo "Creating FixedCodeChange/ from Flaky/ + FixedCodeChange.patch"
    rm -rf FixedCodeChange
    cp -r Flaky FixedCodeChange
    patch -p1 -d FixedCodeChange < FixedCodeChange.patch || echo "WARN: patch had issues"
else
    echo "FixedCodeChange/ already has content, skipping"
fi

echo ""
echo "=== Verify ==="
for d in Flaky FlakyCodeChange FixedCodeChange; do
    if [ -f "$d/pom.xml" ]; then
        echo "  $d: OK"
    else
        echo "  $d: MISSING or EMPTY"
    fi
done
'@
$prepTmp = "$env:TEMP\prep_td_folders.sh"
[System.IO.File]::WriteAllText($prepTmp, $prepScript.Replace("`r`n", "`n"))
docker cp $prepTmp prep_container:/tmp/prep_td_folders.sh
docker exec prep_container bash /tmp/prep_td_folders.sh

docker rm -f prep_container
Write-Host "Step 2 complete."

# =============================================================================
# STEP 3 -- Run FlakyCodeChange (should FAIL)
# =============================================================================
Write-Host "`n===== STEP 3: Run FlakyCodeChange [expect: FAIL] =====" -ForegroundColor Cyan

$CNAME_FLAKY = "td_flaky"
docker rm -f $CNAME_FLAKY 2>&1 | Out-Null
docker run -d --name $CNAME_FLAKY `
  --mount "type=bind,source=$BASE\FlakyCodeChange,target=/app/source" `
  --mount "type=bind,source=$BASE\Flakym2\.m2,target=/root/.m2" `
  $IMAGE tail -f /dev/null

$step3Script = @"
#!/bin/bash
cd /app/source
MODULE="$MODULE"
VICTIM="$VICTIM"
MVNOPTS="-DfailIfNoTests=false -Dgpg.skip=true -Dcheckstyle.skip -Drat.skip -Denforcer.skip -Dmaven.javadoc.skip"

mvn clean install -DskipTests -pl "`$MODULE" -am `$MVNOPTS

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
printf "Summary:\nPasses: %d\nFailures: %d\nErrors: %d\n" `$pass `$fail `$err | tee /app/source/flaky-summary.txt
"@

$tmp = "$env:TEMP\run_td_step3.sh"
[System.IO.File]::WriteAllText($tmp, $step3Script.Replace("`r`n", "`n"))
docker cp $tmp ${CNAME_FLAKY}:/tmp/run_step3.sh
docker exec $CNAME_FLAKY bash /tmp/run_step3.sh

# Bridge: copy flaky-summary into Flaky/ for assemble_llm_context.py
Copy-Item "$BASE\FlakyCodeChange\flaky-summary.txt" "$BASE\Flaky\flaky-summary.txt" -Force -ErrorAction SilentlyContinue

Write-Host "`nStep 3 complete."

# =============================================================================
# STEP 4 -- Run FixedCodeChange (should PASS)
# =============================================================================
Write-Host "`n===== STEP 4: Run FixedCodeChange [expect: PASS] =====" -ForegroundColor Cyan

$CNAME_CLEAN = "td_clean"
docker rm -f $CNAME_CLEAN 2>&1 | Out-Null
docker run -d --name $CNAME_CLEAN `
  --mount "type=bind,source=$BASE\FixedCodeChange,target=/app/source" `
  --mount "type=bind,source=$BASE\Flakym2\.m2,target=/root/.m2" `
  $IMAGE tail -f /dev/null

$step4Script = @"
#!/bin/bash
cd /app/source
MODULE="$MODULE"
VICTIM="$VICTIM"
MVNOPTS="-DfailIfNoTests=false -Dgpg.skip=true -Dcheckstyle.skip -Drat.skip -Denforcer.skip -Dmaven.javadoc.skip"

mvn clean install -DskipTests -pl "`$MODULE" -am `$MVNOPTS

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

$tmp = "$env:TEMP\run_td_step4.sh"
[System.IO.File]::WriteAllText($tmp, $step4Script.Replace("`r`n", "`n"))
docker cp $tmp ${CNAME_CLEAN}:/tmp/run_step4.sh
docker exec $CNAME_CLEAN bash /tmp/run_step4.sh

# Bridge: copy clean-summary into Flaky/
Copy-Item "$BASE\FixedCodeChange\clean-summary.txt" "$BASE\Flaky\clean-summary.txt" -Force -ErrorAction SilentlyContinue

docker stop $CNAME_CLEAN | Out-Null
docker rm $CNAME_CLEAN | Out-Null

Write-Host "`nStep 4 complete."
Write-Host 'Press Enter to continue to Step 6 [TraceMOP], or Ctrl+C to abort.'
Read-Host

# =============================================================================
# STEP 5 + 6 -- TraceMOP on FlakyCodeChange and FixedCodeChange
# =============================================================================
Write-Host "`n===== STEP 5+6: TraceMOP Traces =====" -ForegroundColor Cyan

$TRACE_RUNS = @(
    @{
        Dir      = "FlakyCodeChange"
        CName    = "td_trace_flaky"
        TraceDir = "traces-flaky"
        LogFile  = "tracemop-flaky.log"
    }
    @{
        Dir      = "FixedCodeChange"
        CName    = "td_trace_clean"
        TraceDir = "traces-clean"
        LogFile  = "tracemop-clean.log"
    }
)

foreach ($tr in $TRACE_RUNS) {
    $dir      = $tr.Dir
    $cname    = $tr.CName
    $traceDir = $tr.TraceDir
    $logFile  = $tr.LogFile
    $src_path = "$BASE\$dir"
    $m2_path  = "$BASE\Flakym2\.m2"

    Write-Host "`n--- TraceMOP: $dir -> $traceDir ---" -ForegroundColor Yellow

    docker rm -f $cname 2>&1 | Out-Null
    docker run -d --name $cname `
      --mount "type=bind,source=$src_path,target=/app/source" `
      --mount "type=bind,source=$m2_path,target=/root/.m2" `
      $IMAGE tail -f /dev/null

    Write-Host "  Building Maven extension..."
    docker exec $cname mkdir -p /tmp/ext-build
    docker cp "$VALG\scripts\javamop-extension\pom.xml" ${cname}:/tmp/ext-build/pom.xml
    docker cp "$VALG\scripts\javamop-extension\src"     ${cname}:/tmp/ext-build/src
    docker exec $cname bash -c "cd /tmp/ext-build && mvn package -DskipTests -q"
    if ($LASTEXITCODE -ne 0) { throw "Maven extension build failed in $cname" }

    Write-Host "  Installing TraceMOP agent..."
    docker cp "$VALG\experiments\tracemop.jar" ${cname}:/tmp/tracemop.jar
    docker exec $cname bash -c "cd /app/source && mvn install:install-file -Dfile=/tmp/tracemop.jar -DgroupId=javamop-agent -DartifactId=javamop-agent -Dversion=1.0 -Dpackaging=jar -q"
    if ($LASTEXITCODE -ne 0) { throw "TraceMOP agent install failed in $cname" }

    Write-Host "  Compiling project..."
    docker exec $cname bash -c "cd /app/source && mvn clean install -DskipTests -pl `"$MODULE`" -am -DfailIfNoTests=false -Dgpg.skip=true -Dcheckstyle.skip -Drat.skip -Denforcer.skip -Dmaven.javadoc.skip -Ddependency-check.skip=true -q"

    Write-Host "  Running TraceMOP [$dir]..."

    $script = @"
#!/bin/bash
cd /app/source

MODULE="$MODULE"
VICTIM="$VICTIM"
EXT="/tmp/ext-build/target/javamop-extension-1.0.jar"
MVNOPTS="-DfailIfNoTests=false -Dgpg.skip=true -Dcheckstyle.skip -Drat.skip -Denforcer.skip -Dmaven.javadoc.skip -Ddependency-check.skip=true"

export TRACEDB_CONFIG_PATH="/tmp/.trace-db.config"
printf "db=memory\ndumpDB=false\n" > "`${TRACEDB_CONFIG_PATH}"
export RVMLOGGINGLEVEL=UNIQUE

rm -rf /app/source/$traceDir
mkdir -p /app/source/$traceDir
export TRACEDB_PATH=/app/source/$traceDir

# TD: no testorder, no polluter, no custom Surefire
unset SUREFIRE_VERSION

mvn surefire:test \
  -Dmaven.ext.class.path="`${EXT}" \
  -pl "`$MODULE" \
  -Dtest="`$VICTIM" \
  `$MVNOPTS 2>&1 | tee /app/source/$logFile
"@

    $tmp = "$env:TEMP\run_td_trace_$($tr.CName).sh"
    [System.IO.File]::WriteAllText($tmp, $script.Replace("`r`n", "`n"))
    docker cp $tmp ${cname}:/tmp/run_trace.sh
    docker exec $cname bash /tmp/run_trace.sh

    Write-Host "  Verifying instrumentation..."
    docker exec $cname bash -c "echo 'Trace files:' && ls -la /app/source/$traceDir/ 2>/dev/null && echo '' && echo 'Lines in unique-traces.txt:' && wc -l /app/source/$traceDir/unique-traces.txt 2>/dev/null && echo 'Lines in locations.txt:' && wc -l /app/source/$traceDir/locations.txt 2>/dev/null"

    Write-Host "  Done."
}

# Bridge: copy traces and logs into Flaky/ for analyze_locations.py and assemble_llm_context.py
Write-Host "`nBridging trace files into Flaky/..."
# Copy traces-flaky from FlakyCodeChange into Flaky
if (Test-Path "$BASE\FlakyCodeChange\traces-flaky") {
    if (Test-Path "$BASE\Flaky\traces-flaky") { Remove-Item "$BASE\Flaky\traces-flaky" -Recurse -Force }
    Copy-Item "$BASE\FlakyCodeChange\traces-flaky" "$BASE\Flaky\traces-flaky" -Recurse -Force
}
# Copy traces-clean from FixedCodeChange into Flaky
if (Test-Path "$BASE\FixedCodeChange\traces-clean") {
    if (Test-Path "$BASE\Flaky\traces-clean") { Remove-Item "$BASE\Flaky\traces-clean" -Recurse -Force }
    Copy-Item "$BASE\FixedCodeChange\traces-clean" "$BASE\Flaky\traces-clean" -Recurse -Force
}
# Copy tracemop logs into Flaky
Copy-Item "$BASE\FlakyCodeChange\tracemop-flaky.log" "$BASE\Flaky\tracemop-flaky.log" -Force -ErrorAction SilentlyContinue
Copy-Item "$BASE\FixedCodeChange\tracemop-clean.log" "$BASE\Flaky\tracemop-clean.log" -Force -ErrorAction SilentlyContinue

Write-Host "Step 6 complete."

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

# Use the td_trace_flaky container (still running, has traces-flaky)
# Copy traces-clean into it for comparison
$FLAKY_CN = "td_trace_flaky"

docker exec $FLAKY_CN bash -c "rm -rf /app/source/traces-clean"
docker cp "$BASE\Flaky\traces-clean" ${FLAKY_CN}:/app/source/traces-clean
docker exec $FLAKY_CN bash -c "echo 'traces-flaky:' && ls /app/source/traces-flaky/ | head -3 && echo 'traces-clean:' && ls /app/source/traces-clean/ | head -3"

$comparePy = "$env:TEMP\compare-traces-official.py"
if (!(Test-Path $comparePy)) {
    Invoke-WebRequest -Uri "https://raw.githubusercontent.com/SoftEngResearch/tracemop/master/scripts/compare-traces.py" -OutFile $comparePy
}

docker cp $comparePy                                   ${FLAKY_CN}:/tmp/compare-traces-official.py
docker cp "$VALG\scripts\events_encoding_id.txt"       ${FLAKY_CN}:/tmp/events_encoding_id.txt
docker cp "$REPROFLAKE\patch_compare.py"               ${FLAKY_CN}:/tmp/patch_compare.py
docker cp "$REPROFLAKE\analyze_locations.py"           ${FLAKY_CN}:/tmp/analyze_locations.py

docker exec $FLAKY_CN python3 /tmp/patch_compare.py

docker exec $FLAKY_CN python3 /tmp/analyze_locations.py `
  | Tee-Object -FilePath "$BASE\step_8_B.txt"

Write-Host "Saved: $BASE\step_8_B.txt"

# =============================================================================
# STEP 8C -- Full Trace Comparison
# =============================================================================
Write-Host "`n===== STEP 8C: Full Trace Comparison =====" -ForegroundColor Cyan

docker exec -w /tmp $FLAKY_CN python3 compare-traces-official.py `
  /app/source/traces-flaky `
  /app/source/traces-clean `
  false `
  | Tee-Object -FilePath "$BASE\step_8_C_official.txt"

docker exec $FLAKY_CN python3 /tmp/analyze_locations.py `
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
docker rm -f td_flaky td_clean td_trace_flaky td_trace_clean 2>&1 | Out-Null
Write-Host "Containers removed."

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
