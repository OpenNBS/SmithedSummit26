"""Shared beet cache for song plugins, keyed by song-related pipeline inputs."""

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


def song_manifest_path(ctx: Context) -> Path:
    return SONGS_PATH.parent / ctx.meta["song_manifest_path"]


def songs_cache_key(ctx: Context) -> str:
    """Return a cache identity for song plugins.

    Incorporates the song manifest file contents plus ``regions`` and
    ``speaker_ranges`` from context meta so config changes invalidate drafts.
    """

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
    """Restore sounds into ``draft`` or arrange to save them after generation.

    Mirrors :meth:`beet.toolchain.generator.Draft.cache` but stores artifacts
    under the shared ``songs`` cache so ``beet cache --clear songs`` resets
    both sounds and song-storage plugins.
    """

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
