"""Thumbnail credits schema shared by booth and maintenance scripts."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import NotRequired, TypedDict

from pydantic import TypeAdapter, ValidationError

HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
MIN_ZOOM_LEVEL = 1
MAX_ZOOM_LEVEL = 5


class ThumbnailRenderData(TypedDict):
    startTick: int
    startLayer: int
    backgroundColor: str
    zoomLevel: NotRequired[int]


class ThumbnailEntry(TypedDict):
    author: str
    title: str
    url: str
    thumbnailData: ThumbnailRenderData


type ThumbnailCatalog = list[ThumbnailEntry]

_THUMBNAIL_CATALOG_ADAPTER = TypeAdapter(ThumbnailCatalog)


class ThumbnailCatalogError(ValueError):
    """Raised when thumbnails.json fails structural or semantic validation."""


def validate_thumbnail_catalog(data: object) -> ThumbnailCatalog:
    """Validate raw JSON data as the summit thumbnail catalog."""

    try:
        catalog = _THUMBNAIL_CATALOG_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise ThumbnailCatalogError(str(exc)) from exc

    url_counts = Counter(entry["url"] for entry in catalog)
    duplicates = sorted(url for url, count in url_counts.items() if count > 1)
    if duplicates:
        raise ThumbnailCatalogError(
            f"Duplicate thumbnail song url(s): {', '.join(duplicates)}"
        )

    for entry in catalog:
        render = entry["thumbnailData"]
        color = render["backgroundColor"]
        if not HEX_COLOR.fullmatch(color):
            raise ThumbnailCatalogError(
                f"Thumbnail {entry['url']!r} has invalid backgroundColor {color!r}; "
                "expected #RRGGBB"
            )
        zoom_level = render.get("zoomLevel")
        if zoom_level is not None and not (
            MIN_ZOOM_LEVEL <= zoom_level <= MAX_ZOOM_LEVEL
        ):
            raise ThumbnailCatalogError(
                f"Thumbnail {entry['url']!r} has zoomLevel {zoom_level}; "
                f"expected {MIN_ZOOM_LEVEL}-{MAX_ZOOM_LEVEL}"
            )
        for field in ("startTick", "startLayer"):
            if render[field] < 0:
                raise ThumbnailCatalogError(
                    f"Thumbnail {entry['url']!r} has negative {field}"
                )

    return catalog


def load_thumbnail_catalog(path: Path) -> ThumbnailCatalog:
    """Load and validate a thumbnails.json file."""

    with path.open(encoding="utf-8") as handle:
        return validate_thumbnail_catalog(json.load(handle))
