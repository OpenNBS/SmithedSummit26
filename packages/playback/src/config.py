"""Pre-populate the context with data to be processed by the remaining pipeline stages."""

import json
import logging

from beet import Context
from nbs_shared.project import SONGS_FILES_DIRECTORY

logger = logging.getLogger(__name__)

SONGS_PATH = SONGS_FILES_DIRECTORY

# range: distance from the speaker to where the song starts being audible
# inner_range: distance from the speaker to where the song is fully audible
SPEAKER_RANGES = [
    {
        "name": "short",
        "outer_range": 12,
        "inner_range": 9,
    },
    {
        "name": "mid",
        "outer_range": 20,
        "inner_range": 16,
    },
    {
        "name": "long",
        "outer_range": 32,
        "inner_range": 24,
    },
]

# Number of 'play' animation variants in the AJ speaker models
ANIM_COUNT = 6


def load_song_manifest(ctx: Context):
    song_manifest_path = SONGS_PATH.parent / ctx.meta["song_manifest_path"]

    SONG_DATA = SONGS_PATH.parent / song_manifest_path

    if not SONG_DATA.exists():
        raise FileNotFoundError(f"Song manifest file not found: {SONG_DATA}")

    with open(SONG_DATA, "r", encoding="utf-8") as f:
        song_manifest = json.load(f)
        ctx.meta["song_manifest"] = song_manifest


def load_speaker_ranges(ctx: Context):
    ctx.meta["speaker_ranges"] = SPEAKER_RANGES
    ctx.meta["anim_count"] = ANIM_COUNT

    logger.info(
        "Loaded %d speaker ranges: %s",
        len(SPEAKER_RANGES),
        ", ".join(speaker_type["name"] for speaker_type in SPEAKER_RANGES),
    )


def load_instruments(ctx: Context):
    ctx.meta["instruments"] = set()


def load_regions(ctx: Context):
    regions = set()
    region_counts = {}
    for song_data in ctx.meta["song_manifest"]:
        region = song_data["region"]
        if region is None:
            continue
        regions.add(region)
        region_counts[region] = region_counts.get(region, 0) + 1

    ctx.meta["regions"] = regions
    ctx.meta["region_counts"] = region_counts

    logger.info("Loaded %d regions: %s", len(regions), ", ".join(regions))


def beet_default(ctx: Context):
    load_song_manifest(ctx)
    load_speaker_ranges(ctx)
    load_instruments(ctx)
    load_regions(ctx)
