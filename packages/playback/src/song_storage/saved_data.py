"""Encode the song database as Minecraft command-storage SavedData."""

import re
from collections.abc import Mapping
from pathlib import Path

from beet import Context
from nbtlib import Byte, Compound, File, Int, String

RESOURCE_LOCATION = re.compile(
    r"^(?P<namespace>[a-z0-9_.-]+):(?P<path>[a-z0-9/._-]+)$"
)


def payload_to_nbt(value: Mapping[str, object]) -> Compound:
    """Convert the Python database into explicit Java NBT tags."""

    compound = Compound()
    for key, item in value.items():
        if isinstance(item, Mapping):
            compound[key] = payload_to_nbt(item)
        elif key in {"beat", "advance"}:
            compound[key] = Byte(item)
        elif isinstance(item, int):
            compound[key] = Int(item)
        elif isinstance(item, str):
            compound[key] = String(item)
        else:
            raise TypeError(f"Unsupported song-storage value at {key!r}: {item!r}")
    return compound


def parse_storage_id(storage_id: str) -> tuple[str, str]:
    match = RESOURCE_LOCATION.fullmatch(storage_id)
    if not match:
        raise ValueError(f"Invalid command storage resource location: {storage_id!r}")
    return match.group("namespace"), match.group("path")


def create_command_storage_file(
    storage_id: str,
    root_payload: Mapping[str, object],
    data_version: int,
) -> File:
    """Create the SavedData wrapper used by Minecraft Java 26.2."""

    _, storage_path = parse_storage_id(storage_id)
    root = Compound(
        {
            "data": Compound(
                {"contents": Compound({storage_path: payload_to_nbt(root_payload)})}
            ),
            "DataVersion": Int(data_version),
        }
    )

    # nbtlib's outer mapping represents named roots. Minecraft writes an
    # unnamed root compound, hence the explicit empty-string wrapper.
    return File({"": root}, gzipped=True, byteorder="big")


def resolve_output_path(ctx: Context, namespace: str) -> Path:
    configured_path = ctx.meta.get("command_storage_output")
    if configured_path:
        output_path = Path(configured_path)
        if not output_path.is_absolute():
            output_path = ctx.directory / output_path
        return output_path

    output_directory = ctx.output_directory or ctx.directory / "dist"
    return (
        output_directory
        / "world-data"
        / "data"
        / namespace
        / "command_storage.dat"
    )


def write_command_storage(
    ctx: Context,
    storage_id: str,
    root_payload: Mapping[str, object],
) -> Path:
    """Atomically write the world-data companion artifact."""

    namespace, _ = parse_storage_id(storage_id)
    output_path = resolve_output_path(ctx, namespace)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    storage_file = create_command_storage_file(
        storage_id,
        root_payload,
        ctx.meta["command_storage_data_version"],
    )
    temporary_path = output_path.with_suffix(".dat.tmp")
    storage_file.save(temporary_path)
    temporary_path.replace(output_path)
    return output_path


def remove_legacy_global_storage(ctx: Context) -> None:
    """Remove the obsolete single-database artifact from incremental builds."""

    if ctx.meta.get("command_storage_output"):
        return
    resolve_output_path(ctx, "nbs").unlink(missing_ok=True)
