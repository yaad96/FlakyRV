**ReproFlake \+ Valg**

**Run Guide**

# **Overview**

This guide explains how to run a flaky test from the ReproFlake dataset — with and without Valg (TraceMOP) — and how to compare the resulting RV traces to identify flakiness signals.

**Note:** Tests with test\_type nio are **not supported** by this pipeline. Skip any CSV row where test\_type is nio. All other types (od, britle, id, td, unclassified) are supported.

# **Step 0 — Parse the CSV Row**

Open test\_config.csv. Each row has the following columns:

| Column | Description |
| :---- | :---- |
| test\_type | Type of flaky test: od, td, id, britle, raft, nio |
| result\_container | Unique name for this test run |
| zip | ZIP filename (stored in data/) |
| module | Maven module to test |
| polluter/state setter | Polluter test (OD tests only) |
| flaky\_test | The victim/flaky test |
| iterations | Suggested number of iterations |
| java | Java version required: 8, 11, or 17 |
| url | Download URL if ZIP is not present locally |

# **Step 1 — Download and Extract the ZIP**

Run in PowerShell from f:\\Valg\\ReproFlake\\:

| $name \= "\<result\_container from csv\>" $url  \= "\<url from csv\>" $zip  \= "data\\$name.zip" $dest \= "data\\$name"   Invoke-WebRequest \-Uri $url \-OutFile $zip Expand-Archive \-Path $zip \-DestinationPath $dest \-Force   \# Flatten if there is an extra nested folder $inner \= Get-ChildItem $dest \-Directory | Select-Object \-First 1 if ($inner) {     Move-Item "$($inner.FullName)\\\*" $dest \-Force     Remove-Item $inner.FullName } |
| :---- |

After extraction, data\\\<result\_container\>\\ should contain:

| Flaky/          source code (flaky version) Flakym2/        Maven cache Fixed.patch     patch to create Fixed version |
| :---- |

# **Step 2 — Start the Docker Container**

Pick the correct image based on test\_type and java version:

| test\_type | Image |
| :---- | :---- |
| od (java=8) | flaky\_base\_jdk8\_od\_cov |
| od (java=11) | flaky\_base\_jdk11 |
| britle | flaky\_base\_jdk8\_od\_cov |
| td | flaky\_base\_jdk8 |
| id (java=8) | flaky\_base\_jdk8 |
| id (java=11) | flaky\_base\_jdk11 |
| id (java=17) | flaky\_base\_jdk17 |
| unclassified | flaky\_base\_jdk8 |
| nio | Not supported — excluded from analysis |

| $name  \= "\<result\_container from csv\>" $base  \= "f:\\Valg\\ReproFlake\\data\\$name" $image \= "flaky\_base\_jdk8\_od\_cov" $cname \= "my\_test"   docker rm \-f $cname 2\>$null docker run \-d \--name $cname \`   \--mount type=bind,source="$base\\Flaky",target=/app/source \`   \--mount type=bind,source="$base\\Flakym2\\.m2",target=/root/.m2 \`   $image tail \-f /dev/null |
| :---- |

# **Step 3 — Run Flaky Order WITHOUT Valg (N iterations)**

Edit the variables at the top, save as run\_flaky.ps1, and run with .\\run\_flaky.ps1:

| \# \============================================================ \# CONFIGURE THESE VALUES FROM THE CSV ROW \# \============================================================ $CONTAINER\_NAME \= "my\_test" $MODULE         \= "\<module from csv\>" $POLLUTER       \= "\<polluter from csv\>" $VICTIM         \= "\<flaky\_test from csv\>" $ITERATIONS     \= 20 \# \============================================================   $script \= @" \#\!/bin/bash cd /app/source MODULE="$MODULE" POLLUTER="$POLLUTER" VICTIM="$VICTIM" MVNOPTS="-DfailIfNoTests=false \-Dgpg.skip=true \-Dcheckstyle.skip \-Drat.skip \-Denforcer.skip \-Dmaven.javadoc.skip"   mvn clean install \-DskipTests \-pl "\`$MODULE" \-am \`$MVNOPTS   pass=0; fail=0; err=0 for i in \`$(seq 1 $ITERATIONS); do     result=\`$(mvn \-pl "\`$MODULE" test \-Dsurefire.runOrder=testorder \\       \-Dtest="\`$POLLUTER,\`$VICTIM" \`$MVNOPTS 2\>&1 | grep "Tests run:" | tail \-1)     f=\`$(echo "\`$result" | awk \-F'Failures: ' '{print \`$2}' | awk \-F',' '{print \`$1}')     e=\`$(echo "\`$result" | awk \-F'Errors: ' '{print \`$2}' | awk \-F',' '{print \`$1}')     if \[\[ "\`$f" \== "0" && "\`$e" \== "0" \]\]; then ((pass++))     elif \[\[ "\`$e" \-gt "0" \]\]; then ((err++))     else ((fail++)); fi done printf "Summary:\\nPasses: %d\\nFailures: %d\\nErrors: %d\\n" \`$pass \`$fail \`$err | tee /app/source/flaky-summary.txt "@   $tmp \= "$env:TEMP\\run\_flaky.sh" \[System.IO.File\]::WriteAllText($tmp, $script.Replace("\`r\`n", "\`n")) docker cp $tmp ${CONTAINER\_NAME}:/tmp/run\_flaky.sh docker exec $CONTAINER\_NAME bash /tmp/run\_flaky.sh |
| :---- |

**Expected results by test type:**

**OD/brittle:** Failures or Errors: 20 (or close to it). If 0, the polluter is not reproducing — check test order.

**ID:** Failures may be 0 in 20 runs — the flakiness is non-deterministic. If the CSV has a nondexSeed value (e.g., 933178), the test requires NonDex to trigger. In that case, you may still see 20 passes without NonDex. This is expected — proceed to Step 6 where TraceMOP will capture the behavioral traces regardless.

**TD:** Similar to OD but without a known polluter. Failures depend on what other tests ran previously.

# **Step 4 — Run Clean Order WITHOUT Valg (N iterations)**

Edit the variables at the top, save as run\_clean.ps1, and run with .\\run\_clean.ps1:

| \# \============================================================ \# CONFIGURE THESE VALUES FROM THE CSV ROW \# \============================================================ $CONTAINER\_NAME \= "my\_test" $MODULE         \= "\<module from csv\>" $VICTIM         \= "\<flaky\_test from csv\>" $ITERATIONS     \= 20 \# \============================================================   $script \= @" \#\!/bin/bash cd /app/source MODULE="$MODULE" VICTIM="$VICTIM" MVNOPTS="-DfailIfNoTests=false \-Dgpg.skip=true \-Dcheckstyle.skip \-Drat.skip \-Denforcer.skip \-Dmaven.javadoc.skip"   pass=0; fail=0; err=0 for i in \`$(seq 1 $ITERATIONS); do     result=\`$(mvn \-pl "\`$MODULE" test \\       \-Dtest="\`$VICTIM" \`$MVNOPTS 2\>&1 | grep "Tests run:" | tail \-1)     f=\`$(echo "\`$result" | awk \-F'Failures: ' '{print \`$2}' | awk \-F',' '{print \`$1}')     e=\`$(echo "\`$result" | awk \-F'Errors: ' '{print \`$2}' | awk \-F',' '{print \`$1}')     if \[\[ "\`$f" \== "0" && "\`$e" \== "0" \]\]; then ((pass++))     elif \[\[ "\`$e" \-gt "0" \]\]; then ((err++))     else ((fail++)); fi done printf "Summary:\\nPasses: %d\\nFailures: %d\\nErrors: %d\\n" \`$pass \`$fail \`$err | tee /app/source/clean-summary.txt "@   $tmp \= "$env:TEMP\\run\_clean.sh" \[System.IO.File\]::WriteAllText($tmp, $script.Replace("\`r\`n", "\`n")) docker cp $tmp ${CONTAINER\_NAME}:/tmp/run\_clean.sh docker exec $CONTAINER\_NAME bash /tmp/run\_clean.sh |
| :---- |

**Expected result:** Passes: 20

# **Step 5 — Copy TraceMOP (one-time per container)**

| docker cp "f:\\Valg\\experiments\\tracemop.jar" my\_test:/tmp/tracemop.jar |
| :---- |

# **Step 6 — Run WITH Valg (TraceMOP)**

## **Generic version (any container)**

Edit the variables at the top, save as run\_valg\_generic.ps1, and run with .\\run\_valg\_generic.ps1:

| \# \============================================================ \# CONFIGURE THESE VALUES FROM THE CSV ROW \# \============================================================ $CONTAINER\_NAME \= "my\_test" $MODULE         \= "\<module from csv\>" $POLLUTER       \= "\<polluter from csv\>" $VICTIM         \= "\<flaky\_test from csv\>" $AGENT          \= "/tmp/tracemop.jar" \# \============================================================   $script \= @" \#\!/bin/bash cd /app/source MODULE="$MODULE" POLLUTER="$POLLUTER" VICTIM="$VICTIM" AGENT="$AGENT" MVNOPTS="-DfailIfNoTests=false \-Dgpg.skip=true \-Dcheckstyle.skip \-Drat.skip \-Denforcer.skip \-Dmaven.javadoc.skip"   export TRACEDB\_CONFIG\_PATH="/tmp/.trace-db.config" printf "db=memory\\ndumpDB=false\\n" \> "\`${TRACEDB\_CONFIG\_PATH}" export RVMLOGGINGLEVEL=UNIQUE export JAVA\_TOOL\_OPTIONS="-javaagent:\`${AGENT}"   echo "=== FLAKY ORDER WITH TRACEMOP \===" mkdir \-p /app/source/traces-flaky export TRACEDB\_PATH=/app/source/traces-flaky mvn \-pl "\`$MODULE" test \-Dsurefire.runOrder=testorder \\   \-Dtest="\`$POLLUTER,\`$VICTIM" \\   \`$MVNOPTS 2\>&1 | tee /app/source/tracemop-flaky.log   echo "=== CLEAN ORDER WITH TRACEMOP \===" mkdir \-p /app/source/traces-clean export TRACEDB\_PATH=/app/source/traces-clean mvn \-pl "\`$MODULE" test \\   \-Dtest="\`$VICTIM" \\   \`$MVNOPTS 2\>&1 | tee /app/source/tracemop-clean.log   unset JAVA\_TOOL\_OPTIONS "@   $tmp \= "$env:TEMP\\run\_valg.sh" \[System.IO.File\]::WriteAllText($tmp, $script.Replace("\`r\`n", "\`n")) docker cp $tmp ${CONTAINER\_NAME}:/tmp/run\_valg.sh docker exec $CONTAINER\_NAME bash /tmp/run\_valg.sh |
| :---- |

# **Step 6 (Updated) — Run WITH Valg (TraceMOP) — Maven Extension Approach**

**WARNING: The old Step 6 above is broken.** It uses JAVA\_TOOL\_OPTIONS which loads TraceMOP into the Maven parent process, not the forked Surefire JVM where tests execute. This produces traces containing only Maven infrastructure classes (Guice, Plexus, Aether) — zero project code. **Use this updated Step 6 instead.**

## **One-Time Setup Per Container**

### ***Build the Maven Extension***

| $CONTAINER\_NAME \= "\<your\_container\_name\>"   docker exec $CONTAINER\_NAME mkdir \-p /tmp/ext-build docker cp "f:\\Valg\\scripts\\javamop-extension\\pom.xml" ${CONTAINER\_NAME}:/tmp/ext-build/pom.xml docker cp "f:\\Valg\\scripts\\javamop-extension\\src" ${CONTAINER\_NAME}:/tmp/ext-build/src docker exec $CONTAINER\_NAME bash \-c "cd /tmp/ext-build && mvn package \-DskipTests \-q" |
| :---- |

### ***Install the Agent into Maven Local Repo***

| docker cp "f:\\Valg\\experiments\\tracemop.jar" ${CONTAINER\_NAME}:/tmp/tracemop.jar   docker exec $CONTAINER\_NAME bash \-c "cd /app/source && mvn install:install-file \-Dfile=/tmp/tracemop.jar \-DgroupId=javamop-agent \-DartifactId=javamop-agent \-Dversion=1.0 \-Dpackaging=jar" |
| :---- |

## **Run Flaky \+ Clean Orders with TraceMOP**

**Prerequisite:** Step 3 (or Step 4\) must have run first. Step 6 uses mvn surefire:test which skips compilation — it only runs existing test classes. If the project has not been compiled yet, run mvn clean install \-DskipTests inside the container first.

Edit the variables at the top, save as run\_valg\_ext.ps1, and run with .\\run\_valg\_ext.ps1:

| \# \============================================================ \# CONFIGURE THESE VALUES FROM THE CSV ROW \# \============================================================ $CONTAINER\_NAME \= "my\_test" $MODULE         \= "\<module from csv\>" $POLLUTER       \= "\<polluter from csv\>" $VICTIM         \= "\<flaky\_test from csv\>" \# \============================================================   $script \= @" \#\!/bin/bash cd /app/source MODULE="$MODULE" POLLUTER="$POLLUTER" VICTIM="$VICTIM" EXT="/tmp/ext-build/target/javamop-extension-1.0.jar" MVNOPTS="-DfailIfNoTests=false \-Dgpg.skip=true \-Dcheckstyle.skip \-Drat.skip \-Denforcer.skip \-Dmaven.javadoc.skip"   export TRACEDB\_CONFIG\_PATH="/tmp/.trace-db.config" printf "db=memory\\ndumpDB=false\\n" \> "\`${TRACEDB\_CONFIG\_PATH}" export RVMLOGGINGLEVEL=UNIQUE   echo "=== FLAKY ORDER WITH TRACEMOP \===" rm \-rf /app/source/traces-flaky mkdir \-p /app/source/traces-flaky export TRACEDB\_PATH=/app/source/traces-flaky   if \[ \-n "\`$POLLUTER" \]; then   \# OD/brittle: check if custom Surefire exists for testorder support   CUSTOM\_SUREFIRE="/root/.m2/repository/org/apache/maven/plugins/maven-surefire-plugin/3.0.0-M8-SNAPSHOT"   if \[ \-d "\`$CUSTOM\_SUREFIRE" \]; then     export SUREFIRE\_VERSION=3.0.0-M8-SNAPSHOT     RUN\_ORDER="testorder"   else     unset SUREFIRE\_VERSION     RUN\_ORDER="alphabetical"   fi   mvn surefire:test \\     \-Dmaven.ext.class.path="\`${EXT}" \\     \-pl "\`$MODULE" \-Dsurefire.runOrder=\`$RUN\_ORDER \\     \-Dtest="\`$POLLUTER,\`$VICTIM" \\     \`$MVNOPTS 2\>&1 | tee /app/source/tracemop-flaky.log else   \# ID/TD/unclassified: let extension use its default Surefire   unset SUREFIRE\_VERSION   mvn surefire:test \\     \-Dmaven.ext.class.path="\`${EXT}" \\     \-pl "\`$MODULE" \\     \-Dtest="\`$VICTIM" \\     \`$MVNOPTS 2\>&1 | tee /app/source/tracemop-flaky.log fi   echo "=== CLEAN ORDER WITH TRACEMOP \===" rm \-rf /app/source/traces-clean mkdir \-p /app/source/traces-clean export TRACEDB\_PATH=/app/source/traces-clean   mvn surefire:test \\   \-Dmaven.ext.class.path="\`${EXT}" \\   \-pl "\`$MODULE" \\   \-Dtest="\`$VICTIM" \\   \`$MVNOPTS 2\>&1 | tee /app/source/tracemop-clean.log "@   $tmp \= "$env:TEMP\\run\_valg\_ext.sh" \[System.IO.File\]::WriteAllText($tmp, $script.Replace("\`r\`n", "\`n")) docker cp $tmp ${CONTAINER\_NAME}:/tmp/run\_valg\_ext.sh docker exec $CONTAINER\_NAME bash /tmp/run\_valg\_ext.sh |
| :---- |

## **What Changed vs Old Step 6**

| Old (broken) | New (verified) |
| :---- | :---- |
| export JAVA\_TOOL\_OPTIONS="-javaagent:..." | Maven extension via \-Dmaven.ext.class.path= |
| Agent loads in Maven parent process | Agent loads in Surefire forked test JVM |
| mvn test | mvn surefire:test |
| Traces contain only infrastructure code | Traces contain project code |
| No Surefire version control | OD/brittle: auto-detects custom Surefire — uses testorder if available, falls back to alphabetical. ID/TD: extension uses default Surefire (3.1.2) |

## **How It Handles Each Test Type**

| Type | POLLUTER variable | Flaky run | Clean run |
| :---- | :---- | :---- | :---- |
| od | Set from CSV | testorder if custom Surefire available, else alphabetical | Victim alone |
| britle | Set from CSV | testorder if custom Surefire available, else alphabetical | Victim alone |
| id | Empty | Victim alone (failing conditions) | Victim alone (passing conditions) |
| td | Empty | Victim alone (failing conditions) | Victim alone (passing conditions) |
| unclassified | Empty | Victim alone (failing conditions) | Victim alone (passing conditions) |

The script checks if \[ \-n "$POLLUTER" \] — if polluter is set, it runs both tests with testorder; if empty, it runs victim only.

## **Verify Project Code Is Instrumented**

| docker exec $CONTAINER\_NAME bash \-c "echo 'Project: '$(grep \-c '\<project\_package\>' /app/source/traces-flaky/locations.txt 2\>/dev/null || echo 0); echo 'Infrastructure: '$(grep \-c 'org.codehaus' /app/source/traces-flaky/locations.txt 2\>/dev/null || echo 0)" |
| :---- |

Expected: Project \> 0, Infrastructure \= 0\.

## **Troubleshooting**

| Symptom | Cause | Fix |
| :---- | :---- | :---- |
| No \[TraceMOP\] lines in output | Agent not loading | Verify: docker exec $CONTAINER\_NAME ls /tmp/ext-build/target/javamop-extension-1.0.jar |
| There's no RunOrder with the name testorder | Custom Surefire not in this container | Script auto-detects and falls back to alphabetical. If alphabetical gives wrong order, verify polluter class sorts before victim |
| locations.txt has only infrastructure classes | Using old JAVA\_TOOL\_OPTIONS approach | Make sure JAVA\_TOOL\_OPTIONS is unset; use extension |
| The goal you specified requires a project | install:install-file run from wrong dir | Run from /app/source: cd /app/source && mvn install:install-file ... |
| traces-flaky/ is empty | Agent JAR not in Maven local repo | Re-run mvn install:install-file step |
| maven-surefire-plugin:3.0.0-M8-SNAPSHOT could not be resolved | SUREFIRE\_VERSION set but custom Surefire not in this container's Maven repo (JDK11/17 images don't have it) | Remove export SUREFIRE\_VERSION=3.0.0-M8-SNAPSHOT or leave POLLUTER empty for non-OD tests |

# **Step 7 \-Run Order Summary**

| \# From f:\\Valg\\ReproFlake\\ in PowerShell .\\run\_flaky.ps1             \# confirm N failures .\\run\_clean.ps1             \# confirm N passes .\\run\_valg\_generic.ps1      \# collect RV traces |
| :---- |

## **Step 7 — Where Results Appear (on host)**

| f:\\Valg\\ReproFlake\\data\\\<result\_container\>\\Flaky\\ ├── flaky-summary.txt          pass/fail counts for flaky order runs ├── clean-summary.txt          pass/fail counts for clean order runs ├── traces-flaky\\ │     ├── unique-traces.txt    RV trace fingerprint of flaky run │     └── locations.txt        maps location IDs to source lines └── traces-clean\\       ├── unique-traces.txt    RV trace fingerprint of clean run       └── locations.txt |
| :---- |

Key reference file for decoding event IDs:

| f:\\Valg\\scripts\\events\_encoding\_id.txt Format: SpecName,event\_name,event\_id |
| :---- |

# **Step 8 — Compare the Traces**

## **How the comparison works**

Each line in unique-traces.txt has the format:

| 8 \[e116\~65 x 6, e117\~65, e115\~65\] |  |
| :---- | :---- |
| **Part** | **Meaning** |
| 8 | How many times this trace was seen (stripped — not important) |
| e116 | Event ID 116 — maps to a spec name in events\_encoding\_id.txt |
| \~65 | Source location ID 65 — maps to a source line in locations.txt |
| 6 | That event repeated N times consecutively at that point in the sequence (stripped- not important) |

The script strips counts and locations, then compares which specs appear in each run:

**Specs only in flaky** \= RV behaviors triggered by the polluter \= **flakiness signal**

**Specs only in clean** \= RV behaviors only present when the test passes

**Specs in both** \= noise

## **8B: Comparing Traces with TraceMop Official Script**

Documentation way: run the following after completing Step 7:

### ***CONFIGURE THESE VALUES***

| $CONTAINER\_NAME \= "\<your\_container\_name\>" $name           \= "\<result\_container from csv\>" $base           \= "f:\\Valg\\ReproFlake\\data\\$name" |
| :---- |

*NOTE: Only run docker run if container was deleted.*

*Image depends on test\_type \+ java from CSV:*

  *od          → flaky\_base\_jdk8\_od\_cov*

  *td          → flaky\_base\_jdk8*

  *id (java=8) → flaky\_base\_jdk8*

  *id (java=11)→ flaky\_base\_jdk11*

  *id (java=17)→ flaky\_base\_jdk17*

| $image \= "flaky\_base\_jdk8\_od\_cov" |
| :---- |

### ***If Container Was Deleted, Restart It First***

| docker run \-d \--name $CONTAINER\_NAME \`   \--mount type=bind,source="$base\\Flaky",target=/app/source \`   \--mount type=bind,source="$base\\Flakym2\\.m2",target=/root/.m2 \`   $image tail \-f /dev/null |
| :---- |

### ***One-Time Setup: Download \+ Copy Scripts into Container***

| Invoke-WebRequest \-Uri "https://raw.githubusercontent.com/SoftEngResearch/tracemop/master/scripts/compare-traces.py" \-OutFile "$env:TEMP\\compare-traces-official.py"   docker cp "$env:TEMP\\compare-traces-official.py" ${CONTAINER\_NAME}:/tmp/compare-traces-official.py   docker cp "f:\\Valg\\scripts\\events\_encoding\_id.txt" ${CONTAINER\_NAME}:/tmp/events\_encoding\_id.txt   docker cp "f:\\Valg\\ReproFlake\\patch\_compare.py" ${CONTAINER\_NAME}:/tmp/patch\_compare.py   docker exec ${CONTAINER\_NAME} python3 /tmp/patch\_compare.py |
| :---- |

### ***Run Official Comparison***

| docker exec \-w /tmp ${CONTAINER\_NAME} python3 compare-traces-official.py \`   /app/source/traces-flaky \`   /app/source/traces-clean \`   false |
| :---- |

### ***Run Location Analysis and Save Output***

| docker cp "f:\\Valg\\ReproFlake\\analyze\_locations.py" ${CONTAINER\_NAME}:/tmp/analyze\_locations.py   docker exec ${CONTAINER\_NAME} python3 /tmp/analyze\_locations.py \`   | Tee-Object \-FilePath "f:\\Valg\\ReproFlake\\data\\$name\\step\_8\_B.txt" |
| :---- |

## **Step 8C: Full Trace Comparison with TraceMOP Official Script**

Run the following after completing Step 7\. This compares the full event trace sequences between flaky and clean runs — not just locations.

### **CONFIGURE THESE VALUES**

| $CONTAINER\_NAME \= "\<your\_container\_name\>" $name           \= "\<result\_container from csv\>" $base           \= "f:\\Valg\\ReproFlake\\data\\$name" |
| :---- |

### **If Container Was Deleted, Restart It First**

\# Image depends on test\_type \+ java from CSV:

\#   od          → flaky\_base\_jdk8\_od\_cov

\#   td          → flaky\_base\_jdk8

\#   id (java=8) → flaky\_base\_jdk8

\#   id (java=11)→ flaky\_base\_jdk11

\#   id (java=17)→ flaky\_base\_jdk17

| $image \= "flaky\_base\_jdk8\_od\_cov"   docker run \-d \--name $CONTAINER\_NAME \`   \--mount type=bind,source="$base\\Flaky",target=/app/source \`   \--mount type=bind,source="$base\\Flakym2\\.m2",target=/root/.m2 \`   $image tail \-f /dev/null |
| :---- |

### **One-Time Setup: Download \+ Copy Scripts into Container**

| Invoke-WebRequest \-Uri "https://raw.githubusercontent.com/SoftEngResearch/tracemop/master/scripts/compare-traces.py" \-OutFile "$env:TEMP\\compare-traces-official.py" docker cp "$env:TEMP\\compare-traces-official.py" ${CONTAINER\_NAME}:/tmp/compare-traces-official.py docker cp "f:\\Valg\\scripts\\events\_encoding\_id.txt" ${CONTAINER\_NAME}:/tmp/events\_encoding\_id.txt docker cp "f:\\Valg\\ReproFlake\\patch\_compare.py" ${CONTAINER\_NAME}:/tmp/patch\_compare.py docker exec $CONTAINER\_NAME python3 /tmp/patch\_compare.py |
| :---- |

### **Run Official Trace Comparison and Save Output**

| docker exec \-w /tmp $CONTAINER\_NAME python3 compare-traces-official.py \`   /app/source/traces-flaky \`   /app/source/traces-clean \`   false \`   | Tee-Object \-FilePath "$base\\step\_8\_C\_official.txt" |
| :---- |

### **Run Location Analysis and Save Output**

| docker cp "f:\\Valg\\ReproFlake\\analyze\_locations.py" ${CONTAINER\_NAME}:/tmp/analyze\_locations.py docker exec $CONTAINER\_NAME python3 /tmp/analyze\_locations.py \`   | Tee-Object \-FilePath "$base\\step\_8\_C\_naive.txt" |
| :---- |

### **How to Read the Output**

step\_8\_C\_Official.txt contains three types of lines:

| Line prefix | Meaning |
| :---- | :---- |
| ERROR: Locations don't match | The two runs touched different code locations (listed in the set below) |
| ERROR: \[trace\] is in actual (N times) but not expected | Trace only in flaky run |
| ERROR: \[trace\] is in expected (N times) but not actual | Trace only in clean run |
| WARNING: \[trace\]'s frequency is X in expected, but is Y in actual | Same trace, different count |

## **Quick summary commands:**

| \# Count flaky-only traces (Get-Content "$base\\step\_8\_C\_Official.txt" | Select-String "is in actual.\*but not expected").Count   \# Count clean-only traces (Get-Content "$base\\step\_8\_C\_Official.txt" | Select-String "is in expected.\*but not actual").Count   \# Count frequency differences (Get-Content "$base\\step\_8\_C\_Official.txt" | Select-String "frequency is").Count |
| :---- |

### **Interpreting Results**

Flaky-only traces \> 0 → RV behaviors triggered by the polluter \= flakiness signal

Clean-only traces \> 0 → RV behaviors only present when test passes (clean run exercises more/different code)

Frequency diffs \> 0 → Same behavior in both runs but at different rates (subtler signal)

If all three are 0 → TraceMOP detected no behavioral differences between runs

### **Comparison Between Step 8B and 8C**

## **Step 8B — Location Analysis (analyze\_locations.py)**

Reads only locations.txt from each run

Compares which code locations (Java method \+ line number) were instrumented

Output: set diff of locations (only-in-flaky, only-in-clean, in-both)

Does not read unique-traces.txt — ignores what actually happened at those locations

Does not use events\_encoding\_id.txt — has no concept of RV specs or events

Fast (\< 1 second)

**What it answers:** *"Did the flaky run touch different code than the clean run?"*

## **Step 8C — Full Trace Comparison (compare-traces.py official)**

Reads locations.txt, unique-traces.txt, and events\_encoding\_id.txt

Reconciles location IDs between runs (same code location can get different numeric IDs in each run — the script maps them to a common namespace before comparing)

Compares full event trace sequences — the ordered sequence of RV events each monitor instance observed

Reports three kinds of differences:

  Traces that only exist in one run (behavioral patterns unique to flaky or clean)

  Traces that exist in both but at different frequencies

  Location mismatches (code touched by only one run)

Slower (seconds to minutes depending on trace count)

**What it answers:** *"Did the flaky run behave differently than the clean run — and exactly how?"*

## **When Each Matters**

| Scenario | 8B result | 8C result | What happened |
| :---- | :---- | :---- | :---- |
| Strong OD flakiness (e.g., WildFly) | 440 flaky-only locations | 4,158 flaky-only traces, 407 frequency diffs | Polluter causes entirely different code paths — both steps catch it |
| Subtle state flakiness (e.g., shardingsphere-elasticjob) | 0 flaky-only locations | 8,185 trace differences | Same code is touched, but executed differently — only 8C catches it |
| No RV difference | 0 / 0 | 0 / 0 / 0 | TraceMOP found no behavioral difference between runs |

## **Recommended Workflow**

Run 8B first — it takes 1 second and gives an immediate yes/no signal. Then always run 8C regardless of 8B's result, because 8C catches cases that 8B misses entirely (like shardingsphere-elasticjob where all locations were identical but trace patterns differed).

**8B is the quick screen. 8C is the real analysis. Never skip 8C.**

# **Comparison Between Step 8A and 8B**

## **Step 8A — My Approach (Spec-Level Comparison)**

Uses PowerShell Compare-Object or custom compare\_traces.py

Compares which spec names appear in each run (yes/no)

Fast, simple, works on host

Misses frequency differences (missed elastic-job)

## **Step 8B — Official Script Approach (Sequence \+ Frequency \+ Code-Path)**

Downloads and runs compare-traces-official.py

Reconciles location IDs between runs

Compares full trace sequences \+ how many times each appeared

Then analyze\_locations.py shows which source code locations differ

More thorough, catches both code-path and state-value flakiness

## **Recommended Workflow**

I'd run 8A first — it's quick and gives you an immediate yes/no signal. If 8A shows differences, I already have my answer. If 8A shows nothing (like elastic-job), I move to 8B for deeper analysis.

**So the decision flow is:**

**Step 8A → specs only in flaky \> 0?**

    **YES** → code-path flakiness detected, done

    **NO**  → run Step 8B for frequency/location analysis

# **Step 9 — Generate LLM-Ready Trace Summary**

After completing Step 8C, run the summary script to produce a concise, decoded trace diff that can be fed to an LLM for patch generation.

### **Why This Step Exists**

The raw step\_8\_C\_official.txt is not suitable for LLM consumption:

It can be thousands of lines (e.g., 4,887 lines for ORMLite)

Event IDs like e151\~391 are opaque

Most of the file is noise (specs that appear in both runs)

The summary script decodes event IDs to RV spec names and produces a \~40-line structured summary with only the actionable signal.

### **Run the Script**

From PowerShell in f:\\Valg\\ReproFlake\\:

| py \-3 generate\_llm\_summary.py \<result\_container from csv\> |
| :---- |

### **What It Reads**

| File | Source |
| :---- | :---- |
| data\\\<name\>\\step\_8\_C\_official.txt | Step 8C output (handles UTF-8 and UTF-16) |
| scripts\\events\_encoding\_id.txt | Decodes event IDs → RV spec names |
| test\_config.csv | Test metadata (type, polluter, victim, module, java) |

### **What It Produces**

Output saved to data/\<result\_container\>/llm\_trace\_summary.txt.

| Section | Content |
| :---- | :---- |
| Metadata | Test type, polluter (if OD/brittle), victim, module, java |
| Raw counts | Flaky-only traces, clean-only traces, frequency diffs, location mismatches |
| Signal assessment | STRONG / MODERATE / SUBTLE / NO signal |
| RV specs only in flaky run | The flakiness signal — decoded spec names with event names |
| RV specs only in clean run | Behaviors only present when test passes |
| RV specs in both runs | Noise |
| Frequency-only specs | Same pattern, different occurrence counts |
| Interpretation guide | Context for the LLM, adapted to test type (OD vs ID/TD) |

### **Test Type Handling**

| Type | Behavior |
| :---- | :---- |
| od, britle | References "polluter" in signal assessment and interpretation |
| id, td, unclassified | References "non-determinism" / "execution conditions" instead |
| nio | Not supported (excluded from analysis) |

### **How to Use the Output**

Feed llm\_trace\_summary.txt to the LLM along with:

1\. The flaky test source code (victim)

2\. The polluter test source code (for OD/brittle types)

3\. The code under test snippet

# **Step 10 — Assemble Full LLM Context for Patch Generation**

After completing Step 9, run the assembly script to produce a single structured context file that combines RV trace analysis, test source code, failure output, and production code — ready for LLM consumption.

### **Why This Step Exists**

The llm\_trace\_summary.txt from Step 9 contains decoded RV specs, but the LLM also needs:

The polluter and victim source code (to understand what shared state is corrupted)

The failure stack trace (to see exactly where the crash happens)

The production code referenced in the stack trace (to see where to patch)

A structured task instruction (to guide the LLM toward a correct fix)

This script assembles all of that into one file.

### **Run the Script**

From PowerShell in f:\\Valg\\ReproFlake\\:

| py \-3 assemble\_llm\_context.py \<result\_container from csv\> |
| :---- |

### **What It Reads**

| File | Source |
| :---- | :---- |
| test\_config.csv | Test metadata (type, polluter, victim, module, java) |
| data\\\<n\>\\Flaky\\flaky-summary.txt | Pass/fail counts for flaky run |
| data\\\<n\>\\Flaky\\clean-summary.txt | Pass/fail counts for clean run |
| data\\\<n\>\\llm\_trace\_summary.txt | Step 9 output (decoded RV trace analysis) |
| data\\\<n\>\\Flaky\\tracemop-flaky.log | Failure stack trace extraction |
| data\\\<n\>\\Flaky\\src\\ | Polluter, victim, and production source code |

### **What It Produces**

Output saved to data/\<result\_container\>/llm\_context.txt.

| Section | Content |
| :---- | :---- |
| Test Metadata | Type, polluter (if OD/brittle), victim, module, java |
| Test Results | Pass/fail counts for flaky and clean runs |
| RV Trace Analysis | Full llm\_trace\_summary.txt embedded (specs, signal, counts) |
| Failure Output | Exception \+ stack trace from the failing run |
| Polluter Source Code | Extracted method (OD/brittle only) |
| Victim Source Code | Extracted method (OD) or full class (ID/TD/unclassified) |
| Production Code | Methods from src/main/java that appear in the stack trace |
| Task | Fix instructions adapted to test type, requests two outputs |

### **Test Type Handling**

| Type | Polluter section | Victim section | Task instruction |
| :---- | :---- | :---- | :---- |
| od, britle | Method extracted | Method extracted | "polluter corrupts shared state" — suggests @AfterEach cleanup |
| td | Skipped | Full class | "test-dependency, polluter unknown" — suggests @BeforeEach / self-contained fixtures |
| id, unclassified | Skipped | Full class | "non-deterministic" — suggests mocking, synchronization, deterministic alternatives |
| nio | Not supported | — | — |

### **What the LLM Is Asked to Produce**

The task section requests two outputs:

**OUTPUT A — PATCH:** A unified diff (applicable via patch \-p1) with paths relative to the project root.

**OUTPUT B — DEVELOPER GUIDE:**

1\. Root cause: plain English explanation of what causes the flakiness

2\. Fix description: which file(s) to edit, what to add/remove, and why

3\. Fixed code snippet(s): exact modified method(s), ready to copy-paste

Output A is for automated evaluation (compare against Fixed.patch). Output B is for a developer who wants to understand and apply the fix manually.

### **Prompting Technique**

The assembled prompt uses **zero-shot structured prompting with evidence grounding**:

**Zero-shot** — no examples of previous fixes are included

**Structured** — labeled sections guide the LLM through: metadata → evidence → code → task

**Evidence-grounded** — the RV trace analysis provides runtime behavioral evidence that narrows the LLM's search space (e.g., ThreadSafe specs → look for shared mutable state)

### **How to Use the Output**

**Option 1 — Paste into any LLM web app:** Copy the contents of llm\_context.txt into ChatGPT, Claude, Gemini, etc. The LLM will return Output A (patch) and Output B (developer guide).

**Option 2 — API call (recommended for research):**

| import anthropic   client \= anthropic.Anthropic() context \= open("data/\<name\>/llm\_context.txt").read()   response \= client.messages.create(     model="claude-sonnet-4-20250514",     max\_tokens=4096,     temperature=0,     messages=\[{"role": "user", "content": context}\] )   with open("data/\<name\>/llm\_generated.patch", "w") as f:     f.write(response.content\[0\].text) |
| :---- |

