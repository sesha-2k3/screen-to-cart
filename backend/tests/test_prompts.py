from app.graph.prompts import DESCRIPTION_LIMIT, trim_description


def test_trim_description_keeps_link_and_model_number_lines_first() -> None:
    description = """Thanks for watching!
Headphones: Sony WH-1000XM5
Subscribe for more
Buy here: https://amzn.to/abc"""
    lines = trim_description(description).splitlines()
    assert lines[:2] == ["Headphones: Sony WH-1000XM5", "Buy here: https://amzn.to/abc"]
    assert lines[2:] == ["Thanks for watching!", "Subscribe for more"]


def test_trim_description_stays_within_the_limit() -> None:
    description = "\n".join(["filler line " * 20] * 20 + ["Model: RTX4090"])
    trimmed = trim_description(description)
    assert len(trimmed) <= DESCRIPTION_LIMIT
    assert trimmed.startswith("Model: RTX4090")
