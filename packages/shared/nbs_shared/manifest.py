"""Song manifest schema shared by playback, booth, and maintenance scripts."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import NotRequired, TypedDict

from pydantic import TypeAdapter, ValidationError

# Region ids stored in the generated manifest (not the display names).
SONG_REGION_IDS = frozenset({"plateaus", "tropics", "woodlands"})


class SongManifestEntry(TypedDict):
    id: str
    title: str
    author: str
    region: str | None
    url: str
    beat_interval: NotRequired[int]
    beat_offset: NotRequired[int]
    tempo_factor: NotRequired[float]


type SongManifest = list[SongManifestEntry]

_SONG_MANIFEST_ADAPTER = TypeAdapter(SongManifest)


class SongManifestError(ValueError):
    """Raised when a song manifest fails structural or semantic validation."""


def validate_song_manifest(data: object) -> SongManifest:
    """Validate raw JSON data as a song manifest.

    Checks TypedDict structure via Pydantic, then enforces unique ids and
    known region identifiers (or null).
    """

    try:
        manifest = _SONG_MANIFEST_ADAPTER.validate_python(data)
    except ValidationError as exc:
        raise SongManifestError(str(exc)) from exc

    id_counts = Counter(entry["id"] for entry in manifest)
    duplicates = sorted(song_id for song_id, count in id_counts.items() if count > 1)
    if duplicates:
        raise SongManifestError(
            f"Duplicate song id(s) in manifest: {', '.join(duplicates)}"
        )

    for entry in manifest:
        region = entry["region"]
        if region is not None and region not in SONG_REGION_IDS:
            raise SongManifestError(
                f"Song {entry['id']!r} has unknown region {region!r}; "
                f"expected one of {sorted(SONG_REGION_IDS)} or null"
            )

    return manifest


def load_song_manifest(path: Path) -> SongManifest:
    """Load and validate a song manifest JSON file."""

    with path.open(encoding="utf-8") as handle:
        return validate_song_manifest(json.load(handle))
