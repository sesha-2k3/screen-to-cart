import base64
import binascii

import cv2
import numpy as np

from app.observability import observe
from app.schemas import FrameSelected


class InvalidFrameError(ValueError):
    def __init__(self, index: int) -> None:
        super().__init__(f"Frame {index} is not a decodable base64 image")
        self.index = index


# capture_input=False keeps base64 frames out of Langfuse: private, and they'd use up units.
@observe(name="select_frame", capture_input=False)
def select_sharpest(frames: list[str]) -> FrameSelected:
    """Pick the frame with the highest variance of the Laplacian (least blur)."""
    scores = [_sharpness(_decode_gray(frame, i)) for i, frame in enumerate(frames)]
    best = max(range(len(scores)), key=scores.__getitem__)
    return FrameSelected(index=best, sharpness=scores[best])


def _decode_gray(frame: str, index: int) -> np.ndarray:
    try:
        data = base64.b64decode(frame, validate=True)
    except binascii.Error as error:
        raise InvalidFrameError(index) from error
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise InvalidFrameError(index)
    return image


def _sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())
