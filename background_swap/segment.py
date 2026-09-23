"""Foreground extraction.

rembg is only asked for the *mask*. The cutout is then built by attaching that
mask as the alpha channel of the original RGB data, so subject pixels are never
altered (rembg's own cutout premultiplies edge pixels towards black, which
causes dark fringes). No generative model touches the image.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


OPAQUE_FROM = 240
CLEAR_UP_TO = 8


@lru_cache(maxsize=4)
def _session(model: str):
    from rembg import new_session  # heavy import, deferred

    return new_session(model)


def load_image(path: str) -> Image.Image:
    """Open an image and apply its EXIF orientation (rotation only, no resampling)."""
    try:
        img = Image.open(path)
    except UnidentifiedImageError:
        raise ValueError(
            f"{Path(path).name} is not a readable image (corrupt, encrypted or unsupported format)"
        ) from None
    img = ImageOps.exif_transpose(img)
    return img


def extract_mask(img: Image.Image, model: str = "isnet-general-use") -> Image.Image:
    """Return an 8-bit 'L' alpha mask the same size as ``img``."""
    from rembg import remove

    mask = remove(img.convert("RGB"), session=_session(model), only_mask=True)
    if mask.mode != "L":
        mask = mask.convert("L")
    if mask.size != img.size:
        mask = mask.resize(img.size, Image.Resampling.LANCZOS)
    # The models rarely output exactly 255 inside the subject (typically 250-254), which would
    # blend 1-2% of the new background into every subject pixel. Snap near-opaque to opaque and
    # near-transparent to transparent; only the soft edge keeps partial alpha.
    return mask.point(lambda a: 255 if a >= OPAQUE_FROM else 0 if a <= CLEAR_UP_TO else a)


def cutout(img: Image.Image, model: str = "isnet-general-use") -> Image.Image:
    """RGBA image: original RGB untouched, alpha = segmentation mask."""
    rgba = img.convert("RGBA")
    rgba.putalpha(extract_mask(img, model))
    return rgba
