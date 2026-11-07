import base64

import pytest

from app.vision.frame_select import InvalidFrameError, select_sharpest
from tests.frames import blurred_frame, sharp_frame


def test_select_sharpest_picks_the_sharp_frame() -> None:
    result = select_sharpest([blurred_frame(), sharp_frame(), blurred_frame()])

    assert result.index == 1


def test_select_sharpest_rejects_bad_base64() -> None:
    with pytest.raises(InvalidFrameError) as error:
        select_sharpest([sharp_frame(), "not base64!"])

    assert error.value.index == 1


def test_select_sharpest_rejects_bytes_that_are_not_an_image() -> None:
    with pytest.raises(InvalidFrameError):
        select_sharpest([base64.b64encode(b"hello").decode()])
