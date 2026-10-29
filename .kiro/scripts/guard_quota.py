#!/usr/bin/env python3
"""PreToolUse guard for shell commands: protect the Groq free-tier daily budget.

Blocks:
- full eval runs (eval.run without --subset dev)
- pytest runs forced into live LLM mode or selecting live-marked tests
Exit 0 = allow; non-zero blocks the command and sends stderr to the agent.
"""
import json
import re
import sys


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from strings(value)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = " ".join(strings(event.get("tool_input", {})))

    if "eval.run" in command and not re.search(r"--subset[ =]dev\b", command):
        print(
            "Blocked: a full eval run uses a large share of the Groq daily token budget (200K/day). "
            "Run the dev subset with `--subset dev`, or ask the user to start the full run themselves.",
            file=sys.stderr,
        )
        return 1

    if "pytest" in command and (
        re.search(r"LLM_MODE=live", command) or re.search(r"-m\s+[\"']?live\b", command)
    ):
        print(
            "Blocked: tests must run offline (LLM_MODE=replay, respx for HTTP). "
            "Live tests are for the user to run manually.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
