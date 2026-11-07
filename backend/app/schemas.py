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
