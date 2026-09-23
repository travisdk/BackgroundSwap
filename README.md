# BackgroundSwap

Cuts the subject out of a photo with [rembg](https://github.com/danielgatis/rembg), fetches a
background from Pexels or Unsplash by search term, and composites the two with Pillow.

The subject is never regenerated: rembg only produces a **mask**, which is attached as the alpha
channel of the *original* pixels. Mask values ≥ 240 are snapped to fully opaque (the models
rarely output exactly 255), so subject pixels come out bit-identical; only the soft edge pixels are
blended with the new background. Moving the subject is a whole-pixel shift, never a resample.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # CLI
pip install -r requirements-web.txt      # + web UI
pip install -r requirements-desktop.txt  # + desktop window
```

The rembg model (~40–180 MB) downloads to `~/.rembg/models/` on first run.
For NVIDIA GPU acceleration, install `rembg[gpu]` instead of `rembg[cpu]`.

## API keys

Background search needs a free key from [Pexels](https://www.pexels.com/api/) and/or
[Unsplash](https://unsplash.com/developers). Each user uses their **own** key:

- **Web/desktop app:** on first launch the *API keys* panel is open. Paste a key and press
  *Check & save*. The key is tested and stored in the per-user config file
  (`~/.config/background-swap/config.env` on Linux, `%APPDATA%\background-swap\` on Windows,
  `~/Library/Application Support/background-swap/` on macOS), never in the project folder.
- **CLI / development:** set `PEXELS_API_KEY` / `UNSPLASH_ACCESS_KEY` as environment variables,
  or copy `.env.example` to `.env`.

Precedence: environment variables > `.env` > user config file.

## Usage

```bash
python -m background_swap portrait.jpg "nordic forest"
python -m background_swap portrait.jpg "cozy cafe" -o out/cafe.png --save-cutout
python -m background_swap portrait.jpg "beach sunset" --provider unsplash --model birefnet-general
python -m background_swap portrait.jpg --background-file my_bg.jpg      # offline, local background
```

| Option | Meaning |
|---|---|
| `-o, --output` | `.jpg`, `.png` or `.webp`. Default `<input>_<query>.jpg` next to the input |
| `--provider` | `pexels` or `unsplash` (default from `BACKGROUND_PROVIDER`) |
| `--model` | rembg model: `isnet-general-use`, `u2net`, `birefnet-general`, `birefnet-portrait`, `bria-rmbg`, `u2net_human_seg`, … |
| `--quality` | JPEG/WebP quality (default 95, 4:4:4 chroma) |
| `--save-cutout` | also write the transparent RGBA cutout |
| `--save-background` | also write the downloaded background |

## Web UI

```bash
pip install -r requirements-web.txt
python app.py            # open http://127.0.0.1:7860
```

1. Upload a photo. The subject is cut out once (the first run can take ~30 s on CPU).
2. Search Pexels/Unsplash and click one of the 15 results, or upload your own background.
3. Adjust **pan**, **zoom** and **background blur**, and move the subject with the **Subject**
   sliders or by clicking in the preview. The preview updates live (at reduced size). Pan sliders
   are greyed out when the background has no spare room in that direction; zoom in to pan.
4. **Save full resolution**: writes to `output/` and offers a download link.

Swapping backgrounds or moving sliders never re-runs segmentation, and none of the controls
touch the subject's pixels.

## Desktop app

Runs the same UI in its own native window (pywebview + Qt WebEngine), no browser needed.

```bash
pip install -r requirements-desktop.txt
python desktop.py
./install_desktop_entry.sh      # Linux: add "Background Swap" to the application menu
```

Closing the window stops the local server. Saved images go to `output/`, and the
**Open output folder** button opens that folder in your file manager.

## How it works

1. **Segment** (`background_swap/segment.py`) – EXIF orientation is applied, rembg returns a mask,
   and the mask becomes the alpha channel of the untouched RGB image.
2. **Fetch** (`background_swap/backgrounds.py`) – searches Pexels/Unsplash with an orientation matching
   the photo (landscape/portrait/square) and downloads the top result at full resolution.
3. **Composite** (`background_swap/composite.py`) – the background is scaled to cover and center-cropped
   to the photo's exact size, then the subject is pasted using its alpha mask. The input's ICC
   color profile is carried over to the output.

## Attribution

As the Pexels/Unsplash API guidelines require, the app shows a "Photos provided by Pexels/Unsplash"
link under the search results and a linked "Photo by … on …" credit for the chosen background.
The CLI prints the credit line. The Unsplash integration also triggers the required
download-tracking endpoint.

## Sharing this project

- **Never include an API key.** `.env` is git-ignored; keys saved from the app live outside the
  project. Each user signs up for their own free key (Pexels: 200 requests/hour, 20,000/month).
- Don't include `.venv/` or `output/`; recipients install from the requirements files.

### Third-party licenses

| Component | License |
|---|---|
| rembg | MIT |
| `isnet-general-use`, `u2net` models | Apache-2.0 |
| `bria-rmbg` model (optional) | non-commercial only |
| Gradio | Apache-2.0 |
| pywebview | BSD-3-Clause |
| PySide6 / Qt (Linux desktop window) | LGPL-3.0 |
| Pillow | MIT-CMU |
| requests, python-dotenv | Apache-2.0, BSD-3-Clause |

Background photos are used under the [Pexels license](https://www.pexels.com/license/) or
[Unsplash license](https://unsplash.com/license).

## RMBG-2.0

`bria-rmbg` in rembg is BRIA's RMBG model shipped as ONNX. BRIA's newer RMBG-2.0 (Hugging Face
`briaai/RMBG-2.0`) is gated and licensed for non-commercial use; to use it, generate the mask in
`segment.extract_mask` with `transformers` instead — the rest of the pipeline is unchanged.


## Acknowledgements & Tooling
This application was architected, directed, and configured by Henrik Juhl, 
with implementation and code generation handled via Claude Code.