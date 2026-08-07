"""Painting credits schema shared by the booth package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NotRequired, TypedDict

from pydantic import TypeAdapter, ValidationError


class PaintingEntry(TypedDict):
    author: str
    title: str
    url: str
    size: NotRequired[int]


type PaintingCatalog = list[PaintingEntry]

_PAINTING_CATALOG_ADAPTER = TypeAdapter(PaintingCatalog)


class PaintingCatalogError(ValueError):
    """Raised when paintings.json fails structural or semantic validation."""


def validate_painting_catalog(data: object) -> PaintingCatalog:
    """Validate raw JSON data as the summit painting catalog."""

    try:
        catalog = _PAINTING_CATALOG_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise PaintingCatalogError(str(exc)) from exc

    for entry in catalog:
        size = entry.get("size")
        if size is not None and size < 1:
            raise PaintingCatalogError(
                f"Painting {entry['title']!r} by {entry['author']!r} "
                f"has invalid size {size}; expected a positive integer"
            )

    return catalog


def load_painting_catalog(path: Path) -> PaintingCatalog:
    """Load and validate a paintings.json file."""

    with path.open(encoding="utf-8") as handle:
        return validate_painting_catalog(json.load(handle))
