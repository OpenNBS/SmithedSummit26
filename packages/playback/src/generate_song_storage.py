"""Beet plugin for the storage-backed NBS song database.

The implementation is split across :mod:`src.song_storage`:

* ``render`` handles NBS parsing and concurrent song rendering.
* ``saved_data`` handles the Minecraft SavedData NBT envelope.
* ``debug_functions`` emits optional, explicitly-called in-game loaders.

This plugin intentionally spans the Mecha stage. Before yielding, it renders
the database and publishes the observed chord sizes for ``songs.bolt``. After
Mecha has compiled Bolt, it injects the large raw debug commands and writes the
binary world-data artifact without making Mecha parse either representation.
"""

import logging
from collections.abc import Generator

from beet import Context
from src.song_storage.debug_functions import emit_debug_load_functions
from src.song_storage.render import RenderedStorage, prepare_tasks, render_database
from src.song_storage.saved_data import (
    remove_legacy_global_storage,
    write_command_storage,
)

logger = logging.getLogger(__name__)

DATABASE_META_KEY = "_song_storage_database"
PLAYSOUND_COUNTS_META_KEY = "song_storage_playsound_counts"
REGION_PLAYSOUND_COUNTS_META_KEY = "song_storage_playsound_counts_by_region"


def beet_default(ctx: Context) -> Generator[None]:
    """Prepare macro metadata, then emit artifacts after Mecha finishes."""

    logger.info(
        "Generating regional song databases (hard cap %d playsounds/tick)",
        ctx.meta["max_playsounds_per_tick"],
    )
    database = render_database(prepare_tasks(ctx))
    ctx.meta[DATABASE_META_KEY] = database
    ctx.meta[PLAYSOUND_COUNTS_META_KEY] = list(database.playsound_counts)
    ctx.meta[REGION_PLAYSOUND_COUNTS_META_KEY] = {
        region: list(counts)
        for region, counts in database.playsound_counts_by_region.items()
    }

    logger.info(
        "Observed %d non-empty chord sizes: %s",
        len(database.playsound_counts),
        ", ".join(map(str, database.playsound_counts)),
    )

    # Let the remaining pipeline run. songs.bolt consumes the leaf set above.
    yield

    database = ctx.meta.pop(DATABASE_META_KEY)
    if not isinstance(database, RenderedStorage):
        raise TypeError("Internal song storage database was replaced during build")

    if ctx.meta["generate_storage_load_functions"]:
        emit_debug_load_functions(ctx, database)

    remove_legacy_global_storage(ctx)
    storage_id_template = ctx.meta["song_storage_id_template"]
    for region in database.regions:
        storage_id = storage_id_template.format(region=region)
        output_path = write_command_storage(
            ctx,
            storage_id,
            database.payload_for_region(region),
        )
        logger.info(
            "Wrote %s command storage companion artifact: %s",
            storage_id,
            output_path,
        )
