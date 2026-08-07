"""Beet plugin for the storage-backed NBS song database.

The implementation is split across :mod:`src.song_storage`:

* ``render`` handles NBS parsing and concurrent song rendering.
* ``saved_data`` handles the Minecraft SavedData NBT envelope.
* ``debug_functions`` emits optional, explicitly-called in-game loaders.
* ``link_world`` copies companion artifacts into the ``beet link`` world.

This plugin intentionally spans the Mecha stage. Before yielding, it renders
the database and publishes the observed chord sizes for ``songs.bolt``. After
Mecha has compiled Bolt, it injects the large raw debug commands and writes the
binary world-data artifact without making Mecha parse either representation.
"""

import logging
from collections.abc import Generator
from pathlib import Path

from beet import Context

from src.song_storage.cache import (
    load_cached_playsound_counts,
    save_cached_playsound_counts,
)
from src.song_storage.debug_functions import emit_debug_load_functions
from src.song_storage.link_world import copy_command_storages_to_linked_world
from src.song_storage.render import RenderedStorage, prepare_tasks, render_database
from src.song_storage.saved_data import (
    CommandStorageWriteTask,
    parse_storage_id,
    remove_legacy_global_storage,
    resolve_output_path,
    write_command_storage_file,
)
from src.utilities.parallel import map_as_completed
from src.utilities.songs_cache import songs_cache, songs_cache_key

logger = logging.getLogger(__name__)

DATABASE_META_KEY = "_song_storage_database"
PLAYSOUND_COUNTS_META_KEY = "song_storage_playsound_counts"
REGION_PLAYSOUND_COUNTS_META_KEY = "song_storage_playsound_counts_by_region"


def beet_default(ctx: Context) -> Generator[None]:
    """Prepare macro metadata, then emit artifacts after Mecha finishes."""

    cache = songs_cache(ctx)
    cache_key = songs_cache_key(ctx)
    cached_counts = load_cached_playsound_counts(cache, cache_key)
    storage_cache_hit = cached_counts is not None
    database: RenderedStorage | None = None

    if cached_counts is not None:
        playsound_counts, playsound_counts_by_region = cached_counts
        logger.info(
            "Using cached song-storage metadata (hard cap %d playsounds/tick)",
            ctx.meta["max_playsounds_per_tick"],
        )
    else:
        logger.info(
            "Generating regional song databases (hard cap %d playsounds/tick)",
            ctx.meta["max_playsounds_per_tick"],
        )
        database = render_database(prepare_tasks(ctx))
        playsound_counts = list(database.playsound_counts)
        playsound_counts_by_region = {
            region: list(counts)
            for region, counts in database.playsound_counts_by_region.items()
        }
        save_cached_playsound_counts(
            cache, cache_key, playsound_counts, playsound_counts_by_region
        )

    # Debug loaders need the full rendered database in the freshly built pack.
    if ctx.meta["generate_storage_load_functions"] and database is None:
        logger.info("Rendering song databases for storage load debug functions")
        database = render_database(prepare_tasks(ctx))

    ctx.meta[DATABASE_META_KEY] = database
    ctx.meta[PLAYSOUND_COUNTS_META_KEY] = playsound_counts
    ctx.meta[REGION_PLAYSOUND_COUNTS_META_KEY] = playsound_counts_by_region

    logger.info(
        "Observed %d non-empty chord sizes: %s",
        len(playsound_counts),
        ", ".join(map(str, playsound_counts)),
    )

    # Let the remaining pipeline run. songs.bolt consumes the leaf set above.
    yield

    database = ctx.meta.pop(DATABASE_META_KEY)
    if database is not None and not isinstance(database, RenderedStorage):
        raise TypeError("Internal song storage database was replaced during build")

    if ctx.meta["generate_storage_load_functions"]:
        if database is None:
            raise RuntimeError(
                "Song storage database required for debug load functions"
            )
        emit_debug_load_functions(ctx, database)

    if storage_cache_hit:
        # Assume dist/world command-storage artifacts from a prior build are
        # still correct when the songs cache key matches.
        logger.info(
            "Skipping command-storage write/copy; songs cache hit for current inputs"
        )
        return

    if database is None:
        raise RuntimeError("Song storage database missing after cache miss")

    remove_legacy_global_storage(ctx)
    storage_id_template = ctx.meta["song_storage_id_template"]
    data_version = ctx.meta["command_storage_data_version"]
    output_directory = ctx.output_directory
    write_tasks: list[CommandStorageWriteTask] = []
    for region in database.regions:
        storage_id = storage_id_template.format(region=region)
        namespace, _ = parse_storage_id(storage_id)
        write_tasks.append(
            CommandStorageWriteTask(
                storage_id=storage_id,
                root_payload=database.payload_for_region(region),
                output_path=resolve_output_path(ctx, namespace),
                data_version=data_version,
            )
        )

    # Regions are independent: encode NBT and write each companion artifact
    # concurrently, then merge paths on the main thread for logging / linking.
    written_storages: dict[str, Path] = {}
    for task, output_path in map_as_completed(
        write_command_storage_file,
        write_tasks,
        item_id=lambda task: task.storage_id,
        thread_name_prefix="storage-writer",
        failure_message="Failed to write command storage: %s",
    ):
        written_storages[task.storage_id] = output_path
        logged_path = (
            output_path.relative_to(output_directory)
            if output_directory is not None
            else output_path
        )
        logger.info(
            "Wrote %s command storage companion artifact: %s",
            task.storage_id,
            logged_path,
        )

    copy_command_storages_to_linked_world(ctx, written_storages)
