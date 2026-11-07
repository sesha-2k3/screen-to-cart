"""Identify and disambiguate prompts. Change PROMPT_VERSION whenever a prompt changes."""

from __future__ import annotations

import re

from langchain_core.messages import BaseMessage, HumanMessage

from app.schemas import Candidates, TranscriptSegment

PROMPT_VERSION = "identify-v2"
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
video. It is usually the main item in focus.

Work in this order:
1. Look at the frame first. Write visual_notes for the main item: product type, \
shape, colors, materials, and any brand text or logos you can read. Another model \
will rely on these notes without seeing the image.
2. Then read the title, description and transcript to find the exact brand and model.
3. Use a name from the text only if it fits what the frame shows. Videos often \
mention or link several products; a name that is mentioned is not evidence that it \
is the item in this frame. If the frame shows a square watch, a round watch named \
in the transcript is wrong.
4. If the frame shows no brand and the text names none that fits, use "Generic" as \
the brand and the product type as the model.

Rules:
- Return 3 candidates when you can: the best guess first, then the most likely \
alternatives for the same item (other models or brands that look like it). Return \
fewer only if there are no plausible alternatives.
- confidence is your probability that the brand AND exact model are right. The \
confidences of all candidates must add up to 1 or less, so split it honestly.
- evidence cites what supports each candidate: what is visible in the frame \
(visual), a short quote (transcript) or a line from the description (description). \
Include a visual item whenever the frame supports the candidate.
- search_queries: 1 to 3 store search queries, most specific first.
- If no product is visible, return {"candidates": []}.

Reply with JSON only, in this shape:
"""

_TIER2 = """\
A vision model looked at a frame from a YouTube video and proposed the candidates \
below, but it is unsure. Decide the exact brand and model the viewer is asking about.

Rules:
- Treat the visual notes as the truth about what is in the frame. Use the \
description and transcript to pin down the exact model, but reject any name that \
contradicts the visual notes, even if the video mentions it.
- Return the candidates best first, in the same shape, up to 3.
- confidence is your probability that the brand AND exact model are right. The \
confidences of all candidates must add up to 1 or less.
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
