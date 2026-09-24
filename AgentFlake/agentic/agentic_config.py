"""Configuration defaults for AgentFlake's agentic repair runners."""

OPENAI_API_KEY: str = ""

# The Anthropic key is read ONLY from this file — never from an environment
# variable and never from a constant in this module. Paste the key into it as
# the sole contents. It is git-ignored.
ANTHROPIC_API_KEY_FILE = (
    __import__("pathlib").Path(__file__).resolve().parent.parent.parent
    / ".anthropic_api_key"
)


def anthropic_api_key() -> str:
    """Return the Anthropic key read from ANTHROPIC_API_KEY_FILE.

    Exits with a pointed message when the file is missing or empty, rather
    than falling back to any other source.
    """
    path = ANTHROPIC_API_KEY_FILE
    if not path.is_file():
        raise SystemExit(
            f"ERROR: Anthropic key file not found: {path}\n"
            f"       Create it and paste your key in as the only contents:\n"
            f"         printf %s \"sk-ant-...\" > {path}\n"
            f"         chmod 600 {path}"
        )
    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise SystemExit(
            f"ERROR: Anthropic key file is empty: {path}\n"
            f"       Paste your key in as the only contents."
        )
    return key

CLAUDE_MODELS: dict = {
    "claude":              "claude-sonnet-4-6",   # default alias
    "claude-sonnet":       "claude-sonnet-4-6",
    "sonnet":              "claude-sonnet-4-6",
    "claude-opus":         "claude-opus-4-7",
    "opus":                "claude-opus-4-7",
    "haiku":               "claude-haiku-4-5-20251001",
}

OPENAI_MODELS: dict = {
    "openai":              "gpt-5.4",             # default OpenAI alias
    "gpt-5.4":             "gpt-5.4",
    "gpt-4o":              "gpt-4o",
    "gpt-4o-mini":         "gpt-4o-mini",
    "gpt-4.1":             "gpt-4.1",
    "gpt-4.1-mini":        "gpt-4.1-mini",
}

DEFAULT_MODEL: str = "claude-sonnet-4-6"

# Hard cap on submit_patch attempts per run.
MAX_ITERATIONS: int = 5

# API round-trips per iteration before submit_patch is forced.
MAX_TOOL_TURNS_PER_ITERATION: int = 10

# Extra verification runs after the first pass.
VERIFY_PASS_RUNS: int = 5

MAX_TOKENS: int = 16384
TEMPERATURE: float = 0

# get_error_logs and exact-resource get_code calls bypass this cap.
TOOL_OUTPUT_MAX_CHARS: int = 16_000

# ---------------------------------------------------------------------------
# Prompt ablation.
#
# "typed"   (default) — baseline: the prompt states this container's flakiness
#                       category and, for OD, the polluter FQN.
# "generic"           — ablation: category and polluter are withheld and every
#                       category definition is listed instead, so the agent has
#                       to diagnose the category itself.
#
# Set with AGENTFLAKE_PROMPT_VARIANT=generic. Reproduction and verification are
# unaffected; only what the model is told changes.
# ---------------------------------------------------------------------------

PROMPT_VARIANTS = ("typed", "generic")

# In the "generic" arm, also withhold the polluter test's source from
# get_test_code. Set False to withhold only the category label and the
# POLLUTER/VICTIM role labels while still showing both methods.
GENERIC_HIDE_POLLUTER: bool = True


def prompt_variant() -> str:
    """Resolve the active prompt variant from the environment."""
    import os

    raw = (os.environ.get("AGENTFLAKE_PROMPT_VARIANT") or "typed").strip().lower()
    if raw not in PROMPT_VARIANTS:
        raise SystemExit(
            f"ERROR: AGENTFLAKE_PROMPT_VARIANT={raw!r} is not one of "
            f"{', '.join(PROMPT_VARIANTS)}"
        )
    return raw
