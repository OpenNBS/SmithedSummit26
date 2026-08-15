"""Parse NBS files and assemble the indexed song database."""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

import pynbs
from beet import Context

from src.config import SONGS_PATH
from src.utilities.note_block import (
    PlaysoundNote,
    TimingSettings,
    get_notes,
    timing_settings_from_manifest,
)
from src.utilities.parallel import map_as_completed

logger = logging.getLogger(__name__)

# Macro-expanded NBT paths need song and region keys that remain a single path
# segment without quoting. All current manifest ids satisfy this constraint.
DATABASE_KEY = re.compile(r"^[a-z0-9_.+-]+$")

type ScalarPayload = int | str
type RangePayload = dict[str, ScalarPayload]
type TickPayload = dict[str, RangePayload]
type TicksPayload = dict[str, TickPayload]
type IndexPayload = dict[str, str]


class SongMetadata(TypedDict):
    name: str
    index: int
    region: str
    formatted_string: str
    title: str
    author: str


class SongRecord(TypedDict):
    metadata: SongMetadata
    ticks: TicksPayload


class SongDatabasePayload(TypedDict):
    """Aggregate multi-region payload produced while rendering."""

    regions: dict[str, IndexPayload]
    songs: dict[str, SongRecord]


class RegionStoragePayload(TypedDict):
    """Per-region command-storage root written to world data."""

    index: IndexPayload
    songs: dict[str, SongRecord]


@dataclass(frozen=True)
class SpeakerRange:
    name: str
    outer: int
    inner: int
    stereo_separation: int


@dataclass(frozen=True)
class SongTask:
    song_id: str
    title: str
    author: str
    region: str
    region_index: int
    path: Path
    speaker_ranges: tuple[SpeakerRange, ...]
    max_playsounds_per_tick: int
    autoadvance: bool
    end_delay_ticks: int
    timing_settings: TimingSettings = field(default_factory=lambda: TimingSettings())


@dataclass(frozen=True)
class SongResult:
    task: SongTask
    ticks: TicksPayload
    playsound_counts: frozenset[int]
    tick_count: int
    playsound_count: int


@dataclass(frozen=True)
class RenderedStorage:
    """Complete payload plus the sparse template leaf set."""

    root_payload: SongDatabasePayload
    playsound_counts: tuple[int, ...]
    playsound_counts_by_region: dict[str, tuple[int, ...]]
    tick_count: int
    playsound_count: int

    @property
    def songs(self) -> dict[str, SongRecord]:
        return self.root_payload["songs"]

    @property
    def regions(self) -> dict[str, IndexPayload]:
        return self.root_payload["regions"]

    def payload_for_region(self, region: str) -> RegionStoragePayload:
        """Return an isolated database containing only one region's songs."""

        raw_index = self.regions.get(region)
        if raw_index is None:
            raise KeyError(f"No rendered song index for region {region!r}")

        return {
            "index": raw_index,
            "songs": {song_id: self.songs[song_id] for song_id in raw_index.values()},
        }


def render_range_payload(
    speaker: SpeakerRange,
    playable_notes: Sequence[PlaysoundNote],
    *,
    beat: bool = False,
    advance: bool = False,
    stop: bool = False,
) -> RangePayload:
    """Render the macro arguments for one speaker range.

    ``sound_N`` is exactly ``note.play(inner, outer, stereo_separation)``. The
    leading ``playsound`` token lives in the corresponding Bolt template.
    """

    # Keep tick lifecycle flags beside each range payload. Playback caches the
    # active range payload, so this lets it reuse that copy for every command
    # it needs to run for the tick.
    payload: RangePayload = {
        "count": len(playable_notes),
        "beat": int(beat),
        "advance": int(advance),
        "stop": int(stop),
    }
    payload.update(
        {
            f"sound_{index}": note.play(
                speaker.inner,
                speaker.outer,
                speaker.stereo_separation,
            )
            for index, note in enumerate(playable_notes)
        }
    )
    return payload


def render_song(task: SongTask) -> SongResult:
    """Render one NBS file into sparse, string-keyed tick compounds."""

    song = pynbs.read(task.path)
    ticks: TicksPayload = {}
    playsound_counts: set[int] = set()
    last_tick: int | None = None
    total_playsounds = 0

    for tick, notes in get_notes(song, task.timing_settings):
        last_tick = tick
        playable_notes = tuple(note for note in notes if note.instrument != "BEAT")
        note_count = len(playable_notes)
        if note_count > task.max_playsounds_per_tick:
            raise ValueError(
                f"Song {task.song_id!r} tick {tick} has {note_count} playsounds; "
                f"configured maximum is {task.max_playsounds_per_tick}"
            )

        playsound_counts.add(note_count)
        total_playsounds += note_count
        has_beat = any(note.instrument == "BEAT" for note in notes)
        tick_payload: TickPayload = {
            speaker.name: render_range_payload(
                speaker,
                playable_notes,
                beat=has_beat,
            )
            for speaker in task.speaker_ranges
        }
        ticks[f"t{tick}"] = tick_payload

    if last_tick is not None:
        # After the last note, wait then either advance to the next song or stop.
        end_tick = last_tick + task.end_delay_ticks
        end_payload: TickPayload = {
            speaker.name: render_range_payload(
                speaker,
                (),
                advance=task.autoadvance,
                stop=not task.autoadvance,
            )
            for speaker in task.speaker_ranges
        }
        ticks[f"t{end_tick}"] = end_payload
        playsound_counts.add(0)

    return SongResult(
        task=task,
        ticks=ticks,
        playsound_counts=frozenset(playsound_counts),
        tick_count=len(ticks),
        playsound_count=total_playsounds,
    )


def prepare_tasks(ctx: Context) -> list[SongTask]:
    """Build deterministic worker tasks and per-region string indices."""

    speaker_ranges = tuple(
        SpeakerRange(
            name=speaker["name"],
            outer=speaker["outer_range"],
            inner=speaker["inner_range"],
            stereo_separation=speaker["stereo_separation"],
        )
        for speaker in ctx.meta["speaker_ranges"]
    )
    if not speaker_ranges:
        raise ValueError("At least one speaker range is required")

    autoadvance = bool(ctx.meta.get("autoadvance_songs", True))
    delay_seconds = ctx.meta.get("autoadvance_delay_seconds", 2.0)
    if isinstance(delay_seconds, bool) or not isinstance(delay_seconds, (int, float)):
        raise TypeError("autoadvance_delay_seconds must be a number")
    if delay_seconds < 0:
        raise ValueError("autoadvance_delay_seconds must be non-negative")
    end_delay_ticks = int(delay_seconds * 20)

    region_indices: dict[str, int] = {}
    tasks: list[SongTask] = []
    for song_data in ctx.meta["song_manifest"]:
        song_id = song_data["id"]
        region = song_data["region"]
        if region is None:
            logger.warning("Song %s has no region assigned; skipping", song_id)
            continue
        if not DATABASE_KEY.fullmatch(song_id):
            raise ValueError(
                f"Song id {song_id!r} can't be used as a macro-expanded NBT key"
            )
        if not DATABASE_KEY.fullmatch(region):
            raise ValueError(
                f"Region {region!r} can't be used as a macro-expanded NBT key"
            )

        path = SONGS_PATH / f"{song_id}.nbs"
        if not path.exists():
            logger.warning("Song file not found: %s", path)
            continue

        logger.debug("Processing: %s", song_id)
        index = region_indices.setdefault(region, 0)
        region_indices[region] += 1
        tasks.append(
            SongTask(
                song_id=song_id,
                title=song_data["title"],
                author=song_data["author"],
                region=region,
                region_index=index,
                path=path,
                speaker_ranges=speaker_ranges,
                max_playsounds_per_tick=ctx.meta["max_playsounds_per_tick"],
                autoadvance=autoadvance,
                end_delay_ticks=end_delay_ticks,
                timing_settings=timing_settings_from_manifest(song_data),
            )
        )
    return tasks


def render_database(tasks: Sequence[SongTask]) -> RenderedStorage:
    """Render songs concurrently and assemble O(1) compound-key indices."""

    if not tasks:
        return RenderedStorage(
            root_payload={"regions": {}, "songs": {}},
            playsound_counts=(),
            playsound_counts_by_region={},
            tick_count=0,
            playsound_count=0,
        )

    results: dict[str, SongResult] = {
        task.song_id: result
        for task, result in map_as_completed(
            render_song,
            tasks,
            item_id=lambda task: task.song_id,
            thread_name_prefix="song-storage-generator",
            failure_message="Failed to process song: %s",
        )
    }

    songs: dict[str, SongRecord] = {}
    regions: dict[str, IndexPayload] = {}
    playsound_counts: set[int] = set()
    playsound_counts_by_region: dict[str, set[int]] = {}
    total_ticks = 0
    total_playsounds = 0

    # Preserve manifest order even though workers finish out of order.
    for task in tasks:
        result = results[task.song_id]
        region_index = regions.setdefault(task.region, {})
        region_index[f"i{task.region_index}"] = task.song_id

        songs[task.song_id] = {
            "metadata": {
                "name": task.song_id,
                "index": task.region_index,
                "region": task.region,
                "formatted_string": f"{task.title} - {task.author}",
                "title": task.title,
                "author": task.author,
            },
            "ticks": result.ticks,
        }
        playsound_counts.update(result.playsound_counts)
        playsound_counts_by_region.setdefault(task.region, set()).update(
            result.playsound_counts
        )
        total_ticks += result.tick_count
        total_playsounds += result.playsound_count

    logger.info(
        "Rendered %s song ticks containing %s /playsound commands",
        f"{total_ticks:,}",
        f"{total_playsounds:,}",
    )
    return RenderedStorage(
        root_payload={"regions": regions, "songs": songs},
        playsound_counts=tuple(sorted(count for count in playsound_counts if count)),
        playsound_counts_by_region={
            region: tuple(sorted(count for count in counts if count))
            for region, counts in playsound_counts_by_region.items()
        },
        tick_count=total_ticks,
        playsound_count=total_playsounds,
    )
