"""Pre-populate the context with data to be processed by the remaining pipeline stages."""

import logging
from dataclasses import dataclass

from beet import Context

from nbs_shared.manifest import load_song_manifest as read_song_manifest
from nbs_shared.project import SONGS_FILES_DIRECTORY

logger = logging.getLogger(__name__)

SONGS_PATH = SONGS_FILES_DIRECTORY

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
        if not isinstance(other, RegionConfig):
            return NotImplemented
        return self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)


def load_song_manifest(ctx: Context) -> None:
    song_manifest_path = SONGS_PATH.parent / ctx.meta["song_manifest_path"]

    if not song_manifest_path.exists():
        raise FileNotFoundError(f"Song manifest file not found: {song_manifest_path}")

    ctx.meta["song_manifest"] = read_song_manifest(song_manifest_path)


def load_speaker_ranges(ctx: Context):
    speaker_ranges = ctx.meta.get("speaker_ranges")
    if not isinstance(speaker_ranges, list) or not speaker_ranges:
        raise ValueError("meta.speaker_ranges must be a non-empty list")

    for index, speaker in enumerate(speaker_ranges):
        if not isinstance(speaker, dict):
            raise TypeError(f"meta.speaker_ranges[{index}] must be a mapping")
        for key in ("name", "outer_range", "inner_range", "stereo_separation", "decay_volume"):
            if key not in speaker:
                raise ValueError(f"meta.speaker_ranges[{index}] missing {key!r}")

    anim_variant_count = ctx.meta.get("speaker_anim_variant_count", 6)
    if isinstance(anim_variant_count, bool) or not isinstance(anim_variant_count, int):
        raise TypeError("meta.speaker_anim_variant_count must be an integer")
    if anim_variant_count < 1:
        raise ValueError("meta.speaker_anim_variant_count must be at least 1")
    ctx.meta["speaker_anim_variant_count"] = anim_variant_count

    logger.info(
        "Loaded %d speaker ranges: %s",
        len(speaker_ranges),
        ", ".join(speaker["name"] for speaker in speaker_ranges),
    )


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
    region_colors = ctx.meta.get("region_colors", {})
    if not isinstance(region_colors, dict):
        raise TypeError("meta.region_colors must be a mapping")

    regions: dict[str, RegionConfig] = {}
    for song_data in ctx.meta["song_manifest"]:
        region = song_data["region"]
        if region is None:
            continue

        region_color = region_colors.get(region)
        if region_color is None:
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
    load_regions(ctx)
