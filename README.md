# AgentFlake

AgentFlake is an agentic flaky-test repair pipeline. It reads a flaky-test case
from `FlakyRV/AgentFlake/test_config.csv`,
prepares the subject project, asks an LLM to diagnose and patch the bug,
applies the patch, and validates the repaired test.

## Main Commands

Run one case:

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic.py oktahookssdkjavahooks9187787createUserTest --models claude --runs 1
```

Run many cases:

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1
```

## Repository Layout

```text
FlakyRV/
├── AgentFlake/
│   ├── agentic/
│   │   ├── README.md
│   │   ├── agent_tools.py
│   │   ├── agentic_config.py
│   │   ├── agentic_orchestrator.py
│   │   ├── agentic_orchestrator_anthropic.py
│   │   ├── agentic_orchestrator_openai.py
│   │   ├── agentic_verify.py
│   │   ├── flaky_examples/
│   │   ├── orchestrator_common.py
│   │   ├── prompts.py
│   │   ├── run_agentic.py
│   │   ├── run_agentic_brittle.sh
│   │   ├── run_agentic_bulk.py
│   │   ├── run_agentic_id.sh
│   │   ├── run_agentic_nio.sh
│   │   ├── run_agentic_od.sh
│   │   ├── run_agentic_pass_at_k.py
│   │   ├── run_agentic_td.sh
│   │   ├── run_agentic_unclassified.sh
│   │   └── test_integrity.py
│   ├── LLM Scripts/
│   │   ├── apply_fix.py
│   │   └── assemble_llm_context.py
│   ├── data/
│   ├── Dockerfile
│   ├── Dockerfile.hadoop
│   ├── Dockerfile.od
│   ├── Dockerfile.od11
│   ├── Dockerfile8.id
│   ├── Dockerfile11.id
│   ├── Dockerfile17.id
│   ├── requirements.txt
│   └── test_config.csv
├── .gitignore
└── README.md
```

## Important Paths

| Path | Purpose |
|---|---|
| `FlakyRV/AgentFlake/test_config.csv` | Case list. Each row describes one flaky-test repair target. |
| `FlakyRV/AgentFlake/agentic/run_agentic.py` | Main single-case dispatcher. |
| `FlakyRV/AgentFlake/agentic/run_agentic_bulk.py` | Bulk runner over the case list. |
| `FlakyRV/AgentFlake/agentic/run_agentic_pass_at_k.py` | Repeats one case for pass@k-style evaluation. |
| `FlakyRV/AgentFlake/agentic/run_agentic_od.sh` | OD setup and validation script. |
| `FlakyRV/AgentFlake/agentic/run_agentic_td.sh` | TD setup and validation script. |
| `FlakyRV/AgentFlake/agentic/run_agentic_id.sh` | ID setup and validation script. |
| `FlakyRV/AgentFlake/agentic/run_agentic_nio.sh` | NIO setup and validation script. |
| `FlakyRV/AgentFlake/agentic/run_agentic_unclassified.sh` | Unclassified setup and validation script. |
| `FlakyRV/AgentFlake/agentic/run_agentic_brittle.sh` | Brittle setup and validation script. |
| `FlakyRV/AgentFlake/agentic/agentic_config.py` | Model aliases, API-key defaults, iteration limits, and tool budgets. |
| `FlakyRV/AgentFlake/agentic/agent_tools.py` | Read-only context tools exposed to the repair agent. |
| `FlakyRV/AgentFlake/LLM Scripts/apply_fix.py` | Patch applier used after `submit_patch`. |
| `FlakyRV/AgentFlake/LLM Scripts/assemble_llm_context.py` | Shared CSV, source lookup, method extraction, and failure-log helpers. |
| `FlakyRV/AgentFlake/data/` | Downloaded zips, scratch workspaces, logs, and archived runs. |

## Artifacts and Related Code

| Artifact | Link | Description |
|---|---|---|
| `patches.zip` | `FlakyRV/AgentFlake/patches.zip` | Log of patches from our run over 164 cases. |

## Prerequisites

Install Python 3.9 or newer, Docker, and Git. Docker must be running before
starting an AgentFlake run.

Install Python dependencies:

```bash
cd FlakyRV/AgentFlake
python3 -m pip install -r requirements.txt
```

Set the API key for the provider you run:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

For `--models claude`, only `ANTHROPIC_API_KEY` is required.

## Running One Case

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic.py <case-id> --models claude --runs 1
```

Example:

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic.py oktahookssdkjavahooks9187787createUserTest --models claude --runs 1
```

Useful options:

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic.py <case-id> --models claude --runs 3
python3 run_agentic.py <case-id> --models claude,claude-opus --runs 1
python3 run_agentic.py <case-id> --models claude --runs 1 --max-iterations 5
python3 run_agentic.py <case-id> --models claude --runs 1 --keep-workspace
```

## Running Many Cases

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1
```

Preview commands without running them:

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1 --dry-run
```

Run only selected types:

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1 --types td,id
```

Limit the number of rows:

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1 --limit 10
```

## Case IDs

Case IDs come from `FlakyRV/AgentFlake/test_config.csv`.
To list them:

```bash
cd FlakyRV/AgentFlake
python3 - <<'PY'
import csv
with open("test_config.csv", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        print(row["test_type"], row["result_container"])
PY
```

## Runtime Flow

`FlakyRV/AgentFlake/agentic/run_agentic.py`
reads `FlakyRV/AgentFlake/test_config.csv`,
resolves the requested model, and calls
`FlakyRV/AgentFlake/agentic/run_agentic_pass_at_k.py`.

The pass@k runner chooses a type-specific script based on `test_type`:

| `test_type` | Script |
|---|---|
| `od` | `FlakyRV/AgentFlake/agentic/run_agentic_od.sh` |
| `td` | `FlakyRV/AgentFlake/agentic/run_agentic_td.sh` |
| `id` | `FlakyRV/AgentFlake/agentic/run_agentic_id.sh` |
| `nio` | `FlakyRV/AgentFlake/agentic/run_agentic_nio.sh` |
| `unclassified` / `unassigned` | `FlakyRV/AgentFlake/agentic/run_agentic_unclassified.sh` |
| `brittle` / `britle` | `FlakyRV/AgentFlake/agentic/run_agentic_brittle.sh` |

The type-specific script prepares
`FlakyRV/AgentFlake/data/<case-id>/`,
starts the right Docker image, reproduces the flaky failure, launches the
agentic orchestrator, applies patches through
`FlakyRV/AgentFlake/LLM Scripts/apply_fix.py`,
and verifies the result.

This repository is intentionally trimmed to the current agentic fix/validate
path. Files outside that active runtime path are not included.

## Outputs

Most run artifacts are written under:

```text
FlakyRV/AgentFlake/data/<case-id>/
```

Common files and directories include:

| Path | Purpose |
|---|---|
| `FlakyRV/AgentFlake/data/<case-id>/Steps_Output_Files/agentic_conversation.json` | Tool calls and model turns. |
| `FlakyRV/AgentFlake/data/<case-id>/Steps_Output_Files/agentic_iterations.jsonl` | Per-iteration repair records. |
| `FlakyRV/AgentFlake/data/<case-id>/Steps_Output_Files/llm_response.json` | Last submitted patch payload. |
| `FlakyRV/AgentFlake/data/<case-id>/Steps_Output_Files/apply_report.json` | Patch-application and compile report. |
| `FlakyRV/AgentFlake/data/<case-id>/Steps_Output_Files/verify_after_fix.log` | Verification log. |
| `FlakyRV/AgentFlake/data/<case-id>/Steps_Output_Files/verify_after_fix.verdict` | Final verification status for the last attempt. |
| `FlakyRV/AgentFlake/data/AGENTIC_FULL_RUNS/` | Pass@k run archives. |
