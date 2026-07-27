# AgentFlake

AgentFlake is an agentic flaky-test repair pipeline. It reads a flaky-test case
from `AgentFlake/test_config.csv`, prepares the subject project, asks an LLM to
diagnose and patch the bug, applies the patch, and validates the repaired test.

## 1. Repository Layout

```text
AgentFlake/
├── agentic/
│   ├── README.md
│   ├── agent_tools.py
│   ├── agentic_config.py
│   ├── agentic_orchestrator.py
│   ├── agentic_orchestrator_anthropic.py
│   ├── agentic_orchestrator_openai.py
│   ├── agentic_verify.py
│   ├── flaky_examples/
│   ├── orchestrator_common.py
│   ├── prompts.py
│   ├── run_agentic.py
│   ├── run_agentic_brittle.sh
│   ├── run_agentic_bulk.py
│   ├── run_agentic_id.sh
│   ├── run_agentic_nio.sh
│   ├── run_agentic_od.sh
│   ├── run_agentic_pass_at_k.py
│   ├── run_agentic_td.sh
│   ├── run_agentic_unclassified.sh
│   └── test_integrity.py
├── LLM Scripts/
│   ├── apply_fix.py
│   └── assemble_llm_context.py
├── data/
├── Dockerfile
├── Dockerfile.hadoop
├── Dockerfile.od
├── Dockerfile.od11
├── Dockerfile8.id
├── Dockerfile11.id
├── Dockerfile17.id
├── patches.zip
├── requirements.txt
└── test_config.csv
```

## 2. Important Paths

| Path | Purpose |
|---|---|
| `AgentFlake/test_config.csv` | Lists every repair case, including case ID, flaky-test type, Maven module, victim test, Java version, dataset zip, and download URL. |
| `AgentFlake/agentic/run_agentic.py` | Main command for running one case; it reads the CSV, resolves the model, and starts the repeated-run harness. |
| `AgentFlake/agentic/run_agentic_bulk.py` | Runs many CSV rows in order, with filters such as `--limit`, `--types`, and `--dry-run`. |
| `AgentFlake/agentic/run_agentic_pass_at_k.py` | Repeats one case for `--runs N`, archives each run, and writes per-run summaries. |
| `AgentFlake/agentic/run_agentic_od.sh` | Prepares and validates order-dependent cases with a polluter and victim test. |
| `AgentFlake/agentic/run_agentic_td.sh` | Prepares and validates timing-dependent cases using the flaky-code-change setup. |
| `AgentFlake/agentic/run_agentic_id.sh` | Prepares and validates implementation-dependent cases using the configured NonDex seed. |
| `AgentFlake/agentic/run_agentic_nio.sh` | Prepares and validates non-idempotent-outcome cases by generating a same-JVM wrapper test. |
| `AgentFlake/agentic/run_agentic_unclassified.sh` | Prepares and validates unclassified cases using the victim failure only. |
| `AgentFlake/agentic/run_agentic_brittle.sh` | Prepares and validates brittle cases, which use the OD-style polluter/victim setup. |
| `AgentFlake/agentic/agentic_config.py` | Stores model aliases, default model, API-key fallback values, iteration limits, and tool-output limits. |
| `AgentFlake/agentic/agent_tools.py` | Implements the read-only tools the LLM can call to inspect tests, source code, logs, and examples. |
| `AgentFlake/agentic/agentic_verify.py` | Re-runs the relevant validation command after a patch is applied. |
| `AgentFlake/LLM Scripts/apply_fix.py` | Applies the LLM patch to the checked-out flaky project, recompiles it, and writes `apply_report.json`. |
| `AgentFlake/LLM Scripts/assemble_llm_context.py` | Shared helper code for CSV loading, source lookup, Java method extraction, and failure-log extraction. |
| `AgentFlake/data/` | Stores downloaded dataset zips, unpacked case workspaces, run logs, and archived outputs. |

## 3. Prerequisites

Install:

- Python 3.9 or newer
- Docker Desktop or Docker Engine
- Git

Docker must be running before starting an AgentFlake run. Java for subject
projects is provided by the Docker images built from `AgentFlake/Dockerfile*`.

Install Python dependencies:

```bash
cd AgentFlake
python3 -m pip install -r requirements.txt
```

The required Python packages include:

- `anthropic`
- `openai`
- `tree-sitter`
- `tree-sitter-java`

`tree-sitter` and `tree-sitter-java` are used by
`AgentFlake/LLM Scripts/apply_fix.py` for Java-aware patch application.

Set the API key for the provider you run:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

For `--models claude`, only `ANTHROPIC_API_KEY` is required.

## 4. Running One Case

```bash
cd AgentFlake/agentic
python3 run_agentic.py oktahookssdkjavahooks9187787createUserTest --models claude --runs 1
```

Use a different case ID with the same command shape:

```bash
cd AgentFlake/agentic
python3 run_agentic.py <case-id> --models claude --runs 1
```

Useful single-case options:

```bash
python3 run_agentic.py <case-id> --models claude --runs 3
python3 run_agentic.py <case-id> --models claude,claude-opus --runs 1
python3 run_agentic.py <case-id> --models claude --runs 1 --max-iterations 5
python3 run_agentic.py <case-id> --models claude --runs 1 --keep-workspace
```

## 5. Running Bulk Cases

```bash
cd AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1
```

Preview commands without running them:

```bash
python3 run_agentic_bulk.py --models claude --runs 1 --dry-run
```

Run only selected types:

```bash
python3 run_agentic_bulk.py --models claude --runs 1 --types td,id
```

Limit the number of rows:

```bash
python3 run_agentic_bulk.py --models claude --runs 1 --limit 10
```

## 6. Case IDs

Case IDs come from `AgentFlake/test_config.csv`. To list them:

```bash
cd AgentFlake
python3 - <<'PY'
import csv
with open("test_config.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        print(row["test_type"], row["result_container"])
PY
```

`AgentFlake/test_config.csv` contains:

| Column | Meaning |
|---|---|
| `test_type` | Flakiness category: `od`, `td`, `id`, `nio`, `unclassified`, `brittle`, or `britle`. |
| `result_container` | Case ID passed to `run_agentic.py`. |
| `zip` | Dataset zip base name. |
| `module` | Maven module containing the victim test. |
| `polluter/state setter` | Polluter test for OD/Brittle cases, when present. |
| `flaky_test` | Victim test in `Class#method` format. |
| `iterations` | Repetition count used by some reproduction flows. |
| `config` | Dataset configuration label. |
| `java` | Java version expected by the subject project. |
| `nondexSeed` | NonDex seed for ID cases. |
| `url` | Dataset zip URL. |

## 7. Configuration

Most defaults live in `AgentFlake/agentic/agentic_config.py`.

| Setting | Meaning |
|---|---|
| `ANTHROPIC_API_KEY` | Optional fallback Claude key; environment variables are preferred. |
| `OPENAI_API_KEY` | Optional fallback OpenAI key; environment variables are preferred. |
| `CLAUDE_MODELS` | Claude model aliases accepted by `--models`. |
| `OPENAI_MODELS` | OpenAI model aliases accepted by `--models`. |
| `DEFAULT_MODEL` | Model used when no model is provided by lower-level runners. |
| `MAX_ITERATIONS` | Maximum patch attempts per run. |
| `MAX_TOOL_TURNS_PER_ITERATION` | Maximum context-tool turns before a patch is required. |
| `VERIFY_PASS_RUNS` | Number of confirmation validations after a passing patch. |
| `MAX_TOKENS` | Maximum output tokens for one model call. |
| `TEMPERATURE` | Model sampling temperature. |
| `TOOL_OUTPUT_MAX_CHARS` | Output cap for most tool responses. |

Prefer command-line flags for routine changes:

```bash
cd AgentFlake/agentic
python3 run_agentic.py <case-id> --models claude --runs 1 --max-iterations 5
python3 run_agentic_bulk.py --models claude --runs 1 --limit 20
```

## 8. Output Locations

Run archives are written under:

```text
AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/
```

Typical files:

| Path | Meaning |
|---|---|
| `AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/summary.csv` | One-row-per-run summary for the case. |
| `AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/pipeline.log` | Full shell and Python log for one run. |
| `AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/.run_complete` | Marker written when the run finishes. |
| `AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/Steps_Output_Files/agentic_conversation.json` | Full model/tool conversation. |
| `AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/Steps_Output_Files/agentic_iterations.jsonl` | Structured metadata for each patch attempt. |
| `AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/Steps_Output_Files/llm_response.json` | Last model patch payload and token usage. |
| `AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/Steps_Output_Files/apply_report.json` | Patch application and compile result. |
| `AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/Steps_Output_Files/verify_after_fix.log` | Raw validation output. |
| `AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/Steps_Output_Files/verify_after_fix.verdict` | Final verdict for the run. |

## 9. Troubleshooting

### `ERROR: CSV not found`

Run from the agentic directory:

```bash
cd AgentFlake/agentic
python3 run_agentic.py <case-id> --models claude --runs 1
```

or pass an explicit CSV to the bulk runner:

```bash
cd AgentFlake/agentic
python3 run_agentic_bulk.py --csv ../test_config.csv --models claude --runs 1
```

### `case not found`

Check the case ID in `AgentFlake/test_config.csv`. It must match exactly:

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

These files show whether the failure was from patch application, compilation,
or test validation.

### Run Ends With `INCOMPLETE`

Inspect:

```text
AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/pipeline.log
AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/Steps_Output_Files/agentic_conversation.json
AgentFlake/data/AGENTIC_FULL_RUNS/<case-id>_runs/<model-id>/run_1/Steps_Output_Files/agentic_iterations.jsonl
```

Common causes include setup failure, inability to reproduce the initial
failure, patch-application failure, compile failure, or exhausting the
iteration budget.

## 10. Quick Checklist

```bash
cd AgentFlake
python3 -m pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
cd agentic
python3 run_agentic.py oktahookssdkjavahooks9187787createUserTest --models claude --runs 1
```

## 11. Artifacts and Related Code

| Artifact | Link / Location | Purpose |
|---|---|---|
| AgentFlake Claude agent code | [AgentFlake_Claude_Agent](https://anonymous.4open.science/r/AgentFlake_Claude_Agent/) | Code used for the Claude agent runs. |
| `patches.zip` | [AgentFlake/patches.zip](AgentFlake/patches.zip) | Log of patches from our run over 164 cases. |
| FlakyDoctor code | [AgentFlake_FlakyDoctor](https://anonymous.4open.science/r/AgentFlake_FlakyDoctor/) | Baseline FlakyDoctor code. |
| FlakyGuard code | [agentic_fix_flakyguard](https://anonymous.4open.science/r/agentic_fix_flakyguard/README.md) | Baseline FlakyGuard code. |
