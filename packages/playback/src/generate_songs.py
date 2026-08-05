"""Generate playback functions from the NBS song manifest."""

import json
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path

import pynbs
from beet import Context, Function

from src.config import SONGS_PATH
from src.utilities.note_block import get_notes

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpeakerRange:
    name: str
    outer: int
    inner: int


@dataclass(frozen=True)
class SongTask:
    song_id: str
    title: str
    author: str
    region: str
    region_index: int
    path: Path
    speaker_ranges: tuple[SpeakerRange, ...]
    animation_count: int


@dataclass
class SongResult:
    functions: dict[str, list[str]]
    instruments: set[str]


def quote(value: str) -> str:
    """Serialize a string using the quoting accepted by SNBT commands."""

    return json.dumps(value)


def render_beat(
    region: str, speaker: SpeakerRange, animation_count: int
) -> list[str]:
    lines = [
        f"execute store result score #random nbs run random value 1..{animation_count}"
    ]
    lines.extend(
        f"execute if score #random nbs matches {animation} "
        f"if entity @a[distance=0..{speaker.outer}] run function "
        f"summit_ambiance:speaker_{region}/animations/beat_{animation}/play"
        for animation in range(1, animation_count + 1)
    )
    lines.append(
        f"execute if entity @a[distance=0..{speaker.outer}] "
        "run particle minecraft:note ~ ~1.25 ~ 0 0 0 1 1"
    )
    return lines


def render_song(task: SongTask) -> SongResult:
    """Render one song without mutating the shared Beet context."""

    song = pynbs.read(task.path)
    functions: dict[str, list[str]] = {}
    instruments: set[str] = set()
    last_tick: int | None = None

    for tick, notes in get_notes(song):
        last_tick = tick
        root = f"nbs:song/{task.song_id}/{tick}/root"
        functions[root] = [
            "data modify storage nbs:temp input set value {}",
            f"data modify storage nbs:temp input.song set value {quote(task.song_id)}",
            f"data modify storage nbs:temp input.tick set value {tick}",
            f"execute store result score {task.region}.#len nbs "
            f"if data storage nbs:playback locations.{task.region}[]",
            "execute store result storage nbs:temp input.i int 1 run "
            f"scoreboard players set {task.region}.#iter nbs 0",
            f"function nbs:playback/{task.region}/speaker_iter/root "
            "with storage nbs:temp input",
            f"scoreboard players add notes_played nbs_stats {len(notes)}",
            "scoreboard players add ticks_played nbs_stats 1",
        ]

        for note in notes:
            instruments.add(note.instrument)

            for speaker in task.speaker_ranges:
                path = f"nbs:song/{task.song_id}/{tick}/{speaker.name}"

                if note.instrument == "BEAT":
                    functions.setdefault(path, []).extend(
                        render_beat(task.region, speaker, task.animation_count)
                    )
                else:
                    functions.setdefault(path, []).append(
                        f"playsound {note.play(speaker.inner, speaker.outer)}"
                    )

    if last_tick is not None:
        end_path = f"nbs:song/{task.song_id}/{last_tick + 40}/root"
        functions.setdefault(end_path, []).append(
            f"function nbs:playback/{task.region}/advance"
        )

    return SongResult(functions, instruments)


def render_load_command(task: SongTask) -> str:
    formatted_string = f"{task.title} - {task.author}"
    return (
        f"data modify storage nbs:playback songs.{task.region} append value {{"
        f"name: {quote(task.song_id)}, index: {task.region_index}, "
        f"formatted_string: {quote(formatted_string)}, title: {quote(task.title)}, "
        f"author: {quote(task.author)}}}"
    )


def prepare_tasks(ctx: Context) -> list[SongTask]:
    speaker_ranges = tuple(
        SpeakerRange(
            name=speaker["name"],
            outer=speaker["range"],
            inner=speaker["inner_range"],
        )
        for speaker in ctx.meta["speaker_ranges"]
    )
    animation_count = ctx.meta["anim_count"]
    current_index_per_region = dict.fromkeys(ctx.meta["regions"], 0)
    tasks: list[SongTask] = []

    for song_data in ctx.meta["song_manifest"]:
        song_id = song_data["id"]
        region = song_data["region"]

        if region is None:
            logger.warning("Song %s has no region assigned; skipping", song_id)
            continue

        region_index = current_index_per_region[region]
        current_index_per_region[region] += 1
        path = SONGS_PATH / f"{song_id}.nbs"

        if not path.exists():
            logger.warning("Song file not found: %s", path)
            continue

        logger.info("Processing: %s", song_id)
        tasks.append(
            SongTask(
                song_id=song_id,
                title=song_data["title"],
                author=song_data["author"],
                region=region,
                region_index=region_index,
                path=path,
                speaker_ranges=speaker_ranges,
                animation_count=animation_count,
            )
        )

    return tasks


def beet_default(ctx: Context) -> None:
    logger.info("Generating songs")

    load_lines = ["data modify storage nbs:playback songs set value {}"]
    load_lines.extend(
        f"data modify storage nbs:playback songs.{region} set value []"
        for region in ctx.meta["regions"]
    )

    tasks = prepare_tasks(ctx)
    load_lines.extend(render_load_command(task) for task in tasks)

    if tasks:
        available_workers = min(len(tasks), os.process_cpu_count() or 1)

        if sys._is_gil_enabled():
            # Large results make IPC the bottleneck beyond a small process pool.
            max_workers = min(available_workers, 4)
            executor = ProcessPoolExecutor(
                max_workers=max_workers,
                mp_context=get_context("spawn"),
            )
            executor_kind = "processes"
        else:
            max_workers = min(available_workers, 10)
            executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="song-generator",
            )
            executor_kind = "free-threaded threads"

        logger.info(
            "Rendering %d songs with %d %s",
            len(tasks),
            max_workers,
            executor_kind,
        )

        with executor:
            futures = {
                executor.submit(render_song, task): task.song_id for task in tasks
            }

            # Beet's pack containers aren't thread-safe. Merge completed songs on the
            # main thread while the remaining workers continue rendering.
            for future in as_completed(futures):
                song_id = futures.pop(future)
                try:
                    result = future.result()
                except Exception:
                    logger.exception("Failed to process song: %s", song_id)
                    raise

                ctx.meta["instruments"].update(result.instruments)
                for path, lines in result.functions.items():
                    # Store serialized text so the finished pack doesn't retain
                    # millions of individual command strings and list entries.
                    ctx.data.functions[path] = Function("\n".join(lines) + "\n")

    ctx.data.functions.setdefault("nbs:playback/load", Function()).prepend(load_lines)
    logger.info("🎉 Song processing complete!")
