#!/usr/bin/env python3
"""PreToolUse guard: keep the agent away from real .env files.

You edit .env yourself; hooks only fire on the agent's tool calls, so your own
edits are never blocked. This script stops the agent from:
  - write: writing to .env, or writing anything that looks like an API key
  - read:  reading .env (so your keys never enter the agent's context)
  - shell: touching .env through the shell (cat, echo >>, sed -i, source, cp, ...)
.env.example is always allowed.

Usage (from a hook): python3 .kiro/scripts/guard_secrets.py <write|read|shell>
Kiro sends the hook event as JSON on stdin. Exit 0 = allow; any other exit code
blocks the tool call and sends stderr to the agent.
"""
import json
import re
import sys

KEY_PATTERNS = {
    "Groq API key": re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "Anthropic API key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "Langfuse secret key": re.compile(r"sk-lf-[A-Za-z0-9\-]{10,}"),
}
# A path that is .env or .env.<anything>, except .env.example
ENV_PATH = re.compile(r"(^|[/\\])\.env(\.(?!example$)[\w.\-]+)?$")
# Same idea inside a shell command: a .env token not followed by .example
ENV_IN_COMMAND = re.compile(r"(^|[\s/\\'\"=<>|;&(])\.env(?!\.example\b)(\.[\w\-]+)?(?=$|[\s'\";|&)<>])")
SHELL_TOUCH = re.compile(
    r"\b(cat|less|more|head|tail|grep|rg|sed|awk|cut|sort|cp|mv|rm|tee|nano|vim?|code|source|export|xargs|python3?|node)\b|>|\.\s"
)

HOW_TO_ASK = (
    "The user edits .env by hand. If a new variable is needed, add its name (no value) to "
    ".env.example and tell the user which variable to set in .env. To see which variables "
    "exist, read .env.example or app/config.py."
)


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from strings(value)


def touches_env_path(values) -> str | None:
    for value in values:
        candidate = value.strip()
        if "\n" not in candidate and ENV_PATH.search(candidate):
            return candidate
    return None


def block(message: str) -> int:
    print(f"Blocked: {message} {HOW_TO_ASK}", file=sys.stderr)
    return 1


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "write"
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # nothing to inspect
    values = list(strings(event.get("tool_input", {})))

    if mode == "read":
        path = touches_env_path(values)
        if path:
            return block(f"reading '{path}' would put secrets into the conversation.")
        return 0

    if mode == "shell":
        command = " ".join(values)
        if ENV_IN_COMMAND.search(command) and SHELL_TOUCH.search(command):
            return block("this shell command reads or modifies a .env file.")
        return 0

    # mode == "write"
    path = touches_env_path(values)
    if path:
        return block(f"writing to '{path}' is not allowed.")
    for value in values:
        for label, pattern in KEY_PATTERNS.items():
            if pattern.search(value):
                print(
                    f"Blocked: this write contains what looks like a {label}. Secrets belong only in "
                    "the user's local .env; code should read them through app/config.py (pydantic-settings).",
                    file=sys.stderr,
                )
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
