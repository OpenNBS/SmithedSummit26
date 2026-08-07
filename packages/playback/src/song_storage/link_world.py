"""Install command-storage artifacts into the beet-linked Minecraft world."""

import logging
import shutil
from collections.abc import Mapping
from pathlib import Path

from beet import Context
from beet.contrib.link import LinkManager

from src.song_storage.saved_data import parse_storage_id

logger = logging.getLogger(__name__)


def resolve_linked_world_storage_path(world: Path, storage_id: str) -> Path:
    """Return the Minecraft 26.2 command-storage path for a linked world."""

    namespace, _ = parse_storage_id(storage_id)
    return world / "data" / namespace / "command_storage.dat"


def copy_command_storages_to_linked_world(
    ctx: Context,
    storages: Mapping[str, Path],
) -> None:
    """Copy written companion artifacts into the world from ``beet link``.

    ``storages`` maps each command-storage id (for example
    ``nbs.woodlands:songs``) to the build-output file produced by
    :func:`src.song_storage.saved_data.write_command_storage`.

    When no world is configured in ``ctx.cache["link"]``, logs a warning and
    skips installation so generation still succeeds for plain builds.
    """

    world = LinkManager(ctx).world
    if not world:
        logger.warning(
            "Skipping command-storage world install: no world configured via "
            "`beet link` (ctx.cache['link']). Companion artifacts remain only "
            "in the build output."
        )
        return

    world_path = Path(world)
    if not world_path.is_dir():
        logger.warning(
            "Skipping command-storage world install: linked world path does "
            "not exist: %s",
            world_path,
        )
        return

    if not storages:
        return

    logger.info(
        "Installing %d command-storage artifact(s) into linked world. "
        "Stop the server or close the world first; Minecraft won't load "
        "these files on /reload.",
        len(storages),
    )
    logger.info("Linked world path: %s", world_path)

    for storage_id, source_path in storages.items():
        if not source_path.is_file():
            logger.warning(
                "Skipping %s: build artifact missing at %s",
                storage_id,
                source_path,
            )
            continue

        destination = resolve_linked_world_storage_path(world_path, storage_id)
        destination.parent.mkdir(parents=True, exist_ok=True)

        temporary_path = destination.with_suffix(".dat.tmp")
        shutil.copy2(source_path, temporary_path)
        temporary_path.replace(destination)
        logger.info(
            "Copied %s command storage to linked world: %s",
            storage_id,
            destination.relative_to(world_path),
        )
