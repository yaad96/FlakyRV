#!/usr/bin/env python3
"""Anthropic backend for the agentic repair loop."""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
import time

try:
    from anthropic import Anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: "
          "python3 -m pip install anthropic", file=sys.stderr)
    sys.exit(1)

import agentic_config         # type: ignore  # noqa: E402
import agent_tools            # type: ignore  # noqa: E402
import orchestrator_common as common  # type: ignore  # noqa: E402

DEFAULT_MODEL                = agentic_config.DEFAULT_MODEL
MAX_TOKENS                   = common.MAX_TOKENS
TEMPERATURE                  = common.TEMPERATURE
MAX_TOOL_TURNS_PER_ITERATION = common.MAX_TOOL_TURNS_PER_ITERATION
MAX_ITERATIONS               = common.DEFAULT_MAX_ITERATIONS
TOOL_OUTPUT_MAX_CHARS        = common.TOOL_OUTPUT_MAX_CHARS
VERIFY_PASS_RUNS             = common.VERIFY_PASS_RUNS
SYSTEM_PROMPT                = common.SYSTEM_PROMPT


def is_anthropic_model(model: str) -> bool:
    """True if `model` should be handled by the Anthropic backend."""
    key = (model or "").strip().lower()
    if key in {v.lower() for v in agentic_config.CLAUDE_MODELS.values()}:
        return True
    if key in {k.lower() for k in agentic_config.CLAUDE_MODELS}:
        return True
    return key.startswith("claude")
def _usage_dict(response) -> dict:
    u = response.usage
    return {
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        # Anthropic reports the three input buckets as DISJOINT: input_tokens
        # is the uncached remainder, and the two cache figures are billed on
        # top of it. Summing all four is therefore the real billed total -
        # leaving the cache ones out under-reports a cached run by ~90%.
        "total_tokens": (u.input_tokens + u.output_tokens
                         + (getattr(u, "cache_read_input_tokens", 0) or 0)
                         + (getattr(u, "cache_creation_input_tokens", 0) or 0)),
        "cache_read_input_tokens":
            getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens":
            getattr(u, "cache_creation_input_tokens", 0) or 0,
    }


def _extract_assistant_blocks(response):
    """Return the assistant's content blocks as plain dicts suitable to
    append back into the running messages list."""
    out = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            out.append({"type": "text", "text": block.text})
        elif getattr(block, "type", None) == "tool_use":
            out.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return out


# --- prompt caching -------------------------------------------------------
# The loop resends the whole conversation on every tool turn, so input is
# ~96% of token spend. Anthropic caches by prefix (render order: tools ->
# system -> messages), but only at an explicit cache_control breakpoint, so
# without the markers below nothing is ever reused and every turn re-reads
# the full history at full price.

SYSTEM_PROMPT_CACHED = [{
    "type": "text",
    "text": SYSTEM_PROMPT,
    "cache_control": {"type": "ephemeral"},
}]


def _with_breakpoint(msg: dict) -> dict:
    """Copy of `msg` whose final content block carries a cache breakpoint."""
    content = msg["content"]
    blocks = ([{"type": "text", "text": content}]
              if isinstance(content, str) else list(content))
    if not blocks:
        return msg
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return {**msg, "content": blocks}


def _cached_messages(messages: list[dict], rolling: int = 2) -> list[dict]:
    """`messages` with rolling cache breakpoints on the newest turns.

    Two breakpoints (plus the one on `system`) stay inside Anthropic's cap of
    four and let a turn still read the previous turn's entry when the newest
    block is not yet warm. The originals are left untouched so the archived
    conversation stays free of cache metadata.
    """
    if not messages:
        return messages
    out = list(messages)
    for i in range(max(0, len(out) - rolling), len(out)):
        out[i] = _with_breakpoint(out[i])
    return out


def run(args: argparse.Namespace) -> None:
    ctx = common.prepare_run(args)

    # Read the key from .anthropic_api_key only. No env-var or module fallback,
    # so the key in use is always the one in that file.
    api_key = agentic_config.anthropic_api_key()

    client = Anthropic(api_key=api_key)
    supports_temperature = (
        "temperature" in inspect.signature(client.messages.create).parameters
    )
    excluded_tools = {t.strip() for t in args.exclude_tools.split(",") if t.strip()}
    tools = [t for t in common.all_tool_schemas()
             if t["name"] not in excluded_tools]
    if excluded_tools:
        print(f"[init ] excluded tools: {sorted(excluded_tools)}")

    messages = [{"role": "user", "content": ctx.initial_user}]

    cumulative_usage = common.zero_usage()
    total_elapsed = 0.0
    submit_attempts = 0
    final_verdict = "INCOMPLETE"
    final_category = ""
    iter_summary_rows: list[dict] = []

    print(f"[init ] container={args.container}  test_type={ctx.test_type}  "
          f"provider=anthropic  model={args.model}  "
          f"max_iterations={MAX_ITERATIONS}")

    for attempt in range(1, MAX_ITERATIONS + 1):
        print(f"\n[iter {attempt}/{MAX_ITERATIONS}] ============")
        t_iter_start = time.time()
        iter_start_usage = dict(cumulative_usage)
        tool_turn = 0
        submitted_this_iter = False
        tools_used_this_iter: list[str] = []

        max_context_tools = max(0, MAX_TOOL_TURNS_PER_ITERATION - 1)
        while tool_turn < MAX_TOOL_TURNS_PER_ITERATION:
            tool_turn += 1
            t0 = time.time()
            force_submit = (
                tool_turn == MAX_TOOL_TURNS_PER_ITERATION
                or len(tools_used_this_iter) >= max_context_tools
            )
            create_kwargs = {
                "model": args.model,
                "max_tokens": MAX_TOKENS,
                "system": SYSTEM_PROMPT_CACHED,
                # Tools render first in the cache prefix, so the list must stay
                # byte-identical across turns; tool_choice below is what forces
                # the submit, and narrowing `tools` too would invalidate the
                # whole prefix on the longest turn of the iteration.
                "tools": tools,
                "messages": _cached_messages(messages),
            }
            if supports_temperature:
                create_kwargs["temperature"] = TEMPERATURE
            if force_submit:
                create_kwargs["tool_choice"] = {
                    "type": "tool",
                    "name": "submit_patch",
                }
            response = client.messages.create(**create_kwargs)
            elapsed = time.time() - t0
            total_elapsed += elapsed
            usage = _usage_dict(response)
            cumulative_usage = common.sum_usage(cumulative_usage, usage)

            print(f"[iter {attempt}/turn {tool_turn}] {elapsed:.1f}s  "
                  f"in={usage['input_tokens']} out={usage['output_tokens']}  "
                  f"cache_read={usage['cache_read_input_tokens']}  "
                  f"stop={response.stop_reason}")

            assistant_blocks = _extract_assistant_blocks(response)
            messages.append({"role": "assistant", "content": assistant_blocks})

            tool_uses = [b for b in assistant_blocks if b["type"] == "tool_use"]
            if not tool_uses:
                print(f"[iter {attempt}] assistant returned no tool calls; "
                      f"ending iteration with no submit_patch.")
                break

            # Anthropic requires a result for every tool_use in a turn.
            submit_tu = next(
                (tu for tu in tool_uses if tu["name"] == "submit_patch"), None)

            if submit_tu is None:
                tool_results_block: list[dict] = []
                for tu in tool_uses:
                    if len(tools_used_this_iter) >= max_context_tools:
                        tool_results_block.append({
                            "type": "tool_result",
                            "tool_use_id": tu["id"],
                            "content": (
                                "(skipped: context-tool budget exhausted; "
                                "submit_patch is now required)"
                            ),
                            "is_error": True,
                        })
                        continue
                    tools_used_this_iter.append(tu["name"])
                    tool_args = tu["input"] or {}
                    result_text = agent_tools.dispatch_tool(
                        args.container, tu["name"], tool_args)
                    if (agent_tools.should_truncate_tool_output(tu["name"], tool_args)
                            and len(result_text) > TOOL_OUTPUT_MAX_CHARS):
                        result_text = (
                            result_text[:TOOL_OUTPUT_MAX_CHARS]
                            + f"\n\n(tool output truncated at "
                              f"{TOOL_OUTPUT_MAX_CHARS} chars)\n")
                    tool_results_block.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": result_text,
                    })
                remaining = MAX_TOOL_TURNS_PER_ITERATION - tool_turn
                if remaining <= 3:
                    nudge = (
                        f"\n[SYSTEM] WARNING: you have {remaining} tool "
                        f"turn(s) left in this iteration (cap = "
                        f"{MAX_TOOL_TURNS_PER_ITERATION}). You MUST call "
                        f"submit_patch within the next {remaining} turn(s) "
                        f"or this iteration will be abandoned as INCOMPLETE. "
                        f"Commit to your best fix now."
                    )
                    tool_results_block.append({"type": "text", "text": nudge})
                messages.append({"role": "user", "content": tool_results_block})
                continue

            submit_args = submit_tu["input"] or {}
            submit_tool_use_id = submit_tu["id"]
            other_results: list[dict] = [
                {"type": "tool_result", "tool_use_id": tu["id"],
                 "content": "(skipped: a submit_patch in the same turn "
                            "supersedes this call)"}
                for tu in tool_uses if tu["id"] != submit_tu["id"]
            ]
            submit_attempts += 1
            submitted_this_iter = True
            print(f"[iter {attempt}] submit_patch received "
                  f"({len(submit_args.get('patch') or '')} char diff, "
                  f"{len(submit_args.get('fixed_code') or [])} fixed_code entries)")

            common.write_llm_response_json(ctx.steps_dir, args.container,
                                           submit_args, attempt, model=args.model)

            apply_report = common.run_apply_fix(args.container, ctx.docker_container)
            applied_ok = bool((apply_report.get("result") or {}).get("ok"))
            ready_to_verify = applied_ok and common.compile_confirmed(apply_report)

            verdict = "FAILED"
            verify_tail = ""
            if ready_to_verify:
                verdict, verify_tail = common.run_verify(
                    args.container, ctx.docker_container)
            else:
                (ctx.steps_dir / "verify_after_fix.verdict").write_text(
                    "FAILED\n", encoding="utf-8")

            final_category = common.classify_failure(apply_report, verdict)

            confirm_runs: list[dict] = []
            if verdict == "PASSED":
                for confirm_num in range(1, VERIFY_PASS_RUNS + 1):
                    c_verdict, c_tail = common.run_verify(
                        args.container, ctx.docker_container)
                    confirm_runs.append({"run": confirm_num, "verdict": c_verdict})
                    print(f"[confirm {confirm_num}/{VERIFY_PASS_RUNS}] {c_verdict}")
                    if c_verdict != "PASSED":
                        verdict = c_verdict
                        verify_tail = c_tail
                        final_category = common.classify_failure(apply_report, verdict)
                        break

            iter_elapsed = round(time.time() - t_iter_start, 2)
            iter_delta = {
                k: cumulative_usage.get(k, 0) - iter_start_usage.get(k, 0)
                for k in cumulative_usage
            }
            iter_row = {
                "iteration": attempt,
                "tool_turns": tool_turn,
                "tools_used": tools_used_this_iter,
                "verdict": verdict,
                "category": final_category,
                "applied_ok": applied_ok,
                "elapsed_seconds": iter_elapsed,
                "confirm_runs": confirm_runs,
                "tokens_in":  iter_delta.get("input_tokens", 0),
                "tokens_out": iter_delta.get("output_tokens", 0),
                "cache_read_tokens":  iter_delta.get("cache_read_input_tokens", 0),
                "cache_write_tokens": iter_delta.get("cache_creation_input_tokens", 0),
                "max_iters":  MAX_ITERATIONS,
            }
            with open(ctx.iter_log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(iter_row) + "\n")
            iter_summary_rows.append(iter_row)

            if verdict == "PASSED":
                final_verdict = "PASSED"
                messages.append({
                    "role": "user",
                    "content": other_results + [{
                        "type": "tool_result",
                        "tool_use_id": submit_tool_use_id,
                        "content": (
                            f"=== submit_patch attempt result: PASSED ===\n"
                            f"The test passes in the initial run and all "
                            f"{VERIFY_PASS_RUNS} confirmation runs. "
                            f"Repair confirmed successful."),
                    }],
                })
                break

            common.restore_flaky(ctx.base, ctx.docker_container)
            if confirm_runs:
                confirm_summary = "\n".join(
                    f"  run {r['run']}: {r['verdict']}" for r in confirm_runs)
                failure_report = (
                    f"=== submit_patch attempt result: CONFIRM_FAILED ===\n"
                    f"category:        confirm_failed\n"
                    f"verdict:         {verdict}\n"
                    f"The patch passed the first verification run but failed "
                    f"in a subsequent confirmation run — the fix is still "
                    f"non-deterministic.\n\n"
                    f"Confirmation runs ({VERIFY_PASS_RUNS} total):\n"
                    f"{confirm_summary}\n"
                    f"\n--- last failing verify log ---\n"
                    f"{verify_tail.rstrip()}\n"
                    f"\nFlaky/ has been restored to its pre-patch state. "
                    f"The fix does not pass consistently. Re-examine the "
                    f"root cause and submit a more robust patch.\n"
                ) + common.restrategy_hint("confirm_failed")
            else:
                failure_report = common.format_failure_report(
                    apply_report, verdict, verify_tail)

            print(f"[iter {attempt}] verdict={verdict} "
                  f"category={final_category} — feeding failure back to agent.")
            messages.append({
                "role": "user",
                "content": other_results + [{
                    "type": "tool_result",
                    "tool_use_id": submit_tool_use_id,
                    "content": failure_report,
                    "is_error": True,
                }],
            })
            break  # advance to next attempt

        if final_verdict == "PASSED":
            break

        common.save_conversation(ctx.conv_path, args.model, messages,
                                 provider="anthropic", system=SYSTEM_PROMPT)

        if not submitted_this_iter:
            print(f"[iter {attempt}] no submit_patch this iteration; aborting.")
            break

    code = common.finalize_run(
        ctx=ctx, container=args.container, model=args.model,
        provider="anthropic", messages=messages, system=SYSTEM_PROMPT,
        final_verdict=final_verdict, final_category=final_category,
        submit_attempts=submit_attempts, total_elapsed=total_elapsed,
        cumulative_usage=cumulative_usage, iter_summary_rows=iter_summary_rows,
        max_iters=MAX_ITERATIONS)
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("container")
    ap.add_argument("--docker-container",
                    help="docker container name (default tm_<container>)")
    # No --max-iterations flag: agentic_config.MAX_ITERATIONS is the single
    # place the cap is set, so every entry point runs the same budget.
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"Anthropic model ID or alias (default: {DEFAULT_MODEL})")
    ap.add_argument("--exclude-tools", default="",
                    help="comma-separated tool names to remove from the "
                         "agent's toolset (e.g. get_flaky_example for "
                         "unclassified tests)")
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
