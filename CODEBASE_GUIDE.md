# Valg Codebase Guide

## Key Directory Map

```
Valg/
├── rv-monitor-rt/                          # RUNTIME library (executes during testing)
│   └── src/main/java/com/runtimeverification/rvmonitor/java/rt/
│       ├── table/rlagent/RLAgent.java                  # Core RL two-armed bandit agent
│       ├── table/tracefb/FbManager.java                # Trace feedback manager (ValgT)
│       ├── table/tracefb/FbTrie.java                   # Trie for trace matching
│       ├── table/tracefb/FbStatus.java                 # Feedback status tracking
│       ├── table/tracefb/FbEventNode.java              # Trie node for events
│       └── tablebase/AbstractMonitor.java              # Base monitor (traceVal, recordEvents)
│
├── rv-monitor/                             # CODE GENERATOR (compile-time)
│   └── src/main/java/com/runtimeverification/rvmonitor/java/rvj/
│       ├── Main.java                                   # Entry point, reads RVMOptions
│       ├── RVMOptions.java                             # Hyperparameter flag definitions
│       └── output/
│           ├── combinedoutputcode/
│           │   ├── CombinedOutput.java                 # Declares per-spec agent HashMaps & trace sets
│           │   └── event/itf/EventMethodBody.java      # Injects RL decision logic into generated code
│           └── monitor/BaseMonitor.java                # Trace hash computation (traceVal encoding)
│
├── javamop/                                # JavaMOP: converts .mop specs to AspectJ + .rvm
│   └── src/main/java/...
│
├── logicrepository/                        # Logic plugin core (ERE, FSM, LTL parsers)
├── plugins_logicrepository/                # Logic plugins (e.g., ptltl)
│
├── scripts/                                # Build and execution scripts
│   ├── setup.sh                            # Initial setup: clone, build, create agents
│   ├── install.sh                          # Main build script (accepts hyperparameters)
│   ├── install-javaparser.sh               # Patches JavaParser hashCode visibility
│   ├── make-agent.sh                       # Generates monitoring agent JAR
│   ├── collect_traces.sh                   # ValgT execution (traces + violations)
│   ├── not_collect_traces.sh               # ValgJ execution (violations only)
│   ├── count-traces-frequency.py           # Post-processes trace data to count unique traces
│   ├── get_junit_testcases.py              # Extracts test names from JUnit XML reports
│   ├── Dockerfile                          # Docker environment (Ubuntu 20.04, Java 8, Maven, AspectJ)
│   ├── BaseAspect_new.aj                   # Base AspectJ aspect for weaving
│   ├── events_encoding.txt                 # Event-to-integer encoding map
│   ├── events_encoding_id.txt              # Event ID encoding map
│   ├── props/                              # 160 .mop specification files (no tracking)
│   ├── props-track/                        # 162 .mop specification files (with tracking)
│   ├── javamop-extension/                  # Custom JavaMOP extension source
│   ├── mop-pom-modify/                     # Tools for modifying Maven pom.xml
│   └── resources/                          # Runtime resources (TestNameAspect.aj, etc.)
│
├── experiments/                            # Evaluation scripts and baseline JARs
│   ├── tuning.py                           # Optuna hyperparameter tuning (alpha, epsilon)
│   ├── ev_base.py                          # Baseline evaluation (JavaMOP/TraceMOP on GCP)
│   ├── ev_default.py                       # ValgJ/ValgT with default hyperparameters
│   ├── ev_optimal.py                       # ValgJ/ValgT with tuned hyperparameters
│   ├── run_tool.sh                         # Local Docker-based batch execution
│   ├── javamop.jar                         # Pre-built baseline JavaMOP agent
│   ├── tracemop.jar                        # Pre-built baseline TraceMOP agent
│   ├── rs10j.jar                           # Random sampling 10% (JavaMOP mode)
│   ├── rs50j.jar                           # Random sampling 50% (JavaMOP mode)
│   ├── rs10t.jar                           # Random sampling 10% (TraceMOP mode)
│   └── rs50t.jar                           # Random sampling 50% (TraceMOP mode)
│
├── data/                                   # Evaluation data and results
│   ├── projects.csv                        # 65 evaluation projects metadata
│   ├── rq1.csv                             # RQ1: Valg vs JavaMOP/TraceMOP
│   ├── rq2.csv                             # RQ2: Valg vs random sampling
│   ├── rq3-fixed.csv                       # RQ3: Ablation (fixed alpha/epsilon)
│   ├── rq3-tuning.csv                      # RQ3: Optuna tuning results per project
│   ├── rq4.csv                             # RQ4: Multi-revision evaluation (1,472 revisions)
│   ├── emop.csv                            # eMOP integration results
│   ├── ablation.csv                        # Ablation study results
│   └── shas/                               # Git SHAs per project (one file per project)
│
└── pom.xml                                 # Maven root configuration (multi-module build)
```

---

## 1. RL Technique

### Core RL Agent
**File:** `Valg/rv-monitor-rt/src/main/java/com/runtimeverification/rvmonitor/java/rt/table/rlagent/RLAgent.java`

This implements a **two-armed bandit** with **ERWA** (Exponential Recency-Weighted Average) and **epsilon-greedy** action selection.

- **Fields:**
  - `Qc` (line 10): Q-value for "create" action
  - `Qn` (line 9): Q-value for "ncreate" action
  - `ALPHA` (line 17): Learning rate
  - `EPSILON` (line 16): Exploration probability
  - `THRESHOLD` (line 24): Convergence threshold
  - `uniqueTraces` (line 20): HashSet of unique trace integer hashes
  - `numTotTraces`, `numDupTraces` (lines 13-14): Counters for ncreate reward

- **`decideAction()` (lines 47-79)** — Main decision method:
  - Line 49: First time step → always `create` (returns true)
  - Lines 53-54: After convergence → returns learned optimal action
  - Lines 56-65: If last action was `create`:
    - Unique trace → reward = 1.0
    - Duplicate trace → reward = 0.0
    - Update: `Qc = Qc + ALPHA * (reward - Qc)`
  - Lines 66-68: If last action was `ncreate`:
    - Reward = `numDupTraces / numTotTraces` (duplicate ratio)
    - Update: `Qn = Qn + ALPHA * (reward - Qn)`
  - Lines 73-75: Epsilon-greedy exploration (`Math.random() < EPSILON`)
  - Line 78: Exploitation (pick higher Q-value action)

- **`checkConverged()` (lines 40-45):**
  - Converges when `|1.0 - |Qc - Qn|| < THRESHOLD`
  - Stores optimal action in `convStatus`

- **`setMonitor()` (lines 81-86):**
  - Links created monitor to agent for feedback
  - If converged: `monitor.recordEvents = false` (saves overhead)

### RL Code Injection (Generated Code)
**File:** `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/combinedoutputcode/event/itf/EventMethodBody.java`

- **`addRLAgentCheck()` (lines 1093-1168):**
  - Only applies to **parametric specs** (line 1094: skips if 0 parameters)
  - Computes `threadLoc = Thread.currentThread().getId() + System.identityHashCode(joinpoint.getSourceLocation())`
  - Lazily creates `RLAgent` per (thread, location) pair
  - Calls `rlAgent.decideAction()` — if false, skips monitor creation entirely
  - If true, creates monitor and calls `rlAgent.setMonitor(monitor)`

### Per-Spec Global State
**File:** `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/combinedoutputcode/CombinedOutput.java`

- **`declareAgents()` (lines 165-175):** For each parametric spec, generates:
  - `HashMap<Integer, RLAgent> specName_agents` — one agent per (thread, location)
  - `HashSet<Integer> specName_traces` — shared unique trace hashes

### Trace Integer Encoding
**File:** `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/monitor/BaseMonitor.java`

- Lines 465-467: Each event accumulates into `traceVal`:
  ```java
  traceVal += System.identityHashCode(joinpoint.getSourceLocation()) + random.nextInt();
  ```
- Duplicate check: `HashSet<Integer>.contains(traceVal)` in O(1)

**File:** `Valg/rv-monitor-rt/src/main/java/com/runtimeverification/rvmonitor/java/rt/tablebase/AbstractMonitor.java`
- Line 14: `public int traceVal = 0;` — cumulative trace hash
- Line 15: `public boolean recordEvents = true;` — controls trace recording

### Non-Parametric Event Signaling (No RL)
- RL is **skipped** for non-parametric specs (EventMethodBody.java, line 1094-1095)
- Instead uses simple violation-location tracking: once spec violated at location l, suppress future events at l

---

## 2. Randomization

### Epsilon-Greedy Exploration
**File:** `Valg/rv-monitor-rt/src/main/java/com/runtimeverification/rvmonitor/java/rt/table/rlagent/RLAgent.java`
- Lines 73-75:
  ```java
  if (!converged && Math.random() < EPSILON) {
      Random random = new Random();
      return random.nextBoolean();  // 50/50 create vs ncreate
  }
  ```

### Random Sampling Baselines (RS10, RS50)
Pre-compiled JARs in `Valg/experiments/`:
- `rs10j.jar` / `rs10t.jar` — randomly create monitors with **10% probability**
- `rs50j.jar` / `rs50t.jar` — randomly create monitors with **50% probability**
- Source code not in repo; swapped in via:
  ```bash
  cp ../experiments/rs10j.jar no-track-no-stats-agent.jar
  ```

### Trace Hash Randomization
**File:** `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/monitor/BaseMonitor.java`
- Uses `random.nextInt()` with a **fixed seed per monitor** to encode event ordering in the trace hash

---

## 3. Hyperparameter Tuning

### Parameter Definitions
**File:** `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/RVMOptions.java` (lines 120-133)

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| `alpha` | `-alpha` | 0.9 | Learning rate (ERWA) |
| `epsilon` | `-epsilon` | 0.1 | Exploration probability |
| `threshold` | `-threshold` | 0.0001 | Convergence threshold |
| `initc` | `-initc` | 5.0 | Initial Q-value for create (optimistic) |
| `initn` | `-initn` | 0.0 | Initial Q-value for ncreate (realistic) |

### Optuna Tuning Script
**File:** `Valg/experiments/tuning.py` (110 lines)

- Sampler: **TPE** (Tree-structured Parzen Estimator)
- Search space: `alpha` in [0.01, 0.99], `epsilon` in [0.01, 0.99] (step 0.01)
- Objective: **maximize unique traces checked**
- Per trial: rebuilds agent with new params → runs `collect_traces.sh` → counts unique traces
- 100 trials per iteration, 3 iterations per project
- Storage: SQLite DB (`study-{repo}.db`)

### How Parameters Flow Through the System
```
tuning.py (suggests alpha, epsilon)
  → install.sh (TRACK, STATS, alpha, epsilon, threshold, initc, initn)
    → make-agent.sh (passes params to rv-monitor)
      → rv-monitor -alpha X -epsilon Y -threshold Z -initc A -initn B
        → RVMOptions.java (parses CLI flags)
          → EventMethodBody.java (generates code with params)
            → new RLAgent(traces, alpha, epsilon, threshold, initc, initn)
```

### Default Values in install.sh
**File:** `Valg/scripts/install.sh` (lines 5-12):
```bash
alpha=${3:-0.9}
epsilon=${4:-0.1}
threshold=${5:-0.0001}
initc=${6:-5.0}
initn=${7:-0.0}
```

### How initc=5.0 and initn=0.0 Flow Through the Code (Full Trace)

The initial Q-values for create (5.0, optimistic) and ncreate (0.0, realistic) pass through 6 layers:

**Layer 1 — Default values originate in `install.sh`**
`Valg/scripts/install.sh` (lines 11-12):
```bash
initc=${6:-5.0}    # default 5.0 for create
initn=${7:-0.0}    # default 0.0 for ncreate
```

**Layer 2 — Passed as positional args to `make-agent.sh`**
`Valg/scripts/install.sh` (line 47):
```bash
bash ${SCRIPT_DIR}/make-agent.sh ... ${alpha} ${epsilon} ${threshold} ${initc} ${initn}
```

**Layer 3 — `make-agent.sh` receives them and passes to `rv-monitor` CLI**
`Valg/scripts/make-agent.sh` (lines 37-38, 64):
```bash
initc=${13}
initn=${14}
# ...
rv_monitor_flag="${rv_monitor_flag} -alpha ${alpha} -epsilon ${epsilon} -threshold ${threshold} -initc ${initc} -initn ${initn}"
```

**Layer 4 — `RVMOptions.java` parses CLI flags via JCommander**
`Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/RVMOptions.java` (lines 129-133):
```java
@Parameter(names={"-initc"},description = "[RLMOP] Initial action value for create")
public double initc;    // receives 5.0

@Parameter(names={"-initn"},description = "[RLMOP] Initial action value for ncreate")
public double initn;    // receives 0.0
```

**Layer 5 — Code generator embeds them into generated Java source**
`Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/combinedoutputcode/event/itf/EventMethodBody.java` (lines 1122-1126):
Generates code like:
```java
new RLAgent(spec_traces, 0.9, 0.1, 0.0001, 5.0, 0.0)
```

**Layer 6 — `RLAgent` constructor assigns them as initial Q-values**
`Valg/rv-monitor-rt/src/main/java/com/runtimeverification/rvmonitor/java/rt/table/rlagent/RLAgent.java` (lines 36-37):
```java
this.Qc = initc;   // Q-value for create = 5.0 (optimistic)
this.Qn = initn;   // Q-value for ncreate = 0.0 (realistic)
```

**Why 5.0 and 0.0?**

This is the **"balanced strategy"** from the paper (Section III-B, "Initial value selection"):
- **`initc = 5.0` (optimistic):** Encourages the agent to **create monitors early on**. Since `Qc` starts high, the exploitation phase (`return (Qn <= Qc) ? true : false` at line 78) favors "create" initially. This is intentional because unique traces tend to appear more frequently at earlier time steps.
- **`initn = 0.0` (realistic):** The ncreate action starts at zero and only learns its real value through exploration. It does not artificially encourage skipping monitors.

Since `decideAction()` returns `true` (create) when `Qn <= Qc` (line 78), and initially `0.0 <= 5.0`, the agent starts by creating monitors. Over time, if most traces are redundant, the create reward drops toward 0 while the ncreate reward rises, eventually causing the agent to learn to skip monitor creation.

---

## 4. Workflow — What Triggers What

### Build Pipeline
```
setup.sh
  └→ Clones repo, builds with mvn package

install.sh (TRACK, STATS, alpha, epsilon, threshold, initc, initn)
  ├→ install-javaparser.sh          # Patches JavaParser
  ├→ mvn clean install -DskipTests  # Builds rv-monitor, rv-monitor-rt, javamop
  └→ make-agent.sh                  # Generates the monitoring agent JAR
       ├→ javamop *.mop             # .mop specs → AspectJ code + .rvm files
       ├→ rv-monitor -merge *.rvm   # Merges specs, generates Java monitor code
       │    └→ EventMethodBody.java injects RL logic into generated code
       ├→ javac *.java              # Compiles generated monitors
       └→ javamopagent              # Packages into agent JAR
```

### Execution Pipeline
```
not_collect_traces.sh (ValgJ — violations only)
  ├→ Clones project at specific SHA
  ├→ Installs agent JAR to Maven local repo
  ├→ mvn surefire:test with -Xmx500g
  │    └→ At runtime: AspectJ intercepts method calls
  │         └→ For each creation event:
  │              RLAgent.decideAction() → create or skip monitor
  └→ Output: violation counts, execution time

collect_traces.sh (ValgT — traces + violations)
  ├→ Same as above, plus COLLECT_TRACES=1 env var
  ├→ Traces written to TRACEDB_PATH directory
  └→ count-traces-frequency.py post-processes trace data
       └→ Output: unique trace counts
```

### Experiment Pipeline
```
ev_base.py      → Runs JavaMOP/TraceMOP baselines on GCP VMs
ev_default.py   → Runs ValgJ/ValgT with default hyperparameters on GCP
ev_optimal.py   → Runs ValgJ/ValgT with tuned hyperparameters on GCP
tuning.py       → Optuna-based tuning (per project)
run_tool.sh     → Local Docker-based batch execution
```

---

## 5. Specs Excluded from RL (specList)

**File:** `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/combinedoutputcode/event/itf/EventMethodBody.java` (lines 103-113)

These 10 parametric specs are **hardcoded to be excluded from RL** — they get standard monitoring without the agent decision gate:

```java
private List<String> specList = Arrays.asList(
    "Collections_SynchronizedCollection",
    "Collections_SynchronizedMap",
    "Console_FillZeroPassword",
    "Map_UnsafeIterator",
    "NavigableMap_Modification",
    "NavigableMap_UnsafeIterator",
    "NavigableSet_Modification",
    "ObjectStreamClass_Initialize",
    "PasswordAuthentication_FillZeroPassword",
    "PipedStream_SingleThread",
    "Closeable_MultipleClose"
);
```

**Why excluded?** These are parametric specs that behave similarly to non-parametric ones (e.g., they have simple creation patterns or few unique parameter bindings), so applying RL to them provides no benefit and could miss violations.

The exclusion is checked twice:
- Line 1097: Before deciding whether to create a new monitor (skips RL gate)
- Line 1182: After monitor creation, to skip calling `rlAgent.setMonitor()` (no feedback needed)

---

## 6. Non-Parametric Event Signaling — How It Works in Code

For non-parametric specs (0 parameters), Valg does **not** use RL. Instead, it uses a simpler `violated` flag mechanism:

**File:** `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/monitor/RawMonitor.java`

1. **Line 309:** Each generated non-parametric monitor gets a `violated` boolean field:
   ```java
   ret += "public boolean violated;\n";
   ```

2. **Lines 111-118:** When a violation message is printed ("`has been violated on line`"), the code generator injects `violated = true;` right after it:
   ```java
   int idx = eventActionStr.indexOf("has been violated on line");
   while (idx > 0) {
       idx = eventActionStr.indexOf("}", idx);
       eventActionStr = eventActionStr.substring(0, idx) +
                        "violated = true;\n" +
                        eventActionStr.substring(idx);
   }
   ```

3. **Lines 191-215:** The `Monitoring()` method generates code that:
   - Resets `violated = false` before sending an event (line 192)
   - Sends the event to the monitor (line 194)
   - Checks `if (monitor.violated) { return false; }` after (lines 213-215)
   - If violated, the calling code records the location and suppresses future events from that location

This implements **Algorithm 3** from the paper: once a non-parametric spec is violated at location l, future events at l are suppressed.

---

## 7. Working with Specs (.mop Files)

### 7.1 Where Current Specs Are

Specs live in two directories:

| Directory | Count | Purpose |
|-----------|-------|---------|
| `Valg/scripts/props/` | 160 `.mop` files | Standard monitoring (ValgJ) |
| `Valg/scripts/props-track/` | 162 `.mop` files | Tracking mode (ValgT) — same specs + extra instrumentation |

**Example specs and what they check:**

| Spec File | API Rule | Type |
|-----------|----------|------|
| `Iterator_HasNext.mop` | Must call `hasNext()` before `next()` | Parametric, LTL |
| `Closeable_MultipleClose.mop` | Don't call `close()` more than once | Parametric, ERE |
| `Map_UnsafeIterator.mop` | Don't modify map while iterating | Parametric, FSM |
| `Collections_SynchronizedCollection.mop` | Access synced collection under lock | Parametric, ERE |
| `Thread_SetDaemonBeforeStart.mop` | Call `setDaemon()` before `start()` | Parametric, LTL |

Each `.mop` file defines:
1. **Parameters** — the objects being tracked (e.g., `Iterator i`, `Map m`)
2. **Events** — method calls to intercept via AspectJ pointcuts
3. **Property** — formal rule (LTL, ERE, FSM, or CFG formula)
4. **Handler** — what to do on violation (typically log via `RVMLogging`)

### 7.2 How to Add a New Spec

**Step 1:** Create a `.mop` file in `Valg/scripts/props/` (and `props-track/` if using ValgT):

```
// MySpec.mop
package mop;

import java.util.*;

MySpec(SomeClass obj) {
    // Events: AspectJ pointcuts that intercept method calls
    creation event open after(SomeClass obj) returning :
        call(* SomeClass.open(..)) && target(obj) { }
    event use before(SomeClass obj) :
        call(* SomeClass.use(..)) && target(obj) { }
    event close before(SomeClass obj) :
        call(* SomeClass.close(..)) && target(obj) { }

    // Property: formal rule (LTL, ERE, FSM, or CFG)
    ere: open use* close

    // Handler: what happens on violation/match
    @fail {
        RVMLogging.out.println(Level.CRITICAL, __DEFAULT_MESSAGE);
    }
}
```

Key syntax:
- `creation event` — triggers monitor instantiation (this is where RL decides create vs skip)
- `event` — subsequent events sent to existing monitors
- Property types: `ltl:`, `ere:`, `fsm:`, `cfg:`
- Handlers: `@violation` (LTL), `@match`/`@fail` (ERE/FSM), `@error` (CFG)

**Step 2:** Rebuild the agent:

```bash
cd Valg/scripts
bash install.sh [TRACK] [STATS] [alpha] [epsilon] [threshold] [initc] [initn]
```

This runs the full pipeline: `.mop` → JavaMOP → `.rvm` → rv-monitor → Java → compile → agent JAR.

**Step 3:** If the new spec should be **excluded from RL** (like the 10 specs in `specList`), add its name to the list in:
`Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/combinedoutputcode/event/itf/EventMethodBody.java` (lines 103-113)

### 7.3 How Specs Are Used by the Monitor During RV

**Compile-time pipeline (building the agent):**

```
.mop file
  → [JavaMOP] parses spec, extracts events + pointcuts + property
  → [JavaMOP] generates .rvm (events + property, no AspectJ)
  → [rv-monitor] logic plugin converts property → FSM transition tables
  → [rv-monitor] generates Java monitor class with:
       - State variable ($state$)
       - Transition arrays ($transition_eventName$)
       - Event handler methods (event_eventName())
       - Violation handler code
       - **Valg RL gate** injected at monitor creation point
  → [rv-monitor] generates AspectJ aspect with pointcuts → event method calls
  → [javac + ajc] compiles everything
  → [javamopagent] packages into agent JAR
```

**Runtime flow (when tests run with the agent):**

```
Test executes → calls Iterator.next()
  │
  ├─ AspectJ intercepts via pointcut match
  │
  ├─ Calls generated event method: Iterator_HasNextRuntimeMonitor.nextEvent(i)
  │
  ├─ Looks up monitor for this Iterator instance in indexing tree
  │    (HashMap<WeakRef<Iterator>, Monitor>)
  │
  ├─ If no monitor exists (creation event):
  │    ├─ [Valg RL] RLAgent.decideAction() → true (create) or false (skip)
  │    ├─ If create: new monitor inserted into indexing tree
  │    └─ If skip: event is dropped, no monitoring happens
  │
  ├─ If monitor exists:
  │    ├─ Monitor receives event: $state$ = $transition_next$[$state$]
  │    ├─ If new state is violation state:
  │    │    ├─ Execute @violation handler (logs via RVMLogging)
  │    │    └─ ViolationRecorder.record(specName) stores violation + stack trace
  │    └─ If not violation: continue monitoring
  │
  └─ For non-parametric specs (no RL):
       ├─ Single global monitor tracks state
       ├─ On violation: sets violated = true, records location
       └─ Future events from same location are suppressed
```

**Key point:** Each `.mop` spec becomes its own independent monitor class with its own FSM, pointcuts, and (for parametric specs) its own set of RL agents. All 160 specs run simultaneously during test execution, each intercepting their relevant API calls.

---

## Quick Reference: What to Tweak

| What to change | File to edit |
|---|---|
| RL algorithm / reward function | `Valg/rv-monitor-rt/src/main/java/com/runtimeverification/rvmonitor/java/rt/table/rlagent/RLAgent.java` (lines 56-68) |
| Exploration strategy | `Valg/rv-monitor-rt/src/main/java/com/runtimeverification/rvmonitor/java/rt/table/rlagent/RLAgent.java` (lines 73-78) |
| Convergence condition | `Valg/rv-monitor-rt/src/main/java/com/runtimeverification/rvmonitor/java/rt/table/rlagent/RLAgent.java` (lines 40-45) |
| Add/modify hyperparameters | `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/RVMOptions.java` (lines 120-133) |
| How RL is injected into monitors | `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/combinedoutputcode/event/itf/EventMethodBody.java` (lines 1093-1168) |
| Default parameter values | `Valg/scripts/install.sh` (lines 5-12) |
| Hyperparameter tuning setup | `Valg/experiments/tuning.py` |
| Trace encoding scheme | `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/monitor/BaseMonitor.java` (lines 465-467) |
| Add new specs to monitor | Add `.mop` file to `Valg/scripts/props/` |
| Docker environment | `Valg/scripts/Dockerfile` |
| Monitor state machine logic | `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/monitor/BaseMonitor.java` |
| Parametric indexing tree | `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/combinedoutputcode/newindexingtree/IndexingTreeImplementation.java` |
| Violation recording | `Valg/rv-monitor-rt/src/main/java/com/runtimeverification/rvmonitor/java/rt/ViolationRecorder.java` |
| Logic plugin (FSM/LTL/ERE) | `Valg/logicrepository/src/.../plugins/{fsm,ltl,ere}/` |
| Handler macro replacement | `Valg/rv-monitor/src/main/java/com/runtimeverification/rvmonitor/java/rvj/output/monitor/HandlerMethod.java` |
