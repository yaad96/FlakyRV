# FlakyRV → LLM Flaky-Test Repair Pipeline

## Goal

Use runtime-verification (RV) traces from a **deterministic-failing** run
and a **deterministic-passing** run of a flaky test as evidence for an
LLM, ask the LLM to generate a patch, apply it, and re-run the test to
verify the fix.

The intuition is that a stack trace alone gives the LLM too little to
localise a flaky-test bug. Diffing the JVM-level event traces of a
known-passing run against a known-failing run highlights the specific
behaviours that diverge — which we feed to the LLM along with the
relevant source code.

## How to run it

1. **Prerequisites**
   - Docker, Python 3, Java + Maven on the host.
   - `pip install anthropic`
   - Set your API key: `export ANTHROPIC_API_KEY=sk-ant-...`
   - The required Docker base images must be built locally (see the
     `Dockerfile*` files in this directory).

2. **Pick a test** from [test_config.csv](test_config.csv) — the
   `result_container` column is the unique key.

3. **Run the orchestrator** for that test's flakiness type:

   ```bash
   # For TD (test-dependency) tests:
   ./TraceMop\ Scripts/run_td_tracemop.sh BOOKKEEPER-846

   # For OD (order-dependent) tests:
   ./TraceMop\ Scripts/run_od_tracemop.sh dubbodubborpcdubborpcapiba89f441
   ```

That's it. The script handles the dataset download, Docker setup,
trace collection, prompt assembly, LLM call, patch application, and
post-fix verification.

## Where the results go

Everything for a given test lands under `data/<result_container>/`.
The headline outputs live in `data/<result_container>/Steps Output Files/`:

- `llm_context.txt` — the prompt sent to the LLM
- `llm_response.json` — the LLM's diagnosis, patch, and structured fix
- `apply_report.json` — whether and how the patch was applied
- `verify_after_fix.verdict` — `PASSED`, `FAILED`, `UNKNOWN`, or `SKIPPED`

Worked examples are available under `data/BOOKKEEPER-846/` (TD) and
`data/dubbodubborpcdubborpcapiba89f441/` (OD).
