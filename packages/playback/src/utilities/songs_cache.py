"""Shared beet cache for song plugins.

One key (manifest + regions + speaker ranges) decides whether sounds and
song-storage work can be skipped. ``beet cache --clear songs`` resets both.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from beet import Context
from beet.core.cache import Cache
from beet.core.utils import log_time_scope
from beet.toolchain.generator import Draft, DraftCacheSignal

from src.config import SONGS_PATH, RegionConfig

SONGS_CACHE_NAME = "songs"

_SOUNDS_DRAFT_KEY = "sounds_draft_key"
_SOUNDS_RESOURCE_PACK = "sounds_resource_pack"
_STORAGE_KEY = "storage_key"
_PLAYSOUND_COUNTS = "playsound_counts"
_PLAYSOUND_COUNTS_BY_REGION = "playsound_counts_by_region"


def song_manifest_path(ctx: Context) -> Path:
    return SONGS_PATH.parent / ctx.meta["song_manifest_path"]


def songs_cache_key(ctx: Context) -> str:
    """Cache identity: song manifest contents, regions, and speaker ranges."""

    regions = ctx.meta["regions"]
    regions_payload = {
        name: asdict(config) if isinstance(config, RegionConfig) else config
        for name, config in sorted(regions.items())
    }
    return json.dumps(
        {
            "manifest": song_manifest_path(ctx).read_text(encoding="utf-8"),
            "regions": regions_payload,
            "speaker_ranges": ctx.meta["speaker_ranges"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def songs_cache(ctx: Context) -> Cache:
    return ctx.cache[SONGS_CACHE_NAME]


def cache_sounds_draft(draft: Draft, cache: Cache, cache_key: str) -> None:
    """Like ``Draft.cache``, but stores under the shared ``songs`` cache."""

    cached_resource_pack = cache.directory / _SOUNDS_RESOURCE_PACK
    draft_key = f"sounds {cache_key}"

    if cache.json.get(_SOUNDS_DRAFT_KEY) == draft_key:
        with log_time_scope('Load draft "songs" sounds from cache.'):
            draft.assets.load(cached_resource_pack)
        raise DraftCacheSignal()

    @draft.exit_stack.callback
    @log_time_scope('Update cache for draft "songs" sounds.')
    def _() -> None:
        if draft.assets:
            draft.assets.save(path=cached_resource_pack, overwrite=True)
        cache.json[_SOUNDS_DRAFT_KEY] = draft_key

    draft.exit_stack.enter_context(log_time_scope('Generate draft "songs" sounds.'))


def load_cached_playsound_counts(
    cache: Cache, cache_key: str
) -> tuple[list[int], dict[str, list[int]]] | None:
    """Return Bolt macro leaf sizes when the songs cache key matches."""

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
    """Remember the key and the small ``songs.bolt`` metadata after a render."""

    cache.json[_STORAGE_KEY] = cache_key
    cache.json[_PLAYSOUND_COUNTS] = playsound_counts
    cache.json[_PLAYSOUND_COUNTS_BY_REGION] = playsound_counts_by_region
