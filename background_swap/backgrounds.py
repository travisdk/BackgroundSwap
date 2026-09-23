"""Background image retrieval from Pexels or Unsplash."""

from __future__ import annotations

import io
from dataclasses import dataclass

import requests
from PIL import Image

from .config import Settings, user_config_path

TIMEOUT = 30


class BackgroundError(RuntimeError):
    pass


@dataclass
class Background:
    image: Image.Image
    source_url: str
    photographer: str
    provider: str

    @property
    def credit(self) -> str:
        return f"Photo by {self.photographer} on {self.provider} ({self.source_url})"

    @property
    def credit_md(self) -> str:
        return f"Photo by [{self.photographer}]({self.source_url}) on [{self.provider}]({PROVIDER_HOME[self.provider]})"


PROVIDER_HOME = {"Pexels": "https://www.pexels.com", "Unsplash": "https://unsplash.com"}


def orientation_for(size: tuple[int, int]) -> str:
    w, h = size
    ratio = w / h
    if ratio > 1.15:
        return "landscape"
    if ratio < 0.87:
        return "portrait"
    return "square"


def _download(url: str, headers: dict | None = None) -> Image.Image:
    resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    img = Image.open(io.BytesIO(resp.content))
    img.load()
    return img


@dataclass
class Candidate:
    """A search hit: enough to show a thumbnail and download the full image later."""

    thumb_url: str
    full_url: str
    source_url: str
    photographer: str
    provider: str
    download_location: str | None = None  # Unsplash download-tracking endpoint

    @property
    def credit(self) -> str:
        return f"Photo by {self.photographer} on {self.provider} ({self.source_url})"


def search_pexels(query: str, api_key: str, orientation: str | None = None, per_page: int = 1) -> list[Candidate]:
    params = {"query": query, "per_page": per_page}
    if orientation:
        params["orientation"] = orientation
    resp = requests.get(
        "https://api.pexels.com/v1/search",
        params=params,
        headers={"Authorization": api_key},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return [
        Candidate(
            thumb_url=photo["src"]["medium"],
            full_url=photo["src"]["original"],
            source_url=photo["url"],
            photographer=photo.get("photographer", "unknown"),
            provider="Pexels",
        )
        for photo in resp.json().get("photos", [])
    ]


def _unsplash_headers(access_key: str) -> dict:
    return {"Authorization": f"Client-ID {access_key}", "Accept-Version": "v1"}


def search_unsplash(query: str, access_key: str, orientation: str | None = None, per_page: int = 1) -> list[Candidate]:
    params = {"query": query, "per_page": per_page}
    if orientation:
        params["orientation"] = "squarish" if orientation == "square" else orientation
    resp = requests.get(
        "https://api.unsplash.com/search/photos",
        params=params,
        headers=_unsplash_headers(access_key),
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return [
        Candidate(
            thumb_url=photo["urls"]["small"],
            full_url=photo["urls"]["full"],
            source_url=photo["links"]["html"],
            photographer=photo.get("user", {}).get("name", "unknown"),
            provider="Unsplash",
            download_location=photo["links"].get("download_location"),
        )
        for photo in resp.json().get("results", [])
    ]


def resolve_provider(settings: Settings, provider: str | None = None) -> tuple[str, str]:
    """Return (provider, api_key), falling back to whichever provider has a key configured."""
    provider = (provider or settings.background_provider).lower()
    keys = {"pexels": settings.pexels_api_key, "unsplash": settings.unsplash_access_key}
    if provider not in keys:
        raise BackgroundError(f"Unknown provider {provider!r} (use 'pexels' or 'unsplash')")
    if not keys[provider]:
        provider = next((p for p, k in keys.items() if k), None)
        if provider is None:
            raise BackgroundError(
                "No API key. Add a free Pexels or Unsplash key in the app's 'API keys' panel, "
                f"or set PEXELS_API_KEY / UNSPLASH_ACCESS_KEY in {user_config_path()}"
            )
    return provider, keys[provider]


def search(
    query: str,
    settings: Settings,
    orientation: str | None = None,
    provider: str | None = None,
    per_page: int = 1,
) -> list[Candidate]:
    provider, key = resolve_provider(settings, provider)
    fn = search_pexels if provider == "pexels" else search_unsplash
    results = fn(query, key, orientation, per_page)
    if not results:
        raise BackgroundError(f"{provider.title()} returned no results for {query!r}")
    return results


def download(candidate: Candidate, settings: Settings) -> Background:
    if candidate.download_location and settings.unsplash_access_key:
        # Unsplash API guidelines require pinging the download endpoint when a photo is used.
        try:
            requests.get(
                candidate.download_location,
                headers=_unsplash_headers(settings.unsplash_access_key),
                timeout=TIMEOUT,
            )
        except requests.RequestException:
            pass
    return Background(
        image=_download(candidate.full_url),
        source_url=candidate.source_url,
        photographer=candidate.photographer,
        provider=candidate.provider,
    )


def check_key(provider: str, key: str) -> None:
    """Make one tiny search to confirm the key works; raises BackgroundError if not."""
    fn = search_pexels if provider == "pexels" else search_unsplash
    try:
        fn("nature", key, per_page=1)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            raise BackgroundError(f"The {provider.title()} key was rejected - check that it was copied correctly") from None
        raise


def fetch_background(
    query: str,
    settings: Settings,
    orientation: str | None = None,
    provider: str | None = None,
) -> Background:
    """Download the top search result."""
    return download(search(query, settings, orientation, provider)[0], settings)
