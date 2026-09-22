from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.errors import unsupported_media, unprocessable

_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}


@dataclass(frozen=True, slots=True)
class VerifiedImage:
    mime_type: str
    extension: str
    width_px: int
    height_px: int


def verify_capture_image(data: bytes, *, max_pixels: int) -> VerifiedImage:
    if not data:
        raise unprocessable("invalid_image", "The uploaded image is empty or unreadable.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image.verify()

            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                width_px, height_px = image.size
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise unprocessable(
            "invalid_image",
            "The uploaded file is not a readable supported image.",
        )

    if image_format not in _FORMATS:
        raise unsupported_media(
            "unsupported_image_format",
            "Only JPEG, PNG and WebP images are supported in this prototype.",
        )

    if width_px <= 0 or height_px <= 0 or width_px * height_px > max_pixels:
        raise unprocessable(
            "invalid_image_dimensions",
            "The image dimensions are invalid or exceed the supported limit.",
        )

    mime_type, extension = _FORMATS[image_format]
    return VerifiedImage(
        mime_type=mime_type,
        extension=extension,
        width_px=width_px,
        height_px=height_px,
    )
