"""Download summit songs from Backblaze B2 and sort them into region folders.

Expects a .env file in the project root (or songs/) with:

    B2_APPLICATION_KEY_ID=...
    B2_APPLICATION_KEY=...
    B2_BUCKET_NAME=...
    B2_ENDPOINT=https://s3.<region>.backblazeb2.com
"""

import csv
import re
import sys

from resources.scripts.util.file_store import (
    FileStore,
    ObjectNotFoundError,
    SCRIPT_DIR,
)

CSV_PATH = SCRIPT_DIR / "songs.csv"

REGION_FOLDERS = {
    "Patched Plateau": "patched_plateaus",
    "Textured Tropic": "textured_tropics",
    "Welded Woodland": "welded_woodlands",
}

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def detect_region_folder(description: str) -> str | None:
    for region_name, folder in REGION_FOLDERS.items():
        if region_name in description:
            return folder
    return None


def sanitize_filename(name: str) -> str:
    return INVALID_FILENAME_CHARS.sub("", name).strip()


def build_filename(title: str, author: str) -> str:
    safe_title = sanitize_filename(title)
    safe_author = sanitize_filename(author)
    return f"{safe_title} - {safe_author}.nbs"


def process_song(store: FileStore, row: dict[str, str]) -> None:
    public_id = row["publicId"]
    title = row["title"]
    author = row["uploader"]
    description = row.get("description", "")

    object_key = f"songs/{public_id}.nbs"

    try:
        data = store.download_object(object_key)
    except ObjectNotFoundError:
        print(f"Could not download {object_key}: object not found in bucket")
        return

    region_folder = detect_region_folder(description)
    if region_folder is None:
        print(
            f"No region found in description for {title!r} ({public_id}); "
            "skipping save"
        )
        return

    destination_dir = SCRIPT_DIR / region_folder
    destination_dir.mkdir(parents=True, exist_ok=True)

    filename = build_filename(title, author)
    destination = destination_dir / filename
    destination.write_bytes(data)
    print(f"Saved {destination.relative_to(SCRIPT_DIR)}")


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

    for row in rows:
        process_song(store, row)


if __name__ == "__main__":
    main()
