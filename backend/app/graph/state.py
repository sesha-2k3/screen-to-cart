from typing import Literal, NotRequired, TypedDict

from app.schemas import ProductCandidate, TranscriptSegment


class PipelineState(TypedDict):
    video_id: str
    frame: str  # the sharpest frame, base64 JPEG
    title: str
    description: str
    transcript: list[TranscriptSegment]
    candidates: NotRequired[list[ProductCandidate]]
    tier: NotRequired[Literal[1, 2]]
