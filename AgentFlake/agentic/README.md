# Agentic Flaky-Test Repair

This directory contains the active AgentFlake runner. Paths below are written
from the repository root, starting with `AgentFlake/`.

## Run One Case

```bash
cd AgentFlake/agentic
python3 run_agentic.py oktahookssdkjavahooks9187787createUserTest --models claude --runs 1
```

Use a different case ID with the same command shape:

```bash
cd AgentFlake/agentic
python3 run_agentic.py <case-id> --models claude --runs 1
```

## Run Bulk Cases

```bash
cd AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1
```

Preview a bulk run without executing cases:

```bash
cd AgentFlake/agentic
python3 run_agentic_bulk.py --models claude --runs 1 --dry-run
```

## Prerequisites

Install dependencies:

```bash
cd AgentFlake
python3 -m pip install -r requirements.txt
```

Set the key for the provider you run:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
```

Docker must be running. If a required image is missing, the per-type script
builds it from one of the Dockerfiles in `AgentFlake/`.

## Supported Types

| CSV `test_type` | Script invoked |
|---|---|
| `od` | `AgentFlake/agentic/run_agentic_od.sh` |
| `td` | `AgentFlake/agentic/run_agentic_td.sh` |
| `id` | `AgentFlake/agentic/run_agentic_id.sh` |
| `nio` | `AgentFlake/agentic/run_agentic_nio.sh` |
| `unclassified` / `unassigned` | `AgentFlake/agentic/run_agentic_unclassified.sh` |
| `brittle` / `britle` | `AgentFlake/agentic/run_agentic_brittle.sh` |

## Important Files

| Path | Purpose |
|---|---|
| `AgentFlake/agentic/run_agentic.py` | Main command for one case; reads the CSV and starts the pass@k runner. |
| `AgentFlake/agentic/run_agentic_bulk.py` | Runs many CSV rows in order. |
| `AgentFlake/agentic/run_agentic_pass_at_k.py` | Runs one case multiple times and archives each attempt. |
| `AgentFlake/agentic/agentic_orchestrator.py` | Chooses the Anthropic or OpenAI backend for the repair loop. |
| `AgentFlake/agentic/agent_tools.py` | Tools the LLM uses to inspect tests, source files, logs, and examples. |
| `AgentFlake/agentic/agentic_verify.py` | Re-runs validation after a patch is applied. |
| `AgentFlake/LLM Scripts/apply_fix.py` | Applies the patch and writes patch/compile results. |
| `AgentFlake/LLM Scripts/assemble_llm_context.py` | Shared source-code and log-extraction helpers. |

## Outputs

Run artifacts are written under:

```text
AgentFlake/data/<container>/Steps_Output_Files/
```

Pass@k archives are written under:

```text
AgentFlake/data/AGENTIC_FULL_RUNS/<container>_runs/
```
