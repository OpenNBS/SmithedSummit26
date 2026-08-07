# /// script
# requires-python = ">=3.14,<4"
# dependencies = [
#     "boto3>=1.38.0,<2",
#     "pillow>=12.0.0,<13",
#     "pynbs>=1.1.0,<2",
#     "python-dotenv>=1.1.0,<2",
# ]
# ///

"""Generate note-block pixel-art thumbnails from summit songs stored in Backblaze B2.

Reads thumbnail metadata from data/source/thumbnails.json, downloads each song, and
saves a PNG to data/generated/thumbnails/{author}.png.

Expects a .env file (see scripts/download_songs.py) with B2 credentials.
"""

import json
import sys
from io import BytesIO
from pathlib import Path

import pynbs
from PIL import Image

from _lib.file_store import (
    FileStore,
    ObjectNotFoundError,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = REPOSITORY_ROOT / "data"
THUMBNAILS_JSON = DATA_DIRECTORY / "source" / "thumbnails.json"
OUTPUT_DIR = DATA_DIRECTORY / "generated" / "thumbnails"

DEFAULT_ZOOM_LEVEL = 3
MIN_ZOOM_LEVEL = 1
MAX_ZOOM_LEVEL = 5
BASE_WIDTH = 40
BASE_HEIGHT = 24

INSTRUMENT_COLORS = [
    "#1964ac",
    "#3c8e48",
    "#be6b6b",
    "#bebe19",
    "#9d5a98",
    "#572b21",
    "#bec65c",
    "#be19be",
    "#52908d",
    "#bebebe",
    "#1991be",
    "#be2328",
    "#be5728",
    "#19be19",
    "#be1957",
    "#575757",
    "#d26b50",
    "#c38969",
    "#78a07a",
    "#5ca087",
]


# zoomLevel -> Size
# 1 -> 160×96
# 2 -> 80×48
# 3 -> 40×24
# 4 -> 20×12
# 5 -> 10×6


def canvas_size(zoom_level: int) -> tuple[int, int]:
    zoom_level = max(MIN_ZOOM_LEVEL, min(MAX_ZOOM_LEVEL, int(zoom_level)))
    scale = 2 ** (DEFAULT_ZOOM_LEVEL - zoom_level)
    return int(BASE_WIDTH * scale), int(BASE_HEIGHT * scale)


def parse_hex_color(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.removeprefix("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def instrument_color(instrument: int, default_instruments: int) -> tuple[int, int, int]:
    if default_instruments <= 0:
        color_index = instrument % len(INSTRUMENT_COLORS)
    else:
        color_index = instrument % default_instruments
    return parse_hex_color(INSTRUMENT_COLORS[color_index % len(INSTRUMENT_COLORS)])


def generate_thumbnail(song: pynbs.File, thumbnail_data: dict) -> Image.Image:
    zoom_level = thumbnail_data.get("zoomLevel", DEFAULT_ZOOM_LEVEL)
    start_tick = thumbnail_data["startTick"]
    start_layer = thumbnail_data["startLayer"]
    background_color = parse_hex_color(thumbnail_data["backgroundColor"])

    width, height = canvas_size(zoom_level)
    end_tick = start_tick + width - 1
    end_layer = start_layer + height - 1
    default_instruments = song.header.default_instruments

    img = Image.new("RGB", (width, height), background_color)

    for note in song.notes:
        if note.tick < start_tick or note.tick > end_tick:
            continue
        if note.layer < start_layer or note.layer > end_layer:
            continue

        x = note.tick - start_tick
        y = note.layer - start_layer
        img.putpixel((x, y), instrument_color(note.instrument, default_instruments))

    return img


def process_thumbnail(store: FileStore, entry: dict) -> None:
    song_id = entry["url"]
    thumbnail_data = entry["thumbnailData"]
    object_key = f"songs/{song_id}.nbs"

    try:
        data = store.download_object(object_key)
    except ObjectNotFoundError:
        print(f"Could not download {object_key}: object not found in bucket")
        return

    song = pynbs.Parser(BytesIO(data)).read_file()
    img = generate_thumbnail(song, thumbnail_data)

    name = entry["author"].lower()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT_DIR / f"{name}.png"
    img.save(destination)
    print(f"Saved {destination.relative_to(REPOSITORY_ROOT)}")


def main() -> None:
    store = FileStore()

    if not THUMBNAILS_JSON.is_file():
        raise SystemExit(f"Thumbnails JSON not found: {THUMBNAILS_JSON}")

    with THUMBNAILS_JSON.open(encoding="utf-8") as json_file:
        entries = json.load(json_file)

    if len(sys.argv) > 1:
        requested_ids = set(sys.argv[1:])
        entries = [entry for entry in entries if entry["id"] in requested_ids]
        if not entries:
            raise SystemExit(
                "No matching thumbnails found in JSON for the given song IDs"
            )

    for entry in entries:
        process_thumbnail(store, entry)


if __name__ == "__main__":
    main()
