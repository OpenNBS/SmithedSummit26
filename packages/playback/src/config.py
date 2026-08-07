"""Pre-populate the context with data to be processed by the remaining pipeline stages."""

import json
import logging
from dataclasses import dataclass

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

REGION_COLORS: dict[str, str] = {
    "plateaus": "#DB6EFF",
    "tropics": "#18F02E",
    "woodlands": "#55FF55",
}

# Number of 'play' animation variants in the AJ speaker models
ANIM_COUNT = 6

# Storage-backed song playback. Minecraft 26.2 uses DataVersion 4903 and the
# namespaced world-data path data/<namespace>/command_storage.dat.
# This is a validation ceiling, not the number of generated templates. The
# storage renderer publishes only chord sizes that actually occur. The current
# production catalog peaks at 55, so 64 leaves a little headroom.
DEFAULT_MAX_PLAYSOUNDS_PER_TICK = 64
SONG_STORAGE_ID_TEMPLATE = "nbs.{region}:songs"
COMMAND_STORAGE_DATA_VERSION = 4903
DEFAULT_DEBUG_STORAGE_COMMAND_LIMIT = 1_900_000


@dataclass
class RegionConfig:
    name: str
    song_count: int
    title_color: str

    def __eq__(self, other: object) -> bool:
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


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


def load_song_storage_config(ctx: Context):
    max_playsounds = ctx.meta.setdefault(
        "max_playsounds_per_tick", DEFAULT_MAX_PLAYSOUNDS_PER_TICK
    )
    if isinstance(max_playsounds, bool) or not isinstance(max_playsounds, int):
        raise TypeError("max_playsounds_per_tick must be an integer")
    if max_playsounds < 1:
        raise ValueError("max_playsounds_per_tick must be at least 1")

    storage_id_template = ctx.meta.setdefault(
        "song_storage_id_template", SONG_STORAGE_ID_TEMPLATE
    )
    if not isinstance(storage_id_template, str):
        raise TypeError("song_storage_id_template must be a string")
    if "{region}" not in storage_id_template:
        raise ValueError("song_storage_id_template must contain {region}")
    ctx.meta.setdefault("command_storage_data_version", COMMAND_STORAGE_DATA_VERSION)
    ctx.meta.setdefault(
        "generate_storage_load_functions", bool(ctx.meta.get("debug", False))
    )
    debug_command_limit = ctx.meta.setdefault(
        "debug_storage_command_limit", DEFAULT_DEBUG_STORAGE_COMMAND_LIMIT
    )
    if isinstance(debug_command_limit, bool) or not isinstance(
        debug_command_limit, int
    ):
        raise TypeError("debug_storage_command_limit must be an integer")
    if debug_command_limit < 1_000:
        raise ValueError("debug_storage_command_limit must be at least 1000")


def load_regions(ctx: Context):
    regions: dict[str, RegionConfig] = {}
    for song_data in ctx.meta["song_manifest"]:
        region = song_data["region"]
        if region is None:
            continue

        try:
            region_color = REGION_COLORS[region]
        except KeyError:
            logger.warning("Warning: Region %s has no color assigned", region)
            region_color = "#FFFFFF"

        if region not in regions:
            regions[region] = RegionConfig(
                name=region,
                song_count=0,
                title_color=region_color,
            )
        regions[region].song_count += 1

    ctx.meta["regions"] = regions

    logger.info(
        "Loaded %d regions: %s",
        len(regions),
        ", ".join(regions),
    )


def beet_default(ctx: Context):
    load_song_manifest(ctx)
    load_speaker_ranges(ctx)
    load_song_storage_config(ctx)
    load_instruments(ctx)
    load_regions(ctx)
