"""Pure-Python song function generator (bolt-free, multiprocessing).

Builds mcfunction bodies in memory, then a beet_default pipeline stage injects
them into the data pack after Mecha so they aren't re-parsed.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pynbs
from beet import Context, Function

from src.config import ANIM_COUNT, SONGS_PATH, SPEAKER_RANGES
from src.utilities.note_block import get_notes

logger = logging.getLogger(__name__)

_LOG_FORMAT = "%(levelname)s | %(message)s"
_PLAYBACK_LOAD = "nbs:playback/load"


def _configure_worker_logging() -> None:
    """Spawned workers don't inherit the parent's logging setup."""
    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT, force=True)


def _append(
    functions: MutableMapping[str, list[str]],
    resource_location: str,
    *commands: str,
) -> None:
    functions.setdefault(resource_location, []).extend(commands)


def _define(
    functions: MutableMapping[str, list[str]],
    resource_location: str,
    commands: Sequence[str],
) -> None:
    functions[resource_location] = list(commands)


def _snbt_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _song_entry_snbt(
    song_id: str,
    song_index: int,
    formatted_string: str,
    title: str,
    author: str,
) -> str:
    return (
        "{"
        f"name:{_snbt_string(song_id)},"
        f"index:{song_index},"
        f"formatted_string:{_snbt_string(formatted_string)},"
        f"title:{_snbt_string(title)},"
        f"author:{_snbt_string(author)}"
        "}"
    )


def _regions_from_manifest(song_manifest: Iterable[Mapping[str, Any]]) -> set[str]:
    regions: set[str] = set()
    for song_data in song_manifest:
        region = song_data["region"]
        if region is not None:
            regions.add(region)
    return regions


@dataclass(frozen=True)
class _SongJob:
    song_id: str
    title: str
    author: str
    region: str
    song_index: int
    path: Path
    speaker_ranges: tuple[dict[str, Any], ...]
    anim_count: int


@dataclass
class _SongResult:
    load_command: str
    functions: dict[str, list[str]]
    instruments: set[str]


def _process_song(job: _SongJob) -> _SongResult | None:
    """Worker entrypoint — must stay top-level for ProcessPoolExecutor pickling."""
    logger.info("Processing: %s", job.song_id)

    if not job.path.exists():
        logger.warning("Song file not found: %s", job.path)
        return None

    song = pynbs.read(job.path)
    functions: dict[str, list[str]] = {}
    instruments: set[str] = set()
    formatted_string = f"{job.title} - {job.author}"

    load_command = (
        "data modify storage nbs:playback "
        f"songs.{job.region} append value "
        f"{_song_entry_snbt(job.song_id, job.song_index, formatted_string, job.title, job.author)}"
    )

    tick = -40  # so tick+40 → 0 if a song somehow has no chords
    for chord in get_notes(song):
        tick = chord[0]
        notes = chord[1]

        root_commands: list[str] = [
            "data modify storage nbs:temp input set value {}",
            f"data modify storage nbs:temp input.song set value {_snbt_string(job.song_id)}",
            f"data modify storage nbs:temp input.tick set value {tick}",
            f"execute store result score {job.region}.#len nbs "
            f"if data storage nbs:playback locations.{job.region}[]",
            f"execute store result storage nbs:temp input.i int 1 "
            f"run scoreboard players set {job.region}.#iter nbs 0",
            f"function nbs:playback/{job.region}/speaker_iter/root with storage nbs:temp input",
            f"scoreboard players add notes_played nbs_stats {len(notes)}",
            "scoreboard players add ticks_played nbs_stats 1",
        ]
        _define(functions, f"nbs:song/{job.song_id}/{tick}/root", root_commands)

        for note in notes:
            for speaker in job.speaker_ranges:
                speaker_type = speaker["name"]
                outer_range = speaker["range"]
                inner_range = speaker["inner_range"]
                speaker_fn = f"nbs:song/{job.song_id}/{tick}/{speaker_type}"

                if note.instrument == "BEAT":
                    beat_commands = [
                        f"execute store result score #random nbs "
                        f"run random value 1..{job.anim_count}",
                    ]
                    for i in range(job.anim_count):
                        beat_commands.append(
                            f"execute if score #random nbs matches {i + 1} "
                            f"if entity @a[distance=0..{outer_range}] "
                            f"run function summit_ambiance:speaker_{job.region}/"
                            f"animations/beat_{i + 1}/play"
                        )
                    beat_commands.append(
                        f"execute if entity @a[distance=0..{outer_range}] "
                        "run particle minecraft:note ~ ~1.25 ~ 0 0 0 1 1"
                    )
                    _append(functions, speaker_fn, *beat_commands)
                    continue

                _append(
                    functions,
                    speaker_fn,
                    f"playsound {note.play(inner_range, outer_range)}",
                )

            instruments.add(note.instrument)

    # Uses the last tick from the chord loop (same scoping as the bolt module).
    _define(
        functions,
        f"nbs:song/{job.song_id}/{tick + 40}/root",
        [f"function nbs:playback/{job.region}/advance"],
    )

    return _SongResult(load_command, functions, instruments)


def generate_songs(
    song_manifest: Sequence[Mapping[str, Any]],
    *,
    songs_path: Path = SONGS_PATH,
    speaker_ranges: Sequence[Mapping[str, Any]] = SPEAKER_RANGES,
    regions: Iterable[str] | None = None,
    anim_count: int = ANIM_COUNT,
    instruments: set[str] | None = None,
    max_workers: int | None = None,
) -> dict[str, list[str]]:
    """Generate song playback functions in memory.

    Songs are processed in a process pool (true parallelism for CPU-bound work);
    results are merged in manifest order so `nbs:playback/load` appends stay
    deterministic.

    Returns a dict of function resource locations → command lines.
    """
    regions_set = (
        set(regions) if regions is not None else _regions_from_manifest(song_manifest)
    )
    if instruments is None:
        instruments = set()

    functions: dict[str, list[str]] = {}

    logger.info("Generating songs")

    _append(
        functions,
        _PLAYBACK_LOAD,
        "data modify storage nbs:playback songs set value {}",
    )
    for region in regions_set:
        _append(
            functions,
            _PLAYBACK_LOAD,
            f"data modify storage nbs:playback songs.{region} set value []",
        )

    # Always go through the package module so ProcessPool pickling works when
    # this file is executed as __main__ (e.g. under cProfile with a file path).
    from src import generate_songs_profile as _mod

    current_index_per_region = {region: 0 for region in regions_set}
    speaker_ranges_tuple = tuple(dict(speaker) for speaker in speaker_ranges)
    jobs: list[_mod._SongJob] = []

    for song_data in song_manifest:
        song_id = song_data["id"]
        region = song_data["region"]

        if region is None:
            logger.warning("Song %s has no region assigned; skipping", song_id)
            continue

        song_index = current_index_per_region[region]
        current_index_per_region[region] += 1

        jobs.append(
            _mod._SongJob(
                song_id=song_id,
                title=song_data["title"],
                author=song_data["author"],
                region=region,
                song_index=song_index,
                path=songs_path / f"{song_id}.nbs",
                speaker_ranges=speaker_ranges_tuple,
                anim_count=anim_count,
            )
        )

    with ProcessPoolExecutor(
        max_workers=max_workers,
        initializer=_mod._configure_worker_logging,
    ) as executor:
        results = list(executor.map(_mod._process_song, jobs))

    for result in results:
        if result is None:
            continue
        _append(functions, _PLAYBACK_LOAD, result.load_command)
        functions.update(result.functions)
        instruments.update(result.instruments)

    logger.info("Song processing complete!")
    return functions


def beet_default(ctx: Context) -> None:
    """Inject generated song functions into the pack after Mecha."""
    generated = generate_songs(
        ctx.meta["song_manifest"],
        speaker_ranges=ctx.meta["speaker_ranges"],
        regions=ctx.meta["regions"],
        anim_count=ctx.meta["anim_count"],
        instruments=ctx.meta["instruments"],
    )

    load_commands = generated.pop(_PLAYBACK_LOAD, [])
    song_keys = [k for k in generated if k.startswith("nbs:song/")]
    song_ids = sorted({k.split("/", 2)[1] for k in song_keys})
    logger.info(
        "Injecting %s functions (%s song ids: %s); load has %s commands",
        len(generated) + 1,
        len(song_ids),
        song_ids,
        len(load_commands),
    )
    if load_commands:
        logger.info("First load command: %s", load_commands[0])
        logger.info("Last load command: %s", load_commands[-1])

    # Song registry must run before playback/load's change_song calls.
    # Replace the Function wholesale — mutating .lines on Mecha-built
    # functions is not always persisted to the dumped pack.
    existing_load = (
        list(ctx.data.functions[_PLAYBACK_LOAD].lines)
        if _PLAYBACK_LOAD in ctx.data.functions
        else []
    )
    ctx.data[_PLAYBACK_LOAD] = Function(load_commands + existing_load)

    for path, commands in generated.items():
        ctx.data[path] = Function(commands)


def load_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)


def main() -> dict[str, list[str]]:
    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)
    manifest_name = "manifest.json"
    manifest_path = SONGS_PATH.parent / manifest_name
    song_manifest = load_manifest(manifest_path)
    regions = _regions_from_manifest(song_manifest)
    functions = generate_songs(song_manifest, regions=regions)
    total_commands = sum(len(body) for body in functions.values())
    logger.info(
        "Built %s functions (%s commands) in memory",
        len(functions),
        total_commands,
    )
    return functions


if __name__ == "__main__":
    main()
