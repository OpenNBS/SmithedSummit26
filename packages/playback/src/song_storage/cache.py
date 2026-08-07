"""Lightweight songs-cache helpers for song-storage playsound metadata."""

from __future__ import annotations

from beet.core.cache import Cache

_STORAGE_KEY = "storage_key"
_PLAYSOUND_COUNTS = "playsound_counts"
_PLAYSOUND_COUNTS_BY_REGION = "playsound_counts_by_region"


def load_cached_playsound_counts(
    cache: Cache, cache_key: str
) -> tuple[list[int], dict[str, list[int]]] | None:
    """Return cached playsound counts when the songs cache key matches."""

    if cache.json.get(_STORAGE_KEY) != cache_key:
        return None

    counts = cache.json.get(_PLAYSOUND_COUNTS)
    by_region = cache.json.get(_PLAYSOUND_COUNTS_BY_REGION)
    if not isinstance(counts, list) or not isinstance(by_region, dict):
        return None

    return counts, by_region


def save_cached_playsound_counts(
    cache: Cache,
    cache_key: str,
    playsound_counts: list[int],
    playsound_counts_by_region: dict[str, list[int]],
) -> None:
    """Store the songs cache key and the small Bolt macro leaf metadata."""

    cache.json[_STORAGE_KEY] = cache_key
    cache.json[_PLAYSOUND_COUNTS] = playsound_counts
    cache.json[_PLAYSOUND_COUNTS_BY_REGION] = playsound_counts_by_region
