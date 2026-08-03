#!/usr/bin/env python3
"""
Collect the selected final patch and original flaky files for each completed
agentic container run.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_RUNS_DIR = DEFAULT_DATA_DIR / "AGENTIC_FULL_RUNS"
DEFAULT_OUTPUT_DIR = DEFAULT_DATA_DIR / "AGENTIC_FINAL_PATCHES"


@dataclass(frozen=True)
class Candidate:
    container: str
    test_type: str
    model: str
    run: int
    verdict: str
    fail_category: str
    run_dir: Path
    patch_path: Path
    patch_source: str
    summary: dict[str, str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect final patches and flaky source files from AGENTIC_FULL_RUNS."
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=DEFAULT_RUNS_DIR,
        help=f"Directory containing *_runs folders. Default: {DEFAULT_RUNS_DIR}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory. Default: {DEFAULT_OUTPUT_DIR}",
    )
    return parser.parse_args()


def run_number(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def is_completed(run_dir: Path) -> bool:
    return (run_dir / ".run_complete").exists()


def fixed_code_from_value(value: object) -> list[object]:
    if not isinstance(value, dict):
        return []
    fixed_code = value.get("fixed_code")
    if isinstance(fixed_code, list):
        return fixed_code
    return []


def extract_llm_response_patch(run_dir: Path, output_patch: Path) -> bool:
    response_path = run_dir / "Steps_Output_Files" / "llm_response.json"
    if not response_path.is_file():
        return False

    try:
        response = json.loads(response_path.read_text(errors="replace"))
    except (OSError, json.JSONDecodeError):
        return False

    patch_text = ""
    fixed_code: list[object] = []
    raw_response = response.get("raw_response")
    if isinstance(raw_response, str):
        try:
            raw_data = json.loads(raw_response)
            if isinstance(raw_data, dict):
                patch_value = raw_data.get("patch", "")
                if isinstance(patch_value, str):
                    patch_text = patch_value
                fixed_code = fixed_code_from_value(raw_data)
        except json.JSONDecodeError:
            patch_text = ""

    response_outputs = response.get("response")
    if isinstance(response_outputs, dict):
        for value in response["response"].values():
            if not isinstance(value, dict):
                continue
            if not patch_text and isinstance(value.get("patch"), str):
                patch_text = value["patch"]
            if not fixed_code:
                fixed_code = fixed_code_from_value(value)

    if not patch_text.strip() and not fixed_code:
        return False

    if patch_text.strip():
        output_text = patch_text.rstrip() + "\n"
    else:
        output_text = "# --- NO_AGENT_SUBMITTED_UNIFIED_DIFF ---\n"
    if fixed_code:
        output_text += (
            "\n"
            "# --- AGENT_SUBMITTED_FIXED_CODE_JSON ---\n"
            f"{json.dumps(fixed_code, indent=2, sort_keys=True)}\n"
        )

    output_patch.parent.mkdir(parents=True, exist_ok=True)
    output_patch.write_text(output_text, errors="replace")
    return True


def clean_patch_path(value: str) -> Path | None:
    path_text = value.strip().split("\t", 1)[0].split(" ", 1)[0]
    if not path_text or path_text == "/dev/null":
        return None
    for prefix in ("a/", "b/"):
        if path_text.startswith(prefix):
            path_text = path_text[len(prefix):]
    if path_text.startswith("Flaky/"):
        path_text = path_text[len("Flaky/"):]
    path = Path(path_text)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path


def extract_context_test_code(run_dir: Path) -> str:
    context_path = run_dir / "Steps_Output_Files" / "llm_context.txt"
    try:
        text = context_path.read_text(errors="replace")
    except OSError:
        return ""

    start_marker = "=== TEST CODE ==="
    end_markers = (
        "=== INITIAL FAILURE LOG ===",
        "=== HOW TO PROCEED ===",
    )
    if start_marker not in text:
        return ""

    test_code = text.split(start_marker, 1)[1]
    for marker in end_markers:
        if marker in test_code:
            test_code = test_code.split(marker, 1)[0]
            break
    return test_code.strip()


def original_patch_context(patch_path: Path) -> str:
    try:
        lines = patch_path.read_text(errors="replace").splitlines()
    except OSError:
        return ""

    output_lines: list[str] = []
    current_file: Path | None = None
    in_hunk = False

    for line in lines:
        if line == "# --- AGENT_SUBMITTED_FIXED_CODE_JSON ---":
            break
        if line.startswith("--- "):
            path = clean_patch_path(line[4:])
            current_file = path
            in_hunk = False
            if path is not None:
                if output_lines:
                    output_lines.append("")
                output_lines.append(f"# File: {path.as_posix()}")
            continue
        if line.startswith("+++ "):
            continue
        if line.startswith("@@"):
            in_hunk = current_file is not None
            if in_hunk:
                output_lines.append(line)
            continue
        if not in_hunk:
            continue
        if line.startswith("+"):
            continue
        if line.startswith("-") or line.startswith(" "):
            output_lines.append(line[1:])
        elif line.startswith("\\"):
            output_lines.append(line)

    return "\n".join(output_lines).rstrip()


def write_flaky_code(candidate: Candidate, output_path: Path) -> bool:
    sections: list[str] = []
    test_code = extract_context_test_code(candidate.run_dir)
    patch_context = original_patch_context(candidate.patch_path)

    if test_code:
        sections.extend(["# === FLAKY/RELATED TEST CODE ===", test_code])
    if patch_context:
        sections.extend(["# === ORIGINAL PATCH CONTEXT ===", patch_context])

    if not sections:
        return False

    output_path.write_text("\n\n".join(sections).rstrip() + "\n", errors="replace")
    return True


def collect_tool_usage(run_dir: Path) -> Counter[str]:
    conversation_path = run_dir / "Steps_Output_Files" / "agentic_conversation.json"
    try:
        conversation = json.loads(conversation_path.read_text(errors="replace"))
    except (OSError, json.JSONDecodeError):
        conversation = {}

    tool_counts: Counter[str] = Counter()
    messages = conversation.get("messages", [])
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict) or message.get("role") != "assistant":
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict) or item.get("type") != "tool_use":
                    continue
                name = item.get("name")
                if isinstance(name, str) and name:
                    tool_counts[name] += 1

    if tool_counts:
        return tool_counts

    iterations_path = run_dir / "Steps_Output_Files" / "agentic_iterations.jsonl"
    try:
        lines = iterations_path.read_text(errors="replace").splitlines()
    except OSError:
        return tool_counts
    for line in lines:
        try:
            iteration = json.loads(line)
        except json.JSONDecodeError:
            continue
        for name in iteration.get("tools_used", []):
            if isinstance(name, str) and name:
                tool_counts[name] += 1
    return tool_counts


def patch_for_run(run_dir: Path, temp_dir: Path) -> tuple[Path | None, str]:
    submitted_patch = temp_dir / f"{run_dir.parent.parent.name}_{run_dir.parent.name}_{run_dir.name}_llm_response.patch"
    if extract_llm_response_patch(run_dir, submitted_patch):
        return submitted_patch, "llm_response_patch"

    return None, ""


def load_candidates(runs_dir: Path, temp_dir: Path) -> list[Candidate]:
    candidates: list[Candidate] = []
    for summary_path in sorted(runs_dir.glob("*_runs/summary.csv")):
        with summary_path.open(newline="", errors="replace") as csv_file:
            for row in csv.DictReader(csv_file):
                model = row.get("model", "")
                run = run_number(row.get("run", ""))
                if not model or run < 0:
                    continue

                verdict = row.get("verdict", "").upper()
                if verdict not in {"PASSED", "FAILED"}:
                    continue

                run_dir = summary_path.parent / model / f"run_{run}"
                if not is_completed(run_dir):
                    continue

                patch_path, patch_source = patch_for_run(run_dir, temp_dir)
                if patch_path is None:
                    continue

                candidates.append(
                    Candidate(
                        container=row.get("container", summary_path.parent.name.removesuffix("_runs")),
                        test_type=row.get("test_type", ""),
                        model=model,
                        run=run,
                        verdict=verdict,
                        fail_category=row.get("fail_category", ""),
                        run_dir=run_dir,
                        patch_path=patch_path,
                        patch_source=patch_source,
                        summary=dict(row),
                    )
                )
    return candidates


def choose_final_runs(candidates: Iterable[Candidate]) -> dict[str, Candidate]:
    grouped: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.container, []).append(candidate)

    selected: dict[str, Candidate] = {}
    for container, items in grouped.items():
        passed = [item for item in items if item.verdict == "PASSED"]
        pool = passed or items
        selected[container] = max(
            pool,
            key=lambda item: (
                item.run,
                item.patch_path.stat().st_mtime,
                item.model,
            ),
        )
    return selected


def type_directory_name(test_type: str) -> str:
    normalized = test_type.strip().lower()
    if not normalized:
        return "unknown"
    return "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in normalized
    )


def integer_summary_value(summary: dict[str, str], field: str) -> int:
    try:
        return int(summary.get(field, "") or 0)
    except ValueError:
        return 0


def write_type_summary(type_dir: Path, rows: list[dict[str, object]]) -> None:
    tool_names = sorted(
        {
            name
            for row in rows
            for name in row["tool_counts"]  # type: ignore[index]
        }
    )
    fieldnames = [
        "container",
        "test_type",
        "model",
        "selected_run",
        "verdict",
        "fail_category",
        "agentic_iterations",
        "input_tokens_total",
        "output_tokens_total",
        "total_tokens",
        "elapsed_llm_seconds",
        "elapsed_total_seconds",
        "tool_calls_total",
        "unique_tools_used",
        "tool_breakdown",
        "patch_source",
        "output_patch",
        "flaky_code",
    ] + [f"tool_{name}" for name in tool_names]

    with (type_dir / "summary.csv").open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(rows, key=lambda item: str(item["container"])):
            tool_counts: Counter[str] = row.pop("tool_counts")  # type: ignore[assignment]
            csv_row = dict(row)
            csv_row["tool_breakdown"] = json.dumps(dict(sorted(tool_counts.items())))
            for name in tool_names:
                csv_row[f"tool_{name}"] = tool_counts[name]
            writer.writerow(csv_row)


def write_outputs(selected: dict[str, Candidate], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    summaries_by_type: dict[str, list[dict[str, object]]] = {}

    for container, candidate in sorted(selected.items()):
        type_name = type_directory_name(candidate.test_type)
        type_dir = output_dir / type_name
        container_dir = type_dir / container
        container_dir.mkdir(parents=True, exist_ok=True)
        patch_output = container_dir / "final.patch"
        flaky_code_output = container_dir / "flaky_code.txt"
        shutil.copyfile(candidate.patch_path, patch_output)
        has_flaky_code = write_flaky_code(candidate, flaky_code_output)
        tool_counts = collect_tool_usage(candidate.run_dir)

        metadata = {
            "container": candidate.container,
            "test_type": candidate.test_type,
            "model": candidate.model,
            "run": candidate.run,
            "verdict": candidate.verdict,
            "fail_category": candidate.fail_category,
            "source_run_dir": str(candidate.run_dir),
            "source_patch": str(candidate.patch_path),
            "patch_source": candidate.patch_source,
            "generated_from_flaky_fixed_dirs": candidate.patch_source == "generated_tree_diff",
            "output_patch": str(patch_output),
            "flaky_code": str(flaky_code_output) if has_flaky_code else "",
            "tool_calls_total": sum(tool_counts.values()),
            "unique_tools_used": len(tool_counts),
            "tool_breakdown": dict(sorted(tool_counts.items())),
        }
        (container_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n"
        )
        manifest.append(metadata)
        summaries_by_type.setdefault(type_name, []).append(
            {
                "container": candidate.container,
                "test_type": candidate.test_type,
                "model": candidate.model,
                "selected_run": candidate.run,
                "verdict": candidate.verdict,
                "fail_category": candidate.fail_category,
                "agentic_iterations": integer_summary_value(
                    candidate.summary, "agentic_iterations"
                ),
                "input_tokens_total": integer_summary_value(
                    candidate.summary, "input_tokens_total"
                ),
                "output_tokens_total": integer_summary_value(
                    candidate.summary, "output_tokens_total"
                ),
                "total_tokens": integer_summary_value(candidate.summary, "total_tokens"),
                "elapsed_llm_seconds": candidate.summary.get("elapsed_llm_seconds", ""),
                "elapsed_total_seconds": candidate.summary.get("elapsed_total_seconds", ""),
                "tool_calls_total": sum(tool_counts.values()),
                "unique_tools_used": len(tool_counts),
                "tool_counts": tool_counts,
                "patch_source": candidate.patch_source,
                "output_patch": str(patch_output),
                "flaky_code": str(flaky_code_output) if has_flaky_code else "",
            }
        )

    for type_name, rows in summaries_by_type.items():
        write_type_summary(output_dir / type_name, rows)

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


def main() -> int:
    args = parse_args()
    runs_dir = args.runs_dir.resolve()
    output_dir = args.output_dir.resolve()

    if not runs_dir.is_dir():
        raise SystemExit(f"Runs directory not found: {runs_dir}")

    if output_dir.exists():
        shutil.rmtree(output_dir)

    temp_dir = output_dir / ".generated_patch_cache"
    temp_dir.mkdir(parents=True, exist_ok=True)

    candidates = load_candidates(runs_dir, temp_dir)
    selected = choose_final_runs(candidates)
    write_outputs(selected, output_dir)

    passed = sum(1 for item in selected.values() if item.verdict == "PASSED")
    failed = len(selected) - passed
    print(f"Wrote {len(selected)} container patches to {output_dir}")
    print(f"Selected passed runs: {passed}")
    print(f"Selected failed/latest runs: {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
