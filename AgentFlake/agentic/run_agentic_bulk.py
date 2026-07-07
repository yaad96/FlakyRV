#!/usr/bin/env python3
"""Run AgentFlake cases from test_config.csv in row order."""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
AGENTFLAKE_DIR = SCRIPT_DIR.parent
CSV_FILE = AGENTFLAKE_DIR / "test_config.csv"
RUN_AGENTIC = SCRIPT_DIR / "run_agentic.py"


def load_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.is_file():
        sys.exit(f"ERROR: CSV not found: {csv_path}")

    rows: list[dict[str, str]] = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if "result_container" not in (reader.fieldnames or []):
            sys.exit(f"ERROR: CSV has no result_container column: {csv_path}")
        for row in reader:
            container = (row.get("result_container") or "").strip()
            if container:
                rows.append(row)
    return rows


def select_rows(rows: list[dict[str, str]], args: argparse.Namespace) -> list[dict[str, str]]:
    selected = rows

    if args.types:
        allowed = {t.strip().lower() for t in args.types.split(",") if t.strip()}
        selected = [
            row for row in selected
            if (row.get("test_type") or "").strip().lower() in allowed
        ]

    if args.start_from:
        start = args.start_from.strip()
        for idx, row in enumerate(selected):
            if (row.get("result_container") or "").strip() == start:
                selected = selected[idx:]
                break
        else:
            sys.exit(f"ERROR: --start-from container not found after filters: {start}")

    if args.limit is not None:
        selected = selected[:args.limit]

    return selected


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run agentic repair for every row in test_config.csv, in order.",
    )
    ap.add_argument("--csv", default=str(CSV_FILE),
                    help=f"path to test_config.csv (default: {CSV_FILE})")
    ap.add_argument("--models", default="claude",
                    help="comma-separated model names/IDs passed to run_agentic.py "
                         "(default: claude)")
    ap.add_argument("--runs", type=int, default=1,
                    help="independent runs per model for each container (default: 1)")
    ap.add_argument("--max-iterations", type=int,
                    help="optional patch-attempt cap passed to run_agentic.py")
    ap.add_argument("--keep-workspace", action="store_true",
                    help="pass --keep-workspace to run_agentic.py")
    ap.add_argument("--types",
                    help="optional comma-separated test_type filter, e.g. td,id,nio")
    ap.add_argument("--start-from",
                    help="start at this result_container, preserving CSV order")
    ap.add_argument("--limit", type=int,
                    help="run at most this many selected rows")
    ap.add_argument("--stop-on-failure", action="store_true",
                    help="stop the bulk run after the first failed container")
    ap.add_argument("--dry-run", action="store_true",
                    help="print selected commands without running them")
    args = ap.parse_args()

    rows = load_rows(Path(args.csv))
    selected = select_rows(rows, args)

    if not selected:
        sys.exit("ERROR: no rows selected")

    print(f"[bulk] csv       = {Path(args.csv).resolve()}")
    print(f"[bulk] selected  = {len(selected)} / {len(rows)} rows")
    print(f"[bulk] models    = {args.models}")
    print(f"[bulk] runs      = {args.runs}")
    if args.max_iterations is not None:
        print(f"[bulk] max-iters = {args.max_iterations}")
    if args.dry_run:
        print("[bulk] dry-run   = true")
    print()

    results: list[tuple[str, str, int]] = []
    env = os.environ.copy()

    for index, row in enumerate(selected, start=1):
        container = (row.get("result_container") or "").strip()
        test_type = (row.get("test_type") or "").strip()

        cmd = [
            sys.executable, str(RUN_AGENTIC),
            container,
            "--models", args.models,
            "--runs", str(args.runs),
        ]
        if args.max_iterations is not None:
            cmd.extend(["--max-iterations", str(args.max_iterations)])
        if args.keep_workspace:
            cmd.append("--keep-workspace")

        print(f"{'=' * 72}")
        print(f"[bulk] {index}/{len(selected)}  {container}  ({test_type})")
        print("[bulk] command:", " ".join(cmd))
        print(f"{'=' * 72}")

        if args.dry_run:
            rc = 0
        else:
            proc = subprocess.run(cmd, cwd=str(SCRIPT_DIR), env=env)
            rc = proc.returncode

        results.append((container, test_type, rc))
        status = "OK" if rc == 0 else f"FAILED exit={rc}"
        print(f"[bulk] {container}: {status}")
        print()

        if rc != 0 and args.stop_on_failure:
            print("[bulk] stopping after first failure because --stop-on-failure was set")
            break

    print(f"{'=' * 72}")
    print("[bulk] summary")
    failed = 0
    for container, test_type, rc in results:
        status = "OK" if rc == 0 else f"FAILED exit={rc}"
        if rc != 0:
            failed += 1
        print(f"  {container:60s} {test_type:12s} {status}")
    print(f"[bulk] completed={len(results)} failed={failed}")
    print(f"{'=' * 72}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
