#!/usr/bin/env python3
"""
call_llm.py

Sends the assembled LLM context to Anthropic Claude and saves the response.

Usage:
    python call_llm.py <result_container>

Requires:
    - pip install anthropic

Output:
    data/<result_container>/llm_response.json
"""

import json
import os
import re
import sys
import time

try:
    from anthropic import Anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: py -3 -m pip install anthropic", file=sys.stderr)
    sys.exit(1)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Script lives in ReproFlake-C9E6/LLM Scripts/ ; data is one level up.
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16384


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def parse_response(raw):
    """
    Parse the raw LLM response into structured output_a / output_b fields.
    Returns a dict with the parsed structure.
    """
    parsed = {
        "output_0": {"diagnosis": None},
        "output_a": {"patch": None},
        "output_b": {"root_cause": None, "fix_description": None, "fixed_code": []},
    }

    # --- Split into Output 0, Output A, and Output B ---
    # Extract diagnosis (OUTPUT 0), everything between OUTPUT 0 and OUTPUT A
    diag_match = re.search(
        r'OUTPUT\s*0\s*[—–-]\s*DIAGNOSIS:?\s*\n(.*?)(?=OUTPUT\s*A\s*[—–-]\s*PATCH|$)',
        raw, re.DOTALL
    )
    if diag_match:
        parsed["output_0"]["diagnosis"] = diag_match.group(1).strip()

    # Split the response into the OUTPUT A and OUTPUT B sections. We split
    # on the OUTPUT A header first so that OUTPUT A's diff parser cannot
    # accidentally match ```diff or ```java fenced blocks emitted earlier
    # inside OUTPUT 0's reasoning (e.g. an "Original:"/"Replacement:" draft).
    a_split = re.split(r'OUTPUT\s*A\s*[—–-]\s*PATCH:?', raw, maxsplit=1)
    after_a = a_split[1] if len(a_split) > 1 else raw

    b_split = re.split(r'OUTPUT\s*B\s*[—–-]\s*DEVELOPER\s*GUIDE:?', after_a, maxsplit=1)
    a_section = b_split[0] if len(b_split) > 1 else after_a
    b_section = b_split[1] if len(b_split) > 1 else ""

    # --- Parse Output A: extract diff from a ```diff fenced block ---
    # Require the "diff" tag explicitly (no `(?:diff)?`) so plain ```...```
    # blocks (e.g. ```java teaching aids) cannot match. Take the LAST match
    # in the OUTPUT A section as belt-and-suspenders against the LLM emitting
    # a draft + a final.
    diff_matches = re.findall(r'```diff\s*\n(.*?)```', a_section, re.DOTALL)
    if diff_matches:
        parsed["output_a"]["patch"] = diff_matches[-1].strip()
    else:
        # Fallback 1: the LLM forgot the "diff" tag but the body still looks
        # like a unified diff (starts with --- a/ on the next line).
        plain_diff_matches = re.findall(r'```\s*\n(---\s.*?)```', a_section, re.DOTALL)
        if plain_diff_matches:
            parsed["output_a"]["patch"] = plain_diff_matches[-1].strip()
        else:
            # Fallback 2: everything in the OUTPUT A section.
            a_body = a_section.strip()
            if a_body:
                parsed["output_a"]["patch"] = a_body

    # --- Parse Output B: ROOT_CAUSE ---
    rc_match = re.search(r'###\s*ROOT_CAUSE\s*\n(.*?)(?=###\s*FIX_DESCRIPTION|$)', b_section, re.DOTALL)
    if rc_match:
        parsed["output_b"]["root_cause"] = rc_match.group(1).strip()

    # --- Parse Output B: FIX_DESCRIPTION ---
    fd_match = re.search(r'###\s*FIX_DESCRIPTION\s*\n(.*?)(?=###\s*FIXED_CODE|$)', b_section, re.DOTALL)
    if fd_match:
        parsed["output_b"]["fix_description"] = fd_match.group(1).strip()

    # --- Parse Output B: FIXED_CODE blocks ---
    fc_match = re.search(r'###\s*FIXED_CODE\s*\n(.*)', b_section, re.DOTALL)
    if fc_match:
        fc_section = fc_match.group(1)

        # Split on @@FILE: markers
        file_blocks = re.split(r'@@FILE:\s*', fc_section)[1:]  # skip text before first @@FILE

        for block in file_blocks:
            lines = block.split('\n', 1)
            file_path = lines[0].strip()
            rest = lines[1] if len(lines) > 1 else ""

            # Check for @@IMPORTS before the first @@METHOD
            first_method_pos = rest.find('@@METHOD:')
            imports_text = None
            if first_method_pos > 0:
                pre_method = rest[:first_method_pos]
                imp_match = re.search(r'@@IMPORTS:\s*\n(.*?)(?=@@METHOD:|$)', pre_method, re.DOTALL)
                if imp_match:
                    imports_text = imp_match.group(1).strip() or None

            # Extract all @@METHOD blocks within this @@FILE
            method_blocks = re.split(r'@@METHOD:\s*', rest)
            for mb in method_blocks[1:]:  # skip text before first @@METHOD
                mb_lines = mb.split('\n', 1)
                method_name = mb_lines[0].strip()
                mb_rest = mb_lines[1] if len(mb_lines) > 1 else ""

                # @@OPERATION and @@ANCHOR live between @@METHOD and the
                # ```java fence. Both are optional in the parsed output so
                # responses produced before the schema was extended still
                # parse cleanly; the applier should default operation to
                # 'replace_method' when absent.
                op_match = re.search(r'@@OPERATION:\s*([^\n]+)', mb_rest)
                operation = op_match.group(1).strip() if op_match else None

                anchor_match = re.search(r'@@ANCHOR:\s*([^\n]+)', mb_rest)
                anchor = anchor_match.group(1).strip() if anchor_match else None

                code_match = re.search(r'```java\s*\n(.*?)```', mb_rest, re.DOTALL)
                code = code_match.group(1).strip() if code_match else None

                parsed["output_b"]["fixed_code"].append({
                    "file": file_path,
                    "imports": imports_text,
                    "method": method_name,
                    "operation": operation,
                    "anchor": anchor,
                    "code": code,
                })

    return parsed


# ---------------------------------------------------------------------------
# Two-turn driver helpers
# ---------------------------------------------------------------------------
import fetch_artifacts  # local module in this folder


def _extract_text(response) -> str:
    """Concatenate all text blocks from an Anthropic message response."""
    return "".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    )


def _send(client, system_prompt, messages):
    """Single API call with our standard model/max_tokens.

    Note: `temperature` is intentionally omitted. Opus 4.7+ deprecated it
    (extended-thinking models calibrate internally and reject the parameter
    with a 400). Older Sonnet accepted it; default behaviour is fine for
    code-gen tasks. Omitting keeps the call portable across model families.
    """
    return client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )


def _usage_dict(response):
    """Standard usage dict from an Anthropic response."""
    in_tok = response.usage.input_tokens
    out_tok = response.usage.output_tokens
    return {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": in_tok + out_tok,
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
    }


def _sum_usage(*usages):
    """Sum a list of usage dicts (same keys)."""
    keys = ("input_tokens", "output_tokens", "total_tokens",
            "cache_read_input_tokens", "cache_creation_input_tokens")
    return {k: sum(u.get(k, 0) for u in usages) for k in keys}


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <result_container>")
        sys.exit(1)

    result_container = sys.argv[1]
    base = os.path.join(DATA_DIR, result_container)
    steps_dir = os.path.join(base, "Steps Output Files")
    os.makedirs(steps_dir, exist_ok=True)
    context_file = os.path.join(steps_dir, "llm_context.txt")
    output_file = os.path.join(steps_dir, "llm_response.json")
    turn1_path = os.path.join(steps_dir, "llm_response_turn1.json")
    turn2_path = os.path.join(steps_dir, "llm_response_turn2.json")
    artifacts_dump_path = os.path.join(steps_dir, "llm_artifacts_turn2.txt")

    # Stale turn-2 artefacts from a previous multi-turn run would mislead the
    # human auditor if the current run is single-turn. Clear them up front.
    for stale in (turn2_path, artifacts_dump_path):
        if os.path.exists(stale):
            os.remove(stale)

    if not os.path.isfile(context_file):
        print(f"ERROR: {context_file} not found. Run assemble_llm_context.py first.", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        print("Using ANTHROPIC_API_KEY from environment.")
    else:
        api_key = input("Enter your Anthropic API key: ").strip()
        if not api_key:
            print("ERROR: No API key provided.", file=sys.stderr)
            sys.exit(1)
        os.environ["ANTHROPIC_API_KEY"] = api_key
        print("API key stored in environment for this session.")

    with open(context_file, encoding="utf-8") as f:
        context = f.read()

    client = Anthropic(api_key=api_key)

    system_prompt = (
        "You are an expert Java developer specializing in flaky test diagnosis and repair. "
        "You will receive a structured context file containing test metadata, runtime verification "
        "traces, failure output, and source code. Follow the output format instructions exactly, "
        "your response will be parsed by an automated script."
    )

    # ---- TURN 1 ----
    # Mark the bulky context for ephemeral prompt caching so Turn 2 reuses it.
    turn1_user = [
        {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}}
    ]
    messages = [{"role": "user", "content": turn1_user}]

    print(f"[turn 1] Sending context to {MODEL} ({len(context)} chars)...")
    t0 = time.time()
    resp1 = _send(client, system_prompt, messages)
    t1 = time.time()
    text1 = _extract_text(resp1)
    usage1 = _usage_dict(resp1)
    print(f"[turn 1] {t1 - t0:.1f}s, "
          f"in={usage1['input_tokens']} out={usage1['output_tokens']} "
          f"stop={resp1.stop_reason}")

    # Parse the artifact request (if any) before writing turn1 file
    kind, requested = fetch_artifacts.parse_artifact_block(text1)

    # Write turn 1's standalone JSON file
    turn1_dict = {
        "turn": 1,
        "model": MODEL,
        "elapsed_seconds": round(t1 - t0, 2),
        "prompt_source": "llm_context.txt",
        "prompt_chars": len(context),
        "stop_reason": resp1.stop_reason,
        "usage": usage1,
        "response": text1,
        "artifacts_requested_kind": kind,
        "artifacts_requested": requested,
    }
    with open(turn1_path, "w", encoding="utf-8") as f:
        json.dump(turn1_dict, f, indent=2, ensure_ascii=False)

    # ---- TURN 2 (only if the LLM requested artifacts) ----
    final_text = text1
    final_stop_reason = resp1.stop_reason
    final_usage = usage1

    if kind == "LIST" and requested:
        print(f"[turn 1] LLM requested {len(requested)} artifact(s); fetching...")
        results = fetch_artifacts.fetch_artifacts(requested, base)
        for r in results:
            print(f"  - {r['type']:<16} {r['target']}  "
                  f"{'OK' if r['satisfied'] else 'MISS'} "
                  f"({r['size_chars']} chars)")
        artifacts_log = [
            {k: v for k, v in r.items() if k != "content"}
            for r in results
        ]
        # Save the full Turn 2 user-message body for inspection / reproducibility
        turn2_body = fetch_artifacts.format_artifacts_block(results)
        with open(artifacts_dump_path, "w", encoding="utf-8") as f:
            f.write(turn2_body)

        # Append Turn 1's assistant response and Turn 2's user message
        messages.append({"role": "assistant", "content": text1})
        messages.append({"role": "user", "content": turn2_body})

        print(f"[turn 2] Sending artifacts ({len(turn2_body)} chars) and asking for the fix...")
        t2 = time.time()
        resp2 = _send(client, system_prompt, messages)
        t3 = time.time()
        text2 = _extract_text(resp2)
        usage2 = _usage_dict(resp2)
        print(f"[turn 2] {t3 - t2:.1f}s, "
              f"in={usage2['input_tokens']} out={usage2['output_tokens']} "
              f"stop={resp2.stop_reason} "
              f"cache_read={usage2['cache_read_input_tokens']}")

        # Write turn 2's standalone JSON file
        turn2_dict = {
            "turn": 2,
            "model": MODEL,
            "elapsed_seconds": round(t3 - t2, 2),
            "prompt_source": "llm_artifacts_turn2.txt",
            "prompt_chars": len(turn2_body),
            "stop_reason": resp2.stop_reason,
            "usage": usage2,
            "response": text2,
            "artifacts_satisfied": artifacts_log,
        }
        with open(turn2_path, "w", encoding="utf-8") as f:
            json.dump(turn2_dict, f, indent=2, ensure_ascii=False)

        final_text = text2
        final_stop_reason = resp2.stop_reason
        final_usage = _sum_usage(usage1, usage2)

    elif kind == "NONE":
        print("[turn 1] LLM declared NONE — answering directly in turn 1.")
    elif kind == "ABSENT":
        print("[turn 1] No <ARTIFACTS_REQUESTED> block found — treating turn 1 as final answer.")
    else:
        print(f"[turn 1] Unexpected protocol state ({kind}) — treating turn 1 as final answer.")

    elapsed_seconds = round(time.time() - t0, 2)
    turns_taken = 2 if (kind == "LIST" and requested) else 1

    # Canonical result file. Keeps the same top-level shape as before;
    # per-turn raw responses live in the separate llm_response_turn{1,2}.json
    # files so this file stays focused on the parsed final answer.
    result = {
        "model": MODEL,
        "result_container": result_container,
        "elapsed_seconds": elapsed_seconds,
        "turns_taken": turns_taken,
        "artifacts_requested_kind": kind,
        "stop_reason": final_stop_reason,
        "usage": final_usage,
        "raw_response": final_text,
        "response": parse_response(final_text),
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Done in {elapsed_seconds:.1f}s, "
          f"{final_usage['total_tokens']} tokens "
          f"(cached read: {final_usage['cache_read_input_tokens']})")
    print(f"Saved: {output_file}")
    print(f"  + {turn1_path}")
    if turns_taken == 2:
        print(f"  + {turn2_path}")
        print(f"  + {artifacts_dump_path}")


if __name__ == "__main__":
    main()
