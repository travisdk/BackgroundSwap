"""Run the app in its own native window instead of a browser tab.

    pip install -r requirements-desktop.txt
    python desktop.py

The Gradio UI is served on a free localhost port and shown in a pywebview window;
closing the window shuts the server down.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_API", "pyside6")  # LGPL Qt binding; must be set before pywebview imports qtpy

import webview  # noqa: E402

from app import demo  # noqa: E402

ICON = Path(__file__).parent / "assets" / "icon.png"
TITLE = "Background Swap"


def main() -> None:
    webview.settings["ALLOW_DOWNLOADS"] = True  # "Download" gets a native save dialog
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True  # photographer credit links

    demo.launch(
        prevent_thread_lock=True,
        inbrowser=False,
        quiet=True,
        footer_links=[],
        favicon_path=str(ICON),
    )
    try:
        webview.create_window(TITLE, demo.local_url, width=1440, height=940, min_size=(960, 640))
        webview.start(gui="qt", icon=str(ICON))
    finally:
        demo.close()


if __name__ == "__main__":
    main()
