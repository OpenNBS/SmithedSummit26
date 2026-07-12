"""Download summit songs from Backblaze B2 and sort them into region folders.

Expects a .env file in the project root (or songs/) with:

    B2_APPLICATION_KEY_ID=...
    B2_APPLICATION_KEY=...
    B2_BUCKET_NAME=...
    B2_ENDPOINT=https://s3.<region>.backblazeb2.com
"""

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

from src.resources.scripts.util.file_store import (
    SCRIPT_DIR,
    FileStore,
    ObjectNotFoundError,
)

SONGS_DIR = SCRIPT_DIR / "songs"
DATA_DIR = SCRIPT_DIR / "data"

CSV_PATH = SONGS_DIR / "songs.csv"

REGIONS = {
    "Patched Plateau": "patched_plateaus",
    "Textured Tropic": "textured_tropics",
    "Welded Woodland": "welded_woodlands",
}

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def detect_region(description: str) -> str | None:
    for region_name, region_id in REGIONS.items():
        if region_name in description:
            return region_id
    return None


def extract_id_from_title(title: str) -> str:

    print(title)
    # Remove region names
    for region_name in REGIONS:
        title = title.replace(f"{region_name}s", "").replace(region_name, " ")

    # Remove anything between any opening and closing bracket, one level only
    title = re.sub(r"[\(\[\{].*?[\)\]\}]", "", title)

    # Replace non-core title elements
    title = (
        title.split("feat.")[0]
        .split("Note Block")[0]
        .split("#summit26")[0]
        .split("OST")[-1]
        .split("Super Mario")[-1]
    )

    # Normalize '-' separators, then keep only the first part
    title = re.sub(r"\s*[-]\s*", "-", title)
    title = title.strip("-").strip()
    title = title.split("-")[0]

    # Lowercase and replace spaces with underscores
    title = title.lower()
    title = re.sub(r"\s*[''-]\s*", "", title)
    title = re.sub(r"\s*[,&~:;]\s*", " ", title)
    title = title.replace(" ", "_")

    # Replace diacritics
    normalized = unicodedata.normalize("NFKD", title)
    clean_title = normalized.encode("ascii", "ignore").decode("ascii")

    return clean_title


def sanitize_filename(name: str) -> str:
    return INVALID_FILENAME_CHARS.sub("", name).strip()


def build_filename(title: str) -> str:
    safe_title = sanitize_filename(title)
    return f"{safe_title}.nbs"


def ensure_file_download(store: FileStore, object_key: str, destination: Path):
    if Path(destination).is_file():
        print(f"File already exists: {destination.name}")
        return

    try:
        data = store.download_object(object_key)
        destination.write_bytes(data)
        print(f"Saved {destination.name}")
    except ObjectNotFoundError:
        print(f"Could not download {object_key}: object not found in bucket")


def process_song(store: FileStore, row: dict[str, str]) -> dict[str, str] | None:
    public_id = row["publicId"]
    title = row["title"]
    author = row["uploader"]
    description = row.get("description", "")
    song_id = extract_id_from_title(title)

    object_key = f"songs/{public_id}.nbs"
    filename = build_filename(song_id)
    destination = SONGS_DIR / filename
    ensure_file_download(store, object_key, destination)

    region_id = detect_region(description)
    if region_id is None:
        print(f"Warning: No region found in description for {title!r} ({public_id})")

    song_data = {
        "id": song_id,
        "title": title,
        "region": region_id,
        "author": author,
        "url": f"https://noteblock.world/song/{public_id}",
    }

    return song_data


def main() -> None:
    store = FileStore()

    if not CSV_PATH.is_file():
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    with CSV_PATH.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list[dict[str, str]](reader)

    if len(sys.argv) > 1:
        requested_ids = set[str](sys.argv[1:])
        rows = [row for row in rows if row["publicId"] in requested_ids]
        if not rows:
            raise SystemExit("No matching songs found in CSV for the given public IDs")

    manifest_data = []
    for row in rows:
        song_data = process_song(store, row)
        if song_data:
            manifest_data.append(song_data)

    manifest_path = DATA_DIR / "songs.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=4, separators=(",", ": "))


if __name__ == "__main__":
    main()
