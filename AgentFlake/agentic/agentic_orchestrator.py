#!/usr/bin/env python3
"""Route an agentic run to the Anthropic or OpenAI backend."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import agentic_config  # type: ignore  # noqa: E402

DEFAULT_MODEL          = agentic_config.DEFAULT_MODEL
DEFAULT_MAX_ITERATIONS = agentic_config.MAX_ITERATIONS


def _resolve_model(alias: str) -> tuple[str, str]:
    """Resolve a model alias or id to (canonical_model_id, provider)."""
    key = (alias or "").strip().lower()

    if key in agentic_config.CLAUDE_MODELS:
        return agentic_config.CLAUDE_MODELS[key], "anthropic"
    if key in agentic_config.OPENAI_MODELS:
        return agentic_config.OPENAI_MODELS[key], "openai"

    if key.startswith(("gpt", "o1", "o3", "o4")):
        return alias, "openai"
    if key.startswith("claude"):
        return alias, "anthropic"

    return alias, "anthropic"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("container")
    ap.add_argument("--docker-container",
                    help="docker container name (default tm_<container>)")
    ap.add_argument("--max-iterations", type=int,
                    default=DEFAULT_MAX_ITERATIONS,
                    help=f"hard cap on submit_patch attempts "
                         f"(default {DEFAULT_MAX_ITERATIONS})")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"model ID or alias; routes to the matching provider "
                         f"backend (default: {DEFAULT_MODEL})")
    ap.add_argument("--exclude-tools", default="",
                    help="comma-separated tool names to remove from the "
                         "agent's toolset (e.g. get_flaky_example for "
                         "unclassified tests)")
    args = ap.parse_args()

    model_id, provider = _resolve_model(args.model)
    if model_id != args.model:
        print(f"[dispatch] model alias '{args.model}' -> '{model_id}' ({provider})")
    args.model = model_id

    if provider == "openai":
        import agentic_orchestrator_openai as backend  # noqa: E402
    else:
        import agentic_orchestrator_anthropic as backend  # noqa: E402
    backend.run(args)


if __name__ == "__main__":
    main()
