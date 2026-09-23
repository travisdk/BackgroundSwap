"""Command-line interface.

    python -m background_swap photo.jpg "nordic forest" -o out.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

from .backgrounds import BackgroundError
from .composite import save
from .config import Settings
from .pipeline import replace_background
from .segment import load_image


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="background_swap",
        description="Remove a photo's background and place the subject on a stock photo.",
    )
    p.add_argument("input", help="input photo")
    p.add_argument("query", nargs="?", help='background search, e.g. "cozy cafe"')
    p.add_argument("-o", "--output", help="output file (.jpg/.png/.webp); default: <input>_<query>.jpg")
    p.add_argument("--background-file", help="use a local background image instead of searching")
    p.add_argument("--provider", choices=["pexels", "unsplash"], help="override BACKGROUND_PROVIDER")
    p.add_argument("--model", help="rembg model name, overrides REMBG_MODEL")
    p.add_argument("--quality", type=int, default=95, help="JPEG/WebP quality (default 95)")
    p.add_argument("--save-cutout", action="store_true", help="also save the transparent cutout as PNG")
    p.add_argument("--save-background", action="store_true", help="also save the downloaded background")
    return p


def default_output(input_path: Path, query: str | None) -> Path:
    tag = "".join(c if c.isalnum() else "_" for c in (query or "bg")).strip("_")[:40] or "bg"
    return input_path.with_name(f"{input_path.stem}_{tag}.jpg")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.query and not args.background_file:
        print("error: give a search query or --background-file", file=sys.stderr)
        return 2

    input_path = Path(args.input)
    try:
        photo = load_image(str(input_path))
        bg_image = load_image(args.background_file) if args.background_file else None
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    icc = photo.info.get("icc_profile")

    print(f"Segmenting {input_path.name} ...", file=sys.stderr)
    try:
        result = replace_background(
            photo,
            query=args.query,
            settings=Settings.from_env(),
            background_image=bg_image,
            provider=args.provider,
            model=args.model,
        )
    except (BackgroundError, requests.RequestException) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    out = Path(args.output) if args.output else default_output(input_path, args.query)
    save(result.image, out, quality=args.quality, icc_profile=icc)
    print(f"Saved {out}")

    if args.save_cutout:
        cut = save(result.cutout, out.with_name(f"{out.stem}_cutout.png"), icc_profile=icc)
        print(f"Saved {cut}")
    if result.background:
        if args.save_background:
            bg = save(result.background.image.convert("RGB"), out.with_name(f"{out.stem}_background.jpg"))
            print(f"Saved {bg}")
        print(result.background.credit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
