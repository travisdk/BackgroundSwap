"""Interactive web UI.  pip install -r requirements-web.txt && python app.py

1. Upload a photo -> the subject is cut out once (cached for the session).
2. Search Pexels/Unsplash -> pick a background from the results, or upload your own.
3. Pan / zoom / blur the background with a live preview.
4. Save the full-resolution result.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import gradio as gr
import requests
from PIL import Image

from background_swap.backgrounds import PROVIDER_HOME, BackgroundError, check_key, download, orientation_for, resolve_provider, search
from background_swap.composite import composite, pan_room, save
from background_swap.config import Settings, save_user_keys, user_config_path, user_keys
from background_swap.segment import cutout, load_image

OUTPUT_DIR = Path(__file__).parent / "output"
PREVIEW_MAX = 1024  # longest side of the live preview
RESULTS = 15
PAN_X, PAN_Y = "Pan ←→", "Pan ↑↓"

KEYS_HELP = """Background photos come from **Pexels** or **Unsplash**. Both are free, but each needs its
own API key, which is stored only on this computer (`{path}`). You need at least one:

- **Pexels:** sign up at [pexels.com/api](https://www.pexels.com/api/) and copy *Your API Key*.
- **Unsplash:** create an app at [unsplash.com/developers](https://unsplash.com/developers) and copy its *Access Key*.

Leave a field empty to keep the key already saved."""


def _shrink(img: Image.Image, longest: int) -> Image.Image:
    img = img.copy()
    img.thumbnail((longest, longest), Image.Resampling.LANCZOS)
    return img


def _params(pan_x, pan_y, zoom, blur, subj_x, subj_y, size):
    # Blur and subject offset are size-independent (per mille / percent of the canvas),
    # so the preview and the full-resolution save match.
    w, h = size
    return dict(
        centering=(pan_x / 100, pan_y / 100),
        zoom=zoom,
        blur=blur * max(size) / 1000,
        offset=(round(subj_x / 100 * w), round(subj_y / 100 * h)),
    )


def _open(path):
    try:
        return load_image(path)
    except ValueError as e:
        raise gr.Error(str(e))


def on_photo(path, state):
    if not path:
        return None, {}
    photo = _open(path)
    settings = Settings.from_env()
    fg = cutout(photo, settings.rembg_model)
    state = {  # keep any background already chosen
        **state,
        "name": Path(path).stem,
        "icc": photo.info.get("icc_profile"),
        "fg": fg,
        "fg_preview": _shrink(fg, PREVIEW_MAX),
    }
    box = state["fg_preview"].getchannel("A").point(lambda a: 255 if a > 128 else 0).getbbox()
    state["subject_center"] = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) if box else None
    return state["fg_preview"], state


def on_search(query, provider, state):
    if not query:
        raise gr.Error("Type something to search for")
    orientation = orientation_for(state["fg"].size) if state.get("fg") else None
    try:
        results = search(query, Settings.from_env(), orientation, provider, per_page=RESULTS)
    except (BackgroundError, requests.RequestException) as e:
        raise gr.Error(str(e))
    gallery = [(c.thumb_url, c.photographer) for c in results]
    return gallery, results, attribution(results[0].provider)


def attribution(provider: str) -> str:
    name = provider.title()
    return f"Photos provided by [{name}]({PROVIDER_HOME[name]})"


def key_status() -> str:
    s = Settings.from_env()
    mark = lambda k: "saved ✓" if k else "not set"
    return f"Pexels: **{mark(s.pexels_api_key)}** · Unsplash: **{mark(s.unsplash_access_key)}**"


def on_save_keys(pexels, unsplash):
    new = {"pexels": (pexels or "").strip(), "unsplash": (unsplash or "").strip()}
    if not any(new.values()):
        raise gr.Error("Paste at least one key")
    try:
        for provider, key in new.items():
            if key:
                check_key(provider, key)
    except (BackgroundError, requests.RequestException) as e:
        raise gr.Error(str(e))
    stored = user_keys()
    save_user_keys(
        PEXELS_API_KEY=new["pexels"] or stored["PEXELS_API_KEY"],
        UNSPLASH_ACCESS_KEY=new["unsplash"] or stored["UNSPLASH_ACCESS_KEY"],
    )
    gr.Info("Keys saved")
    return "", "", key_status(), gr.Accordion(open=False)


def on_load():
    s = Settings.from_env()
    try:
        provider = resolve_provider(s)[0]
    except BackgroundError:
        provider = s.background_provider
    return gr.Accordion(open=not s.has_key), key_status(), provider, attribution(provider)


def _set_background(state, bg: Image.Image, credit: str):
    state["bg"] = bg
    state["bg_preview"] = _shrink(bg, PREVIEW_MAX * 2)
    state["credit"] = credit
    return state


def on_pick(evt: gr.SelectData, candidates, state):
    try:
        bg = download(candidates[evt.index], Settings.from_env())
    except requests.RequestException as e:
        raise gr.Error(str(e))
    return _set_background(state, bg.image, bg.credit_md)


def on_upload_bg(path, state):
    if not path:
        return state
    return _set_background(state, _open(path), "Own background")


def _pan_sliders(state, zoom):
    """Grey out a pan slider when the background has no spare room in that direction."""
    if not state.get("fg") or not state.get("bg"):
        return gr.Slider(interactive=True, label=PAN_X), gr.Slider(interactive=True, label=PAN_Y)
    room_x, room_y = pan_room(state["bg"].size, state["fg"].size, zoom)
    min_px = max(state["fg"].size) * 0.005  # less than this is not visible
    return (
        gr.Slider(interactive=room_x > min_px, label=PAN_X if room_x > min_px else f"{PAN_X} · zoom in to pan"),
        gr.Slider(interactive=room_y > min_px, label=PAN_Y if room_y > min_px else f"{PAN_Y} · zoom in to pan"),
    )


def render_preview(state, *values):
    if not state.get("fg_preview") or not state.get("bg_preview"):
        return None, state.get("credit", "")
    fg = state["fg_preview"]
    img = composite(fg, state["bg_preview"], **_params(*values, fg.size))
    return img, state["credit"]


def render_all(state, *values):
    """Preview plus pan-slider availability (after photo, background or zoom changes)."""
    zoom = values[2]
    return *render_preview(state, *values), *_pan_sliders(state, zoom)


def on_place(evt: gr.SelectData, state):
    """Click in the preview: move the subject's centre to that point."""
    if not state.get("subject_center"):
        return gr.Slider(), gr.Slider()
    w, h = state["fg_preview"].size
    cx, cy = state["subject_center"]
    x, y = evt.index
    return round((x - cx) / w * 100, 1), round((y - cy) / h * 100, 1)


def on_save(state, *values):
    *values, fmt = values
    if not state.get("fg") or not state.get("bg"):
        raise gr.Error("Pick a photo and a background first")
    fg = state["fg"]
    img = composite(fg, state["bg"], **_params(*values, fg.size))
    out = OUTPUT_DIR / f"{state['name']}_{time.strftime('%Y%m%d-%H%M%S')}.{fmt}"
    save(img, out, icc_profile=state["icc"])
    gr.Info(f"Saved {out}")
    return str(out)


def open_output_folder():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        import os

        os.startfile(OUTPUT_DIR)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(OUTPUT_DIR)])


with gr.Blocks(title="Background Swap", fill_width=True) as demo:
    state = gr.State({})
    candidates = gr.State([])

    with gr.Accordion("API keys", open=False) as keys_panel:
        gr.Markdown(KEYS_HELP.format(path=user_config_path()))
        with gr.Row():
            pexels_key = gr.Textbox(label="Pexels API key", type="password", scale=2)
            unsplash_key = gr.Textbox(label="Unsplash Access Key", type="password", scale=2)
            save_keys_btn = gr.Button("Check & save", variant="primary", scale=1)
        keys_status = gr.Markdown()

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 1 · Photo")
            photo = gr.UploadButton("Choose photo…", file_types=["image"], type="filepath", variant="primary")
            cut = gr.Image(label="Cutout", type="pil", image_mode="RGBA", format="png", interactive=False, height=220)

            gr.Markdown("### 2 · Background")
            with gr.Row():
                query = gr.Textbox(show_label=False, placeholder="cozy cafe, nordic forest, ...", scale=3)
                search_btn = gr.Button("Search", scale=1)
            provider = gr.Radio(["pexels", "unsplash"], value=Settings.from_env().background_provider, label="Provider")
            gallery = gr.Gallery(label="Click one to use it", columns=5, height=240, allow_preview=False)
            provided_by = gr.Markdown()
            own_bg = gr.UploadButton("…or use your own background image", file_types=["image"], type="filepath")

        with gr.Column(scale=2):
            preview = gr.Image(
                label="3 · Preview · click to place the subject", type="pil", format="jpeg", interactive=False, height=520
            )
            credit = gr.Markdown()
            with gr.Row():
                subj_x = gr.Slider(-100, 100, value=0, step=0.5, label="Subject ←→", scale=3)
                subj_y = gr.Slider(-100, 100, value=0, step=0.5, label="Subject ↑↓", scale=3)
                reset_subj = gr.Button("Reset position", scale=1)
            with gr.Row():
                pan_x = gr.Slider(0, 100, value=50, step=1, label=PAN_X)
                pan_y = gr.Slider(0, 100, value=50, step=1, label=PAN_Y)
            with gr.Row():
                zoom = gr.Slider(1, 3, value=1, step=0.05, label="Zoom")
                blur = gr.Slider(0, 20, value=0, step=0.5, label="Background blur")
            with gr.Row():
                fmt = gr.Radio(["jpg", "png"], value="jpg", label="Format")
                save_btn = gr.Button("4 · Save full resolution", variant="primary")
            with gr.Row():
                saved = gr.File(label="Download", interactive=False, scale=3)
                open_btn = gr.Button("Open output folder", scale=1)

    controls = [state, pan_x, pan_y, zoom, blur, subj_x, subj_y]
    refresh = dict(fn=render_all, inputs=controls, outputs=[preview, credit, pan_x, pan_y])
    refresh_image = dict(fn=render_preview, inputs=controls, outputs=[preview, credit])

    photo.upload(on_photo, [photo, state], [cut, state]).then(**refresh)
    search_btn.click(on_search, [query, provider, state], [gallery, candidates, provided_by])
    query.submit(on_search, [query, provider, state], [gallery, candidates, provided_by])
    provider.change(attribution, provider, provided_by)
    save_keys_btn.click(on_save_keys, [pexels_key, unsplash_key], [pexels_key, unsplash_key, keys_status, keys_panel])
    demo.load(on_load, None, [keys_panel, keys_status, provider, provided_by])
    gallery.select(on_pick, [candidates, state], state).then(**refresh)
    own_bg.upload(on_upload_bg, [own_bg, state], state).then(**refresh)
    zoom.change(**refresh, show_progress="hidden")
    for s in (pan_x, pan_y, blur, subj_x, subj_y):
        s.change(**refresh_image, show_progress="hidden")
    preview.select(on_place, state, [subj_x, subj_y])
    reset_subj.click(lambda: (0, 0), None, [subj_x, subj_y])
    save_btn.click(on_save, [*controls, fmt], saved)
    open_btn.click(open_output_folder)


if __name__ == "__main__":
    demo.launch()
