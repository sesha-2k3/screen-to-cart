import base64

import cv2
import numpy as np


def sharp_frame() -> str:
    rng = np.random.default_rng(0)
    return _encode(rng.integers(0, 256, (90, 160, 3), dtype=np.uint8))


def blurred_frame() -> str:
    rng = np.random.default_rng(0)
    image = rng.integers(0, 256, (90, 160, 3), dtype=np.uint8)
    return _encode(cv2.GaussianBlur(image, (15, 15), 0))


def _encode(image: np.ndarray) -> str:
    ok, jpeg = cv2.imencode(".jpg", image)
    assert ok
    return base64.b64encode(jpeg.tobytes()).decode()
