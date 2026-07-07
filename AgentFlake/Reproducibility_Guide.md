# AgentFlake Reproducibility Guide

AgentFlake is an agentic flaky-test repair pipeline. It reads a flaky-test
case from `test_config.csv`, prepares the subject project, collects the
smallest useful context, asks an LLM to produce a patch, applies the patch,
and validates the repaired test.

This guide describes the current way to run AgentFlake from this repository.
The two normal entry points are:

```bash
python3 run_agentic.py oktahookssdkjavahooks9187787createUserTest --models claude --runs 1
```

and:

```bash
python3 run_agentic_bulk.py --models claude --runs 1
```

The first command runs one case. The second command reads `test_config.csv`
and runs the selected rows one by one in CSV order.

---

## 1. Repository Layout

From the repository root:

```text
.
├── AgentFlake/
│   ├── agentic/
│   │   ├── run_agentic.py
│   │   ├── run_agentic_bulk.py
│   │   ├── run_agentic_pass_at_k.py
│   │   ├── run_agentic_od.sh
│   │   ├── run_agentic_td.sh
│   │   ├── run_agentic_id.sh
│   │   ├── run_agentic_nio.sh
│   │   ├── run_agentic_unclassified.sh
│   │   ├── run_agentic_brittle.sh
│   │   ├── agentic_orchestrator.py
│   │   ├── agentic_config.py
│   │   ├── agent_tools.py
│   │   ├── prompts.py
│   │   └── flaky_examples/
│   ├── LLM Scripts/
│   │   └── apply_fix.py
│   ├── test_config.csv
│   ├── requirements.txt
│   ├── Dockerfile*
│   └── data/
├── experiments/
├── scripts/
├── FlakyDoctor/
└── README.md
```

Important paths:

| Path | Purpose |
|---|---|
| `AgentFlake/test_config.csv` | Case list. Each row describes one flaky-test repair target. |
| `AgentFlake/agentic/run_agentic.py` | Main single-case dispatcher. |
| `AgentFlake/agentic/run_agentic_bulk.py` | Bulk runner over `test_config.csv`. |
| `AgentFlake/agentic/run_agentic_pass_at_k.py` | Repeats one case for pass@k-style evaluation. |
| `AgentFlake/agentic/run_agentic_*.sh` | Type-specific setup and validation scripts. |
| `AgentFlake/agentic/agentic_config.py` | Defaults for models, iteration limits, keys, and tool budgets. |
| `AgentFlake/agentic/prompts.py` | System and task prompts given to the agent. |
| `AgentFlake/agentic/agent_tools.py` | Read-only tools and patch-submission tool exposed to the agent. |
| `AgentFlake/LLM Scripts/apply_fix.py` | Patch applier used after `submit_patch`. |
| `AgentFlake/data/` | Downloaded project zips, scratch workspaces, logs, and archived runs. |

---

## 2. Artifacts and Related Code

Additional artifacts used for comparison and inspection:

| Artifact | Link / Location | Purpose |
|---|---|---|
| AgentFlake Claude agent code | [AgentFlake_Claude_Agent](https://anonymous.4open.science/r/AgentFlake_Claude_Agent/) | Code used for the Claude agent runs. |
| `patches.zip` | `patches.zip` | Log of patches from our run over 164 cases. |
| FlakyDoctor code | [AgentFlake_FlakyDoctor](https://anonymous.4open.science/r/AgentFlake_FlakyDoctor/) | Baseline FlakyDoctor code. |
| FlakyGuard code | [agentic_fix_flakyguard](https://anonymous.4open.science/r/agentic_fix_flakyguard/README.md) | Baseline FlakyGuard code. |

---

## 3. Prerequisites

Install:

- Python 3.9 or newer
- Docker Desktop or Docker Engine
- Git
- Java is provided by the AgentFlake Docker images for the subject projects

Install Python dependencies from the `AgentFlake` directory:

```bash
cd AgentFlake
python3 -m pip install -r requirements.txt
```

The Python dependencies include:

- `anthropic`
- `openai`
- `tree-sitter`
- `tree-sitter-java`

`tree-sitter` and `tree-sitter-java` are required by
`LLM Scripts/apply_fix.py` for AST-aware patch application.

### API Keys

AgentFlake needs an API key for the model provider you choose.

For Claude:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

For OpenAI models:

```bash
export OPENAI_API_KEY="sk-..."
```

You can also place keys in `AgentFlake/agentic/agentic_config.py`, but
environment variables are usually cleaner for local use.

---

## 4. Understanding `test_config.csv`

`AgentFlake/test_config.csv` is the case index. Each row contains:

| Column | Meaning |
|---|---|
| `test_type` | Flakiness category: `od`, `td`, `id`, `nio`, `unclassified`, or `brittle`. |
| second column | Case identifier used as the first argument to `run_agentic.py`. |
| `zip` | Dataset zip base name. |
| `module` | Maven module for the victim test. |
| `polluter/state setter` | Polluter test for OD/Brittle cases, when present. |
| `flaky_test` | Victim test in `Class#method` format. |
| `iterations` | Repetition count used by some reproduction flows. |
| `config` | Dataset configuration label. |
| `java` | Java version expected by the subject project. |
| `nondexSeed` | NonDex seed for ID cases. |
| `url` | Zenodo URL for the project zip. |

To list case IDs manually:

```bash
cd AgentFlake
python3 - <<'PY'
import csv
with open("test_config.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        case_id = list(row.values())[1]
        print(row["test_type"], case_id)
PY
```

The command above prints the second column name used internally by the CSV.
When running AgentFlake, treat that value as the case ID.

---

## 5. Run One Case

Go to the agentic directory:

```bash
cd AgentFlake/agentic
```

Run one case:

```bash
python3 run_agentic.py oktahookssdkjavahooks9187787createUserTest --models claude --runs 1
```

What each part means:

| Part | Meaning |
|---|---|
| `python3` | Runs the Python dispatcher. |
| `run_agentic.py` | Main single-case AgentFlake entry point. |
| `oktahookssdkjavahooks9187787createUserTest` | Case ID from `test_config.csv`. |
| `--models claude` | Uses the `claude` alias from `agentic_config.py`. |
| `--runs 1` | Performs one independent repair attempt for this model. |

A run with a different case ID has the same shape:

```bash
python3 run_agentic.py <case-id> --models claude --runs 1
```

### Useful Single-Case Options

```bash
python3 run_agentic.py <case-id> --models claude --runs 3
```

Runs the same case three independent times.

```bash
python3 run_agentic.py <case-id> --models claude,claude-opus --runs 1
```

Runs the case once for each listed model.

```bash
python3 run_agentic.py <case-id> --models claude --runs 1 --max-iterations 5
```

Limits the agent to five patch attempts for that run.

```bash
python3 run_agentic.py <case-id> --models claude --runs 1 --keep-workspace
```

Keeps the per-case working files after the run for inspection.

---

## 6. Run Many Cases

Go to the agentic directory:

```bash
cd AgentFlake/agentic
```

Run every row in CSV order:

```bash
python3 run_agentic_bulk.py --models claude --runs 1
```

The bulk runner invokes the single-case dispatcher for each selected row:

```bash
python3 run_agentic.py <case-id> --models claude --runs 1
```

It continues to the next row even if one case fails. At the end it prints
a summary of all completed rows and exits nonzero if any selected row failed.

### Useful Bulk Options

Preview commands without running them:

```bash
python3 run_agentic_bulk.py --models claude --runs 1 --dry-run
```

Run only the first 10 selected rows:

```bash
python3 run_agentic_bulk.py --models claude --runs 1 --limit 10
```

Run only selected test types:

```bash
python3 run_agentic_bulk.py --models claude --runs 1 --types td,id
```

Start at a specific case ID:

```bash
python3 run_agentic_bulk.py --models claude --runs 1 --start-from HADOOP-12588
```

Stop after the first failing case:

```bash
python3 run_agentic_bulk.py --models claude --runs 1 --stop-on-failure
```

Use more than one model:

```bash
python3 run_agentic_bulk.py --models claude,claude-opus --runs 1
```

Use a different CSV:

```bash
python3 run_agentic_bulk.py --csv ../test_config.csv --models claude --runs 1
```

---

## 7. Model Aliases

Aliases are defined in `AgentFlake/agentic/agentic_config.py`.

Common aliases:

| Alias | Model |
|---|---|
| `claude` | `claude-sonnet-4-6` |
| `claude-sonnet` | `claude-sonnet-4-6` |
| `claude-opus` | `claude-opus-4-7` |
| `opus` | `claude-opus-4-7` |
| `haiku` | `claude-haiku-4-5-20251001` |
| `openai` | OpenAI default from config |
| full model ID | Passed through unchanged |

Examples:

```bash
python3 run_agentic.py <case-id> --models claude --runs 1
python3 run_agentic.py <case-id> --models claude-opus --runs 1
python3 run_agentic.py <case-id> --models gpt-4o --runs 1
```

---

## 8. What Happens During a Run

AgentFlake uses a five-step workflow.

### Step 1: Initialization

`run_agentic.py` reads `test_config.csv`, finds the requested case ID,
checks its `test_type`, resolves model aliases, checks the required API key,
and calls `run_agentic_pass_at_k.py`.

`run_agentic_pass_at_k.py` then calls the correct type-specific script:

| `test_type` | Script |
|---|---|
| `od` | `run_agentic_od.sh` |
| `td` | `run_agentic_td.sh` |
| `id` | `run_agentic_id.sh` |
| `nio` | `run_agentic_nio.sh` |
| `unclassified` / `unassigned` | `run_agentic_unclassified.sh` |
| `brittle` / `britle` | `run_agentic_brittle.sh` |

The type-specific script downloads the project zip if needed, unpacks the
case under `AgentFlake/data/`, prepares the working tree, runs the failing
test setup for that category, and writes the initial failure evidence.

### Step 2: Planning and Context Collection

The orchestrator starts the LLM with a compact prompt containing:

- category
- case ID
- victim test
- relevant failure log
- instructions for minimal repair

The model can request context through tools:

| Tool | Purpose |
|---|---|
| `get_test_code` | Reads the victim test. |
| `get_code` | Reads a specific Java class, method, or resource. |
| `get_error_logs` | Reads failure, compile, or validation logs. |
| `get_flaky_example` | Provides a category-specific repair exemplar when available. |
| `get_rv_trace_diff` | Provides trace-difference context for categories that use trace evidence. |

Tool use is bounded by limits in `agentic_config.py` and the prompt.

### Step 3: Sufficiency Check

The model decides when it has enough evidence to patch. It should not keep
reading files indefinitely. Once confident, it calls `submit_patch`.

The prompt asks for:

- a diagnosis
- root cause
- fix description
- unified diff
- structured fallback code edits

### Step 4: Patch Generation and Application

The orchestrator writes the patch attempt to the run output directory and
calls:

```text
AgentFlake/LLM Scripts/apply_fix.py
```

`apply_fix.py` tries the unified diff first. If needed, it uses the
structured fallback edits. The applier is AST-aware for Java where possible.

After applying the patch, AgentFlake compiles the relevant project/module.
If compilation fails, the error is returned to the model for the next
iteration.

### Step 5: Validation

If compilation succeeds, AgentFlake reruns the reproduction command for the
case. The validation script writes:

```text
verify_after_fix.verdict
verify_after_fix.log
```

Possible verdicts:

| Verdict | Meaning |
|---|---|
| `PASSED` | The patch compiled and the reproduction command passed. |
| `FAILED` | The patch applied/compiled but validation still failed. |
| `INCOMPLETE` | The run ended before a passing repair was produced. |

On failure, the working tree is restored and the model receives the failure
report before the next patch attempt. The loop ends when a patch passes or
when `MAX_ITERATIONS` is reached.

---

## 9. Output Locations

For a single case, archived runs are written under:

```text
AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/
```

Typical layout:

```text
AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/
├── summary.csv
└── <model-id>/
    └── run_1/
        ├── pipeline.log
        ├── .run_complete
        └── Steps_Output_Files/
            ├── agentic_conversation.json
            ├── agentic_iterations.jsonl
            ├── apply_report.json
            ├── llm_context.txt
            ├── llm_response.json
            ├── verify_after_fix.log
            └── verify_after_fix.verdict
```

Important files:

| File | Meaning |
|---|---|
| `summary.csv` | One-row-per-run summary for the case. |
| `pipeline.log` | Full shell/Python log for that run. |
| `agentic_conversation.json` | Full model/tool conversation. |
| `agentic_iterations.jsonl` | Structured per-iteration metadata. |
| `llm_context.txt` | Initial prompt sent to the model. |
| `llm_response.json` | Last model patch payload and token usage. |
| `apply_report.json` | Patch application and compile result. |
| `verify_after_fix.log` | Raw validation output. |
| `verify_after_fix.verdict` | Final verdict for the run. |

To inspect the final verdict:

```bash
cat AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/Steps_Output_Files/verify_after_fix.verdict
```

To inspect the run summary:

```bash
cat AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/summary.csv
```

---

## 10. Configuration

Most defaults live in:

```text
AgentFlake/agentic/agentic_config.py
```

Common settings:

| Setting | Meaning |
|---|---|
| `MAX_ITERATIONS` | Maximum patch attempts per run. |
| `MAX_TOOL_TURNS_PER_ITERATION` | Maximum context/tool turns before a patch is required. |
| `VERIFY_PASS_RUNS` | Number of confirmation validations after a passing patch. |
| `DEFAULT_MODEL` | Default model ID. |
| `MAX_TOKENS` | Max output tokens for one model call. |
| `TEMPERATURE` | Model temperature. |
| `TOOL_OUTPUT_MAX_CHARS` | Tool-output truncation limit. |
| `CLAUDE_MODELS` | Claude aliases. |
| `OPENAI_MODELS` | OpenAI aliases. |

Prefer command-line flags for routine runs:

```bash
python3 run_agentic.py <case-id> --models claude --runs 1 --max-iterations 5
python3 run_agentic_bulk.py --models claude --runs 1 --limit 20
```

Edit `agentic_config.py` when you want a persistent default.

---

## 11. Practical Run Recipes

### Run One Known Case

```bash
cd AgentFlake/agentic
python3 run_agentic.py oktahookssdkjavahooks9187787createUserTest --models claude --runs 1
```

### Run the First Five CSV Rows

```bash
cd AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1 --limit 5
```

### Run All TD Cases

```bash
cd AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1 --types td
```

### Resume Bulk Work at a Specific Case

```bash
cd AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1 --start-from ZOOKEEPER-4327-testRequestThrottler
```

### Preview a Bulk Run

```bash
cd AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1 --types id --limit 3 --dry-run
```

---

## 12. Troubleshooting

### `ERROR: CSV not found`

Run from the expected directory:

```bash
cd AgentFlake/agentic
python3 run_agentic.py <case-id> --models claude --runs 1
```

or pass an explicit CSV to the bulk runner:

```bash
python3 run_agentic_bulk.py --csv ../test_config.csv --models claude --runs 1
```

### `case not found`

Check the case ID in `test_config.csv`. It must match the CSV value exactly.

```bash
cd AgentFlake
grep -n "oktahookssdkjavahooks9187787createUserTest" test_config.csv
```

### API-Key Error

Set the key for the provider you are running:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

or:

```bash
export OPENAI_API_KEY="sk-..."
```

### Python Dependency Error

Install requirements:

```bash
cd AgentFlake
python3 -m pip install -r requirements.txt
```

### Docker Is Not Running

Start Docker Desktop or Docker Engine, then rerun the command.

### Patch Applies But Validation Fails

Open:

```text
AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/Steps_Output_Files/verify_after_fix.log
```

and:

```text
AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/Steps_Output_Files/apply_report.json
```

These files show whether the failure was from patch application,
compilation, or test validation.

### Run Ends With `INCOMPLETE`

Look at:

```text
pipeline.log
agentic_conversation.json
agentic_iterations.jsonl
```

Common causes include setup failure, inability to reproduce the initial
failure, patch-application failure, compile failure, or exhausting the
iteration budget.

---

## 13. Quick Checklist

1. Install Python dependencies:

   ```bash
   cd AgentFlake
   python3 -m pip install -r requirements.txt
   ```

2. Export the key:

   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

3. Start Docker.

4. Run one case:

   ```bash
   cd AgentFlake/agentic
   python3 run_agentic.py oktahookssdkjavahooks9187787createUserTest --models claude --runs 1
   ```

5. Or run rows in order:

   ```bash
   cd AgentFlake/agentic
   python3 run_agentic_bulk.py --models claude --runs 1
   ```

6. Inspect:

   ```bash
   cat ../data/AGENTIC_FULL_RUNS/<case-id>_runs/summary.csv
   ```
