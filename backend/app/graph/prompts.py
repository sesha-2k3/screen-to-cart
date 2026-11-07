"""Identify and disambiguate prompts. Change PROMPT_VERSION whenever a prompt changes."""

from __future__ import annotations

import re

from langchain_core.messages import BaseMessage, HumanMessage

from app.schemas import Candidates, TranscriptSegment

PROMPT_VERSION = "identify-v1"
DESCRIPTION_LIMIT = 1500

# A word with both letters and digits, like WH-1000XM5 or RTX4090.
_MODEL_NUMBER = re.compile(r"\b(?=[\w-]*[A-Za-z])(?=[\w-]*\d)[\w-]+\b")

# Plain-text shape instead of provider structured output, so prompts work on any provider.
_SHAPE = """\
{"candidates": [{
  "brand": string,
  "model": string,
  "category": string,
  "color": string or null,
  "confidence": number from 0 to 1,
  "evidence": [{"source": "visual" | "transcript" | "description", "detail": string}],
  "search_queries": [string],
  "visual_notes": string
}]}"""

_TIER1 = """\
You identify the exact product a viewer is asking about in a frame from a YouTube \
video. It is usually the main item in focus. Use the frame and the video's title, \
description and transcript around this moment to name the exact brand and model.

Rules:
- Return up to 3 candidates, best first. List more than one only if you are unsure \
which product it is, or several products are equally prominent.
- confidence is your probability that the brand AND exact model are right.
- evidence cites what supports each candidate: text or logos in the frame (visual), \
a short quote (transcript) or a line from the description (description).
- search_queries: 1 to 3 store search queries, most specific first.
- visual_notes: describe brand text, logos, colors, shape and materials in detail. \
Another model will rely on these notes without seeing the image.
- If no product is visible, return {"candidates": []}.

Reply with JSON only, in this shape:
"""

_TIER2 = """\
A vision model looked at a frame from a YouTube video and proposed the candidates \
below, but it is unsure. Using its visual notes and the video's text, decide the \
exact brand and model the viewer is asking about.

Rules:
- Prefer names that appear in the description or transcript and fit the visual notes.
- Return the candidates best first, in the same shape. Return one if you are confident.
- confidence is your probability that the brand AND exact model are right.
- Keep or improve the evidence, search_queries and visual_notes.

Reply with JSON only, in this shape:
"""


def tier1_messages(
    frame: str, title: str, description: str, transcript: list[TranscriptSegment]
) -> list[BaseMessage]:
    """One user message with exactly one image; Groq counts each image as 2,048 tokens."""
    text = f"{_TIER1}{_SHAPE}\n\n{_context(title, description, transcript)}"
    return [
        HumanMessage(
            content=[
                {"type": "text", "text": text},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{frame}"},
                },
            ]
        )
    ]


def tier2_messages(
    tier1: Candidates,
    title: str,
    description: str,
    transcript: list[TranscriptSegment],
) -> list[BaseMessage]:
    context = _context(title, description, transcript)
    text = (
        f"{_TIER2}{_SHAPE}\n\n{context}\n\n"
        f"Vision model candidates:\n{tier1.model_dump_json(indent=1)}"
    )
    return [HumanMessage(content=text)]


def trim_description(description: str, limit: int = DESCRIPTION_LIMIT) -> str:
    """Keep lines with links or model numbers first, then the rest, up to ``limit``."""
    lines = [line for line in description.splitlines() if line.strip()]
    first = [line for line in lines if "http" in line or _MODEL_NUMBER.search(line)]
    rest = [line for line in lines if line not in first]
    kept: list[str] = []
    for line in first + rest:
        room = limit - len("\n".join(kept)) - (1 if kept else 0)
        if room <= 0:
            break
        kept.append(line[:room])
    return "\n".join(kept)


def _context(title: str, description: str, transcript: list[TranscriptSegment]) -> str:
    spoken = "\n".join(f"[{s.start:.0f}s] {s.text}" for s in transcript)
    return (
        f"Title: {title}\n\n"
        f"Description:\n{trim_description(description) or '(empty)'}\n\n"
        f"Transcript around this moment:\n{spoken or '(no captions)'}"
    )
