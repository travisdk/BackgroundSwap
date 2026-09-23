"""End-to-end: photo -> cutout -> fetched background -> composite."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from .backgrounds import Background, fetch_background, orientation_for, resolve_provider
from .composite import composite
from .config import Settings
from .segment import cutout


@dataclass
class Result:
    image: Image.Image
    cutout: Image.Image
    background: Background | None


def replace_background(
    photo: Image.Image,
    query: str | None = None,
    settings: Settings | None = None,
    background_image: Image.Image | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> Result:
    """Swap the background of ``photo``.

    Either ``query`` (searched on Pexels/Unsplash) or ``background_image`` must be given.
    """
    settings = settings or Settings.from_env()
    if background_image is None:
        if not query:
            raise ValueError("Provide a search query or a background image")
        resolve_provider(settings, provider)  # fail before the slow segmentation step
    fg = cutout(photo, model or settings.rembg_model)

    bg_meta = None
    if background_image is None:
        bg_meta = fetch_background(query, settings, orientation_for(fg.size), provider)
        background_image = bg_meta.image

    return Result(image=composite(fg, background_image), cutout=fg, background=bg_meta)
