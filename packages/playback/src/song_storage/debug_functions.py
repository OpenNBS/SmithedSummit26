"""Generate opt-in in-game loaders for debugging command storage."""

import logging
from collections.abc import Mapping
from concurrent.futures import as_completed

from beet import Context, Function, FunctionTag

from src.song_storage.render import RenderedStorage, create_executor
from src.song_storage.saved_data import payload_to_nbt

logger = logging.getLogger(__name__)


def song_load_commands(
    storage_id: str,
    song_id: str,
    raw_song: Mapping[str, object],
    command_limit: int,
) -> list[str]:
    """Use one mutation when possible and safely batch oversized songs.

    Dense songs can serialize to many megabytes of SNBT. For those, initialize
    metadata once and merge string-keyed tick batches below the configured
    command-length ceiling. No individual note or range is copied separately.
    """

    song_path = f"songs.{song_id}"
    full_command = (
        f"data modify storage {storage_id} {song_path} set value "
        f"{payload_to_nbt(raw_song).snbt()}"
    )
    if len(full_command) <= command_limit:
        return [full_command]

    metadata = raw_song.get("metadata")
    ticks = raw_song.get("ticks")
    if not isinstance(metadata, Mapping) or not isinstance(ticks, Mapping):
        raise TypeError(f"Invalid song record for {song_id!r}")

    commands = [
        f"data modify storage {storage_id} {song_path} set value "
        f"{{metadata:{payload_to_nbt(metadata).snbt()},ticks:{{}}}}"
    ]
    prefix = f"data modify storage {storage_id} {song_path}.ticks merge value {{"
    batch: list[str] = []
    batch_length = len(prefix) + 1

    def flush() -> None:
        nonlocal batch_length
        if batch:
            commands.append(prefix + ",".join(batch) + "}")
            batch.clear()
            batch_length = len(prefix) + 1

    for tick_key, tick_payload in ticks.items():
        if not isinstance(tick_payload, Mapping):
            raise TypeError(f"Invalid tick payload {song_id!r}.{tick_key}")
        entry = f"{tick_key}:{payload_to_nbt(tick_payload).snbt()}"
        separator_length = int(bool(batch))
        if len(prefix) + len(entry) + 1 > command_limit:
            raise ValueError(
                f"Single tick {song_id!r}.{tick_key} exceeds "
                f"debug_storage_command_limit={command_limit}"
            )
        if batch_length + separator_length + len(entry) > command_limit:
            flush()
            separator_length = 0
        batch.append(entry)
        batch_length += separator_length + len(entry)

    flush()
    logger.info(
        "Split debug loader for %s into %d bounded storage operations",
        song_id,
        len(commands),
    )
    return commands


def emit_debug_load_functions(ctx: Context, database: RenderedStorage) -> None:
    """Emit bounded song mutations grouped into region functions.

    Nothing is added to ``minecraft:load``. These functions intentionally make
    large, laggy storage mutations and must be called explicitly while testing.
    Most songs use one mutation; oversized records use tick batches.
    """

    storage_id_template = ctx.meta["song_storage_id_template"]
    command_limit = ctx.meta["debug_storage_command_limit"]
    all_commands = []
    song_commands: dict[str, list[str]] = {}
    song_tasks: list[tuple[str, str, dict[str, object]]] = []

    for region, raw_index in database.regions.items():
        if not isinstance(raw_index, dict):
            raise TypeError(f"Invalid region index for {region!r}")

        storage_id = storage_id_template.format(region=region)
        for song_id in raw_index.values():
            if not isinstance(song_id, str):
                raise TypeError(f"Invalid song id in region {region!r}: {song_id!r}")
            raw_song = database.songs[song_id]
            if not isinstance(raw_song, dict):
                raise TypeError(f"Invalid song payload for {song_id!r}")
            song_tasks.append((storage_id, song_id, raw_song))

    if song_tasks:
        executor, max_workers, executor_kind = create_executor(len(song_tasks))
        logger.info(
            "Generating %d debug song loaders with %d %s",
            len(song_tasks),
            max_workers,
            executor_kind,
        )
        with executor:
            futures = {
                executor.submit(
                    song_load_commands,
                    storage_id,
                    song_id,
                    raw_song,
                    command_limit,
                ): song_id
                for storage_id, song_id, raw_song in song_tasks
            }
            for future in as_completed(futures):
                song_id = futures[future]
                try:
                    song_commands[song_id] = future.result()
                except Exception:
                    logger.exception("Failed to generate debug loader: %s", song_id)
                    raise

    for region, raw_index in database.regions.items():
        storage_id = storage_id_template.format(region=region)
        commands = [
            f"data remove storage {storage_id} index",
            f"data remove storage {storage_id} songs",
            f"data modify storage {storage_id} index set value "
            f"{payload_to_nbt(raw_index).snbt()}",
        ]
        for song_id in raw_index.values():
            commands.extend(song_commands[song_id])

        commands.append(f"function nbs:playback/{region}/change_song")
        function_path = f"nbs:songs/debug/load/{region}"
        ctx.data.functions[function_path] = Function("\n".join(commands) + "\n")
        ctx.data.function_tags[f"nbs:debug/load/{region}"] = FunctionTag(
            {"values": [function_path]}
        )
        all_commands.append(f"function {function_path}")

    all_function_path = "nbs:songs/debug/load/all"
    ctx.data.functions[all_function_path] = Function("\n".join(all_commands) + "\n")
    ctx.data.function_tags["nbs:debug/load/all"] = FunctionTag(
        {"values": [all_function_path]}
    )
