from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]


class TranscriptSegment(BaseModel):
    start: float = Field(description="Seconds from the start of the video")
    duration: float
    text: str


class IdentifyRequest(BaseModel):
    video_id: str
    t: float = Field(ge=0, description="Seconds into the video when the user asked")
    frames: list[str] = Field(
        min_length=1,
        max_length=3,
        description="Base64 JPEG crops, without a data: URL prefix",
    )
    title: str
    description: str
    transcript: list[TranscriptSegment]
    paid_promotion: bool


class FrameSelected(BaseModel):
    index: int
    sharpness: float


class Evidence(BaseModel):
    source: Literal["visual", "transcript", "description"]
    detail: str = Field(description="Short quote or observation")


class ProductCandidate(BaseModel):
    brand: str
    model: str
    category: str
    color: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence]
    search_queries: list[str]
    visual_notes: str = Field(
        description="Brand text, logos, colors and shape seen in the frame"
    )


class Candidates(BaseModel):
    """LLM output of both tiers, and the cached identify result."""

    candidates: list[ProductCandidate] = Field(description="Best first")


class CandidatesEvent(Candidates):
    tier: Literal[1, 2]


class ErrorEvent(BaseModel):
    code: Literal["rate_limited", "upstream_error"]
    message: str
    retry_after_seconds: float | None = None


class LookupResult(Candidates):
    video_id: str
    bucket: int
