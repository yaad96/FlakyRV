# Agentic Flaky-Test Repair

This directory contains the active AgentFlake runner.

Normal entry point:

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic.py <container> --models claude --runs 1
```

Example:

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic.py oktahookssdkjavahooks9187787createUserTest --models claude --runs 1
```

## Prerequisites

Install dependencies:

```bash
cd FlakyRV/AgentFlake
python3 -m pip install -r requirements.txt
```

Set the key for the provider you run:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
```

Docker must be running. If a required image is missing, the per-type script
builds it from one of the Dockerfiles in
`FlakyRV/AgentFlake/`.

## Supported Types

| CSV `test_type` | Script invoked |
|---|---|
| `od` | `FlakyRV/AgentFlake/agentic/run_agentic_od.sh` |
| `td` | `FlakyRV/AgentFlake/agentic/run_agentic_td.sh` |
| `id` | `FlakyRV/AgentFlake/agentic/run_agentic_id.sh` |
| `nio` | `FlakyRV/AgentFlake/agentic/run_agentic_nio.sh` |
| `unclassified` / `unassigned` | `FlakyRV/AgentFlake/agentic/run_agentic_unclassified.sh` |
| `brittle` / `britle` | `FlakyRV/AgentFlake/agentic/run_agentic_brittle.sh` |

## Runtime Flow

1. `FlakyRV/AgentFlake/agentic/run_agentic.py`
   reads `FlakyRV/AgentFlake/test_config.csv`,
   resolves model aliases, and calls
   `FlakyRV/AgentFlake/agentic/run_agentic_pass_at_k.py`.
2. `FlakyRV/AgentFlake/agentic/run_agentic_pass_at_k.py`
   runs the matching per-type shell script once per requested run.
3. The per-type script prepares
   `FlakyRV/AgentFlake/data/<container>/`,
   starts Docker, reproduces the flaky failure, snapshots `Flaky/` to
   `Flaky.pristine`, and launches
   `FlakyRV/AgentFlake/agentic/agentic_orchestrator.py`.
4. The orchestrator exposes read-only context tools from
   `FlakyRV/AgentFlake/agentic/agent_tools.py`.
5. The model calls `submit_patch`; the orchestrator writes `llm_response.json`,
   applies it through
   `FlakyRV/AgentFlake/LLM Scripts/apply_fix.py`,
   recompiles, and runs
   `FlakyRV/AgentFlake/agentic/agentic_verify.py`.
6. On failure, `Flaky/` is restored from `Flaky.pristine` and the agent can try
   again until `MAX_ITERATIONS` is reached.

## Useful Commands

```bash
cd FlakyRV/AgentFlake/agentic
python3 run_agentic.py <container> --models claude --runs 3
python3 run_agentic.py <container> --models claude,claude-opus --runs 1
python3 run_agentic.py <container> --models claude --runs 1 --max-iterations 5
python3 run_agentic.py <container> --models claude --runs 1 --keep-workspace
python3 run_agentic_bulk.py --models claude --runs 1 --dry-run
```

## Outputs

Run artifacts are written under:

```text
FlakyRV/AgentFlake/data/<container>/Steps_Output_Files/
```

Common files:

| File | Description |
|---|---|
| `FlakyRV/AgentFlake/data/<container>/Steps_Output_Files/agentic_conversation.json` | Full model/tool transcript. |
| `FlakyRV/AgentFlake/data/<container>/Steps_Output_Files/agentic_iterations.jsonl` | One JSON line per patch attempt. |
| `FlakyRV/AgentFlake/data/<container>/Steps_Output_Files/llm_response.json` | Last `submit_patch` payload. |
| `FlakyRV/AgentFlake/data/<container>/Steps_Output_Files/apply_report.json` | Patch application and compile report. |
| `FlakyRV/AgentFlake/data/<container>/Steps_Output_Files/verify_after_fix.log` | Raw Maven verification output. |
| `FlakyRV/AgentFlake/data/<container>/Steps_Output_Files/verify_after_fix.verdict` | `PASSED`, `FAILED`, or `INCOMPLETE`. |
