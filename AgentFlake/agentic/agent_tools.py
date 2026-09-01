#!/usr/bin/env python3
"""Read-only context tools exposed to the repair agent."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Reuse the legacy extraction helpers so agentic and non-agentic views match.
SCRIPT_DIR = Path(__file__).resolve().parent
REPROFLAKE_DIR = SCRIPT_DIR.parent
LLM_SCRIPTS_DIR = REPROFLAKE_DIR / "LLM Scripts"
sys.path.insert(0, str(LLM_SCRIPTS_DIR))
from assemble_llm_context import (  # type: ignore  # noqa: E402
    DATA_DIR,
    JAVA_SOURCE_DIRS,
    load_csv_row,
    read_file_safe,
    fqn_to_path,
    find_source_file,
    extract_java_method,
    extract_class_header,
    extract_failure_from_log,
)

EXAMPLES_DIR = SCRIPT_DIR / "flaky_examples"


def _container_base(container: str) -> Path:
    return Path(DATA_DIR) / container


def _source_base(container: str, row: dict) -> Path:
    """Source code may live under <container>/Flaky/ OR under <zip>/Flaky/
    when many containers share a zip. Match the per-type assemblers.
    """
    base = _container_base(container)
    zip_name = (row.get("zip") or "").strip()
    if (base / "Flaky" / "src").is_dir():
        return base
    if zip_name and zip_name != container:
        alt = Path(DATA_DIR) / zip_name
        if (alt / "Flaky" / "src").is_dir():
            return alt
    return base


def _method_fallback_marker(reason: str) -> str:
    return f"({reason}. Use get_code with a more specific FQN if needed.)"

def get_test_code(container: str, test_name: str | None = None) -> str:
    """Return source for the flaky-test container's relevant test methods.

    OD: returns both polluter and victim methods (the CSV pins both).
    TD/ID/NIO: returns the victim method only.

    If `test_name` is supplied, the helper still uses the CSV-known FQN for
    that role; passing a third-party test name is rejected with a clear
    marker rather than risk surfacing arbitrary unrelated code.
    """
    row = load_csv_row(container)
    if not row:
        return f"(container '{container}' not in test_config.csv)"
    source_base = _source_base(container, row)
    module = (row.get("module") or ".").strip()
    test_type = (row.get("test_type") or "").strip().lower()
    polluter_fqn = (row.get("polluter/state setter") or "").strip()
    victim_fqn = (row.get("flaky_test") or "").strip()

    # Keep arbitrary test lookup in get_code; this tool is case-scoped.
    known = {n for n in (polluter_fqn, victim_fqn) if n}
    if test_name and test_name.strip() and test_name.strip() not in known:
        return (
            f"(test_name '{test_name}' is not the victim or polluter for this "
            f"container. Known names: {sorted(known) or 'none'}. Use get_code "
            f"with the FQN if you want a different class/method.)"
        )

    pieces: list[str] = []

    def _emit(label: str, fqn: str) -> None:
        rel_path, method = fqn_to_path(fqn)
        src_file = find_source_file(str(source_base), module, rel_path)
        pieces.append(f"=== {label}: {fqn} ===")
        if not src_file:
            pieces.append(f"(source file not found for {fqn})")
            pieces.append("")
            return
        pieces.append(f"File: {os.path.relpath(src_file, source_base)}")
        if method:
            body = extract_java_method(src_file, method)
            if body:
                pieces.append(f"Method: {method}")
                pieces.append("")
                pieces.append(body.rstrip())
            else:
                pieces.append(_method_fallback_marker(
                    f"could not extract method {method}"))
        else:
            pieces.append(_method_fallback_marker(
                "FQN has no #methodName component"))
        pieces.append("")

    if test_type == "od" and polluter_fqn:
        _emit("POLLUTER", polluter_fqn)
    if victim_fqn:
        _emit("VICTIM", victim_fqn)

    if not pieces:
        return f"(no test FQNs recorded for {container})"
    return "\n".join(pieces).rstrip() + "\n"
_TEXT_FILE_EXTS = {
    ".yaml", ".yml", ".json", ".xml", ".properties", ".txt", ".csv",
    ".conf", ".ini", ".md",
}


def _safe_relative_path(target: str) -> Path | None:
    path = Path(target)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path


def _is_exact_text_file_target(target: str) -> bool:
    rel = _safe_relative_path(target)
    return rel is not None and (rel.suffix.lower() in _TEXT_FILE_EXTS or "/" in target)


def should_truncate_tool_output(name: str, arguments: dict) -> bool:
    if name == "get_error_logs":
        return False
    if name == "get_code" and _is_exact_text_file_target((arguments or {}).get("target") or ""):
        return False
    return True


def _find_exact_text_file(source_base: Path, module: str, target: str) -> Path | None:
    rel = _safe_relative_path(target)
    if rel is None:
        return None
    if not _is_exact_text_file_target(target):
        return None

    target_without_flaky = Path(*rel.parts[1:]) if rel.parts and rel.parts[0] == "Flaky" else rel
    roots: list[Path] = []
    if module and module != ".":
        roots.extend([
            source_base / "Flaky" / module,
            source_base / "Flaky" / module / "src" / "test" / "resources",
            source_base / "Flaky" / module / "src" / "main" / "resources",
        ])
    roots.extend([
        source_base,
        source_base / "Flaky",
        source_base / "Flaky" / "src" / "test" / "resources",
        source_base / "Flaky" / "src" / "main" / "resources",
    ])

    for root in roots:
        for candidate_rel in (rel, target_without_flaky):
            candidate = root / candidate_rel
            if candidate.is_file():
                return candidate

    flaky_root = source_base / "Flaky"
    if flaky_root.is_dir():
        resource_roots = (
            flaky_root.glob("*/src/test/resources"),
            flaky_root.glob("*/src/main/resources"),
        )
        for matches in resource_roots:
            for root in sorted(matches):
                candidate = root / target_without_flaky
                if candidate.is_file():
                    return candidate
    return None

def get_code(container: str, target: str) -> str:
    """Return source for a class/method by FQN, or an exact text resource.

    Accepted targets:
      - 'com.foo.Bar'              -> structural class header (no method bodies)
      - 'com.foo.Bar#methodName'   -> annotations + signature + body of method
      - 'schemas/Foo.yaml'         -> exact text resource/file content

    Searches src/main/java first, then src/test/java. This is the agent's
    main vehicle for tracing state pollution into production code.
    """
    if not target or not target.strip():
        return "(get_code requires a non-empty target)"
    target = target.strip()

    row = load_csv_row(container)
    if not row:
        return f"(container '{container}' not in test_config.csv)"
    source_base = _source_base(container, row)
    module = (row.get("module") or ".").strip()

    text_file = _find_exact_text_file(source_base, module, target)
    if text_file is not None:
        rel_file = os.path.relpath(text_file, source_base)
        text = read_file_safe(str(text_file))
        return f"File: {rel_file}\n\n{text.rstrip()}\n"

    rel_path, method = fqn_to_path(target)
    src_file = find_source_file(
        str(source_base), module, rel_path,
        search_dirs=JAVA_SOURCE_DIRS,
    )
    if not src_file:
        return (
            f"(no editable source file found for {target} under Flaky/. "
            f"If this FQN was copied exactly from the stack trace, it is "
            f"likely supplied by a dependency or otherwise outside the "
            f"editable tree; do not retry path variants for the same class.)"
        )

    rel_src = os.path.relpath(src_file, source_base)
    if method:
        # Show all overloads so wrapper methods do not hide the real logic.
        body = extract_java_method(src_file, method, all_overloads=True)
        if body:
            return (
                f"File: {rel_src}\n"
                f"Method: {method}\n\n"
                f"{body.rstrip()}\n"
            )
        return (
            f"File: {rel_src}\n"
            f"{_method_fallback_marker(f'method {method} not found in file')}\n"
        )

    header = extract_class_header(src_file, include_inner_classes=False)
    if header is None:
        return f"(file not readable: {rel_src})"
    return (
        f"File: {rel_src}\n"
        f"(Structural view: package + imports + signatures + fields. "
        f"Method bodies elided — re-call get_code with '#methodName' for one.)\n\n"
        f"{header.rstrip()}\n"
    )
_LOG_KIND_HINT = (
    "Pass log_type='test_failure' for the original failing surefire run "
    "(the same log the initial prompt summarised), 'compile' for the most "
    "recent Maven recompile errors from the last patch attempt, or 'verify' "
    "for the most recent verify_after_fix.log from the last patch attempt."
)


def _read_first_existing(*paths: Path) -> tuple[str, Path | None]:
    """Return (content, path) for the first path that exists, else ("", None)."""
    for p in paths:
        if p.is_file():
            return read_file_safe(str(p)), p
    return "", None


def get_error_logs(container: str, log_type: str = "test_failure") -> str:
    """Return raw log content for diagnosis.

    log_type:
      'test_failure' — the failure extracted from traces-flakycc/mvn.log
                       (TD), traces-flaky/mvn.log (OD/NIO) or
                       traces-fail/mvn.log (ID). This is the same source
                       the initial prompt summarised; the agent can pull
                       the full block when it needs the stack trace.
      'compile'      — apply_report.json compile/recompile error tail from
                       the most recent submit_patch attempt.
      'verify'       — Steps_Output_Files/verify_after_fix.log from
                       the most recent submit_patch attempt.
    """
    log_type = (log_type or "").strip().lower()
    base = _container_base(container)
    row = load_csv_row(container)
    if not row:
        return f"(container '{container}' not in test_config.csv)"
    source_base = _source_base(container, row)
    steps = base / "Steps_Output_Files"

    if log_type == "test_failure":
        for cand in ("traces-flakycc", "traces-flaky", "traces-fail",
                     "traces-fixed"):
            text = extract_failure_from_log(
                str(source_base / cand / "mvn.log"))
            if not text.startswith("("):
                return f"(from {cand}/mvn.log)\n\n{text}\n"
        return "(no failure block found in any traces-*/mvn.log)"

    if log_type == "compile":
        report_path = steps / "apply_report.json"
        if not report_path.is_file():
            return ("(no apply_report.json yet — submit a patch first; this "
                    "log is only populated after submit_patch runs)")
        import json
        try:
            rep = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return f"(apply_report.json malformed: {exc})"
        rc = rep.get("recompile") or {}
        if rc.get("skipped"):
            return "(recompile was skipped on the last attempt)"
        # Maven often writes real compile failures to stdout, not stderr.
        tail = rc.get("stdout_tail") or rc.get("stderr_tail") or ""
        if not tail:
            return "(no recompile output recorded on the last apply attempt)"
        ok = "ok" if rc.get("ok") else "failed"
        return f"(recompile {ok}; tail of mvn output:)\n\n{tail.rstrip()}\n"

    if log_type == "verify":
        log_path = steps / "verify_after_fix.log"
        verify_log, _ = _read_first_existing(log_path)
        if not verify_log:
            return ("(no verify_after_fix.log yet — submit a patch first; "
                    "this log is only populated after submit_patch runs)")
        block = extract_failure_from_log(str(log_path))
        if block and not block.startswith("("):
            return f"{block}\n"
        return f"{verify_log.rstrip()}\n"

    return f"(unknown log_type '{log_type}'. {_LOG_KIND_HINT})"
_NO_EXAMPLE_TYPES = {"unclassified", "unassigned"}

_CATEGORY_ALIASES = {
    "od": "od", "order-dependent": "od", "brittle": "od", "britle": "od",
    "td": "td", "timing-dependent": "td",
    "id": "id", "implementation-dependent": "id", "nondex": "id",
    "nio": "nio", "non-idempotent": "nio", "non-idempotent-outcome": "nio",
}


def get_flaky_example(category: str | None = None,
                      container: str | None = None) -> str:
    """Return a category-specific successful-repair exemplar.

    Defaults the category to the container's test_type when unspecified —
    saves the agent a tool call. The exemplar contains a worked example
    fix and category-specific search hints (e.g., method-name patterns
    flakyDoctor used to look for in ID cases).
    """
    canon = None
    if category and category.strip():
        requested = category.strip().lower()
        if requested in _NO_EXAMPLE_TYPES:
            return ("(get_flaky_example is unavailable for Unclassified/"
                    "Unassigned flaky-test types because no category-specific "
                    "exemplar exists. Use get_test_code, get_code, and error "
                    "logs instead.)")
        canon = _CATEGORY_ALIASES.get(requested)
        if not canon:
            return (f"(unknown category '{category}'; supported: "
                    f"OD, TD, ID, NIO)")
    if not canon and container:
        row = load_csv_row(container)
        if row:
            test_type = (row.get("test_type") or "").strip().lower()
            if test_type in _NO_EXAMPLE_TYPES:
                return ("(get_flaky_example is unavailable for Unclassified/"
                        "Unassigned flaky-test types because no category-specific "
                        "exemplar exists. Use get_test_code, get_code, and error "
                        "logs instead.)")
            canon = _CATEGORY_ALIASES.get(test_type)
    if not canon:
        return ("(category required when container is unknown; "
                "supported: OD, TD, ID, NIO)")

    path = EXAMPLES_DIR / f"{canon}.md"
    if not path.is_file():
        return f"(no example file at {path})"
    return path.read_text(encoding="utf-8")
TOOL_SCHEMAS = [
    {
        "name": "get_test_code",
        "description": (
            "Return the source code for the flaky test in this container "
            "(annotations + signature + body). For OD cases, also returns "
            "the polluter test's source. Use this first to see what the "
            "test is asserting and what helpers/lifecycle hooks exist."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "test_name": {
                    "type": "string",
                    "description": (
                        "Optional. The test FQN to fetch (must match the "
                        "victim or polluter for this container). Omit to "
                        "get all relevant tests for the case."
                    ),
                },
            },
        },
    },
    {
        "name": "get_code",
        "description": (
            "Return source for a Java class or method by fully-qualified "
            "name. Pass a class FQN ('com.foo.Bar') for a structural class "
            "header (package + imports + signatures + fields, no method "
            "bodies). Pass an FQN with a method ('com.foo.Bar#baz') for "
            "the named method's annotations + signature + body. Searches "
            "src/main/java first, then src/test/java. You may also pass an "
            "exact text resource or repo-relative path named by the test or "
            "failure log, such as 'schemas/Foo.yaml'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": (
                        "Either 'package.ClassName' (class header), "
                        "'package.ClassName#methodName' (method body), or an "
                        "exact text resource/path copied from the test or "
                        "failure log (for example 'schemas/Foo.yaml'). Copy "
                        "Java FQNs verbatim from the stack trace, an import, "
                        "or an extends/implements clause — do not guess the "
                        "package. For a nested class, name its enclosing "
                        "top-level class (e.g. 'pkg.Outer.Inner' or "
                        "'pkg.Outer'); the file is located automatically "
                        "regardless of which module it lives in."
                    ),
                },
            },
            "required": ["target"],
        },
    },
    {
        "name": "get_error_logs",
        "description": (
            "Return raw failure/compile/verify logs. Use 'test_failure' "
            "for the original failing surefire run's stack trace, "
            "'compile' for Maven recompile errors from the most recent "
            "patch attempt, or 'verify' for the most recent verify_after_fix.log."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "log_type": {
                    "type": "string",
                    "enum": ["test_failure", "compile", "verify"],
                    "description": (
                        "Which log to retrieve. 'compile' and 'verify' are "
                        "empty until you have submitted at least one patch."
                    ),
                },
            },
            "required": ["log_type"],
        },
    },
    {
        "name": "get_flaky_example",
        "description": (
            "Return a category-specific successful-repair exemplar with "
            "fix strategies and search hints (e.g. method-name patterns "
            "for ID like flakyDoctor used). Defaults the category to this "
            "container's test_type if you omit it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["OD", "TD", "ID", "NIO"],
                    "description": (
                        "Flaky-test category. Omit to default to this "
                        "container's recorded type."
                    ),
                },
            },
        },
    },
]


def dispatch_tool(container: str, name: str, arguments: dict) -> str:
    """Dispatch a read-only context-tool call by name. Returns a string
    payload suitable to hand back as the tool_result content block.

    Unknown tool names yield an explicit marker; an exception inside any
    tool is caught and returned as a short error string so the agent loop
    can continue rather than crash mid-iteration.
    """
    arguments = arguments or {}
    try:
        if name == "get_test_code":
            return get_test_code(container, arguments.get("test_name"))
        if name == "get_code":
            return get_code(container, arguments.get("target") or "")
        if name == "get_error_logs":
            return get_error_logs(
                container, arguments.get("log_type") or "test_failure")
        if name == "get_flaky_example":
            return get_flaky_example(
                arguments.get("category"), container=container)
        return (f"(unknown tool '{name}'. Available: get_test_code, get_code, "
                f"get_error_logs, get_flaky_example, submit_patch.)")
    except Exception as exc:  # noqa: BLE001
        return f"(tool {name} raised {type(exc).__name__}: {exc})"
