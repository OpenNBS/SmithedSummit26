"""Generate per-song, per-tick speaker note functions from NBS files."""

import json
import logging
import os
import sys
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path

import pynbs
from beet import Context, Function
from src.config import SONGS_PATH
from src.utilities.note_block import PlaysoundNote, get_notes

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenderOptions:
    """Commands and resource names shared by every generated song tick."""

    in_range_tag: str = "nbs.in_range"
    new_in_range_tag: str = "nbs.in_range.new"
    actionbar_prefix: str = "🎵 Now Listening: "
    advancement_template: str = "nbs:song/{song_id}"
    particle: str = "minecraft:note ~ ~1.25 ~ 0 0 0 1 1 normal"


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
    path: Path
    speaker_ranges: tuple[SpeakerRange, ...]
    actionbar_color: str = "green"
    options: RenderOptions = RenderOptions()


@dataclass
class SongResult:
    functions: dict[str, list[str]]


def render_root(task: SongTask, tick: int) -> list[str]:
    """Route to the matching variant, using the final variant as fallback."""

    # execute if entity @s[tag=nbs.speaker.short] run return run function nbs:song/demo/8/short
    # execute if entity @s[tag=nbs.speaker.mid] run return run function nbs:song/demo/8/mid
    # return run function nbs:song/demo/8/long

    if not task.speaker_ranges:
        raise ValueError("At least one speaker range is required")

    # we always ensure that fallback gets hit (usually long)
    *checked_ranges, fallback = task.speaker_ranges

    commands = [
        f"execute if entity @s[tag=nbs.speaker.{speaker.name}] "
        f"run return run function nbs:song/{task.song_id}/{tick}/{speaker.name}"
        for speaker in checked_ranges
    ]
    commands.append(
        f"return run function nbs:song/{task.song_id}/{tick}/{fallback.name}"
    )
    return commands


def render_variant(
    task: SongTask,
    tick: int,
    speaker: SpeakerRange,
    notes: Sequence[PlaysoundNote],
    extra_commands: Sequence[str] = (),
) -> list[str]:
    """Render one range-specific tick function.

    Keep the lifecycle commands here so range tracking, UI, advancements, and
    particles can be customized independently from note parsing.
    """

    options = task.options
    listeners = f"@a[distance=..{speaker.outer}]"
    current_listeners = f"@a[tag={options.new_in_range_tag}]"
    new_listeners = f"@a[tag={options.new_in_range_tag},tag=!{options.in_range_tag}]"
    no_longer_listeners = (
        f"@a[tag=!{options.new_in_range_tag}, tag={options.in_range_tag}]"
    )
    actionbar = json.dumps(
        [
            {"text": options.actionbar_prefix, "color": task.actionbar_color},
            {"text": f"{task.title} - {task.author}", "color": "white"},
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )

    # handles dynamic actionbar showcasing (comment out 107-111 if too much)
    commands = [
        f"execute unless entity {listeners} run return fail",
    ]

    # only every tick cooresponding to 1s
    # TODO: this tick may not exist in the song
    if (tick % 20) == 0:
        commands = [
            f"tag {listeners} add {options.new_in_range_tag}",
            f"title {new_listeners} actionbar {actionbar}",
            f"tag {current_listeners} add {options.in_range_tag}",
            f"tag {no_longer_listeners} remove {options.in_range_tag}",
            f"tag {current_listeners} remove {options.new_in_range_tag}",
        ] + commands

    # we handle beats later outside
    if any(note.instrument == "BEAT" for note in notes):
        commands.append("tag @s add nbs.beat")

    # play our chord
    commands.extend(
        f"playsound {note.play(speaker.inner, speaker.outer)}"
        for note in notes
        if note.instrument != "BEAT"
    )
    commands.extend(extra_commands)  # jank to handle last note in right place

    # keep track of songs listened to
    advancement = options.advancement_template.format(song_id=task.song_id)
    commands.extend(
        [
            f"advancement grant {listeners} only {advancement}",
            f"return run particle {options.particle} {listeners}",
        ]
    )
    return commands


def render_chord(
    task: SongTask,
    tick: int,
    notes: Sequence[PlaysoundNote],
    extra_commands: Sequence[str] = (),
) -> dict[str, list[str]]:
    """Render a tick root and all of its range-specific child functions."""

    functions = {
        f"nbs:song/{task.song_id}/{tick}/root": render_root(task, tick),
    }
    functions.update(
        {
            f"nbs:song/{task.song_id}/{tick}/{speaker.name}": render_variant(
                task,
                tick,
                speaker,
                notes,
                extra_commands,
            )
            for speaker in task.speaker_ranges
        }
    )
    return functions


def render_song(task: SongTask) -> SongResult:
    """Render one song"""

    song = pynbs.read(task.path)
    functions: dict[str, list[str]] = {}
    last_tick: int | None = None

    for tick, notes in get_notes(song):
        last_tick = tick
        functions.update(render_chord(task, tick, notes))

    if last_tick is not None:
        end_tick = last_tick + 40
        functions.update(
            render_chord(
                task,
                end_tick,
                [],
                extra_commands=("tag @s add nbs.advance",),
            )
        )

    return SongResult(functions)


def prepare_tasks(ctx: Context) -> list[SongTask]:
    speaker_ranges = tuple(
        SpeakerRange(
            name=speaker["name"],
            outer=speaker["outer_range"],
            inner=speaker["inner_range"],
        )
        for speaker in ctx.meta["speaker_ranges"]
    )
    tasks: list[SongTask] = []

    regions = ctx.meta["regions"]

    for song_data in ctx.meta["song_manifest"]:
        song_id = song_data["id"]
        region_name = song_data["region"]
        if region_name is None:
            logger.warning("Song %s has no region assigned; skipping", song_id)
            continue

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
                path=path,
                speaker_ranges=speaker_ranges,
                actionbar_color=regions[region_name].title_color,
            )
        )

    return tasks


def beet_default(ctx: Context) -> None:
    logger.info("Generating song note functions for %d songs", len(ctx.meta["song_manifest"]))
    tasks = prepare_tasks(ctx)

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

                for path, lines in result.functions.items():
                    # Store serialized text so the finished pack doesn't retain
                    # millions of individual command strings and list entries.
                    ctx.data.functions[path] = Function("\n".join(lines) + "\n")

    logger.info("🎉 Song note generation complete!")
