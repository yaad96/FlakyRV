"""Configuration defaults for AgentFlake's agentic repair runners."""

ANTHROPIC_API_KEY: str = ""
OPENAI_API_KEY: str = ""

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
