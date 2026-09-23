"""Fit a background to the foreground's size and alpha-composite them."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


def fit_background(
    bg: Image.Image,
    size: tuple[int, int],
    centering: tuple[float, float] = (0.5, 0.5),
    zoom: float = 1.0,
) -> Image.Image:
    """Scale-to-cover then crop ``bg`` to exactly ``size`` (no distortion).

    ``centering`` picks which part of the background is kept (0 = left/top, 1 = right/bottom);
    ``zoom`` > 1 crops in further.
    """
    bg = ImageOps.exif_transpose(bg).convert("RGB")
    w, h = size
    zoom = max(zoom, 1.0)
    zw, zh = round(w * zoom), round(h * zoom)
    bg = ImageOps.fit(bg, (zw, zh), method=Image.Resampling.LANCZOS, centering=centering)
    if (zw, zh) == (w, h):
        return bg
    left = round((zw - w) * centering[0])
    top = round((zh - h) * centering[1])
    return bg.crop((left, top, left + w, top + h))


def pan_room(bg_size: tuple[int, int], size: tuple[int, int], zoom: float = 1.0) -> tuple[float, float]:
    """How far (in output pixels) the background can be panned horizontally and vertically."""
    bw, bh = bg_size
    w, h = size
    zoom = max(zoom, 1.0)
    scale = max(w * zoom / bw, h * zoom / bh)  # scale-to-cover, as in fit_background
    return bw * scale - w, bh * scale - h


def composite(
    foreground: Image.Image,
    background: Image.Image,
    centering: tuple[float, float] = (0.5, 0.5),
    zoom: float = 1.0,
    blur: float = 0.0,
    offset: tuple[int, int] = (0, 0),
) -> Image.Image:
    """Place an RGBA foreground over a background fitted to its size.

    Where alpha is 255 the output pixel equals the foreground pixel exactly;
    only semi-transparent edge pixels are blended with the background.
    Zoom, pan and blur only ever affect the background. ``offset`` moves the subject
    by whole pixels (no resampling); parts moved past the edge are cropped.
    """
    if foreground.mode != "RGBA":
        raise ValueError("foreground must be RGBA")
    out = fit_background(background, foreground.size, centering, zoom)
    if blur > 0:
        out = out.filter(ImageFilter.GaussianBlur(blur))
    out.paste(foreground.convert("RGB"), (int(offset[0]), int(offset[1])), mask=foreground.getchannel("A"))
    return out


def save(img: Image.Image, path: str | Path, quality: int = 95, icc_profile: bytes | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {}
    if icc_profile:
        kwargs["icc_profile"] = icc_profile
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        img.convert("RGB").save(path, "JPEG", quality=quality, subsampling=0, optimize=True, **kwargs)
    elif suffix == ".png":
        img.save(path, "PNG", optimize=True, **kwargs)
    elif suffix == ".webp":
        img.save(path, "WEBP", quality=quality, **kwargs)
    else:
        raise ValueError(f"Unsupported output format {suffix!r} (use .jpg, .png or .webp)")
    return path
