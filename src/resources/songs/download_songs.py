"""Download summit songs from Backblaze B2 and sort them into region folders.

Expects a .env file in the project root (or songs/) with:

    B2_APPLICATION_KEY_ID=...
    B2_APPLICATION_KEY=...
    B2_BUCKET_NAME=...
    B2_ENDPOINT=https://s3.<region>.backblazeb2.com
"""

import csv
import os
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CSV_PATH = SCRIPT_DIR / "songs.csv"

REGION_FOLDERS = {
    "Patched Plateau": "patched_plateaus",
    "Textured Tropic": "textured_tropics",
    "Welded Woodland": "welded_woodlands",
}

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def load_env() -> None:
    for env_path in (SCRIPT_DIR / ".env", PROJECT_ROOT / ".env"):
        if env_path.is_file():
            load_dotenv(env_path)
            return
    load_dotenv()


def get_b2_client():
    key_id = os.environ.get("B2_APPLICATION_KEY_ID")
    application_key = os.environ.get("B2_APPLICATION_KEY")
    endpoint = os.environ.get("B2_ENDPOINT")

    missing = [
        name
        for name, value in (
            ("B2_APPLICATION_KEY_ID", key_id),
            ("B2_APPLICATION_KEY", application_key),
            ("B2_ENDPOINT", endpoint),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            f"Missing required environment variable(s): {', '.join(missing)}"
        )

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=application_key,
    )


def get_bucket_name() -> str:
    bucket = os.environ.get("B2_BUCKET_NAME")
    if not bucket:
        raise SystemExit("Missing required environment variable: B2_BUCKET_NAME")
    return bucket


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


def download_object(client, bucket: str, key: str) -> bytes:
    buffer = BytesIO()
    client.download_fileobj(bucket, key, buffer)
    return buffer.getvalue()


def process_song(client, bucket: str, row: dict[str, str]) -> None:
    public_id = row["publicId"]
    title = row["title"]
    author = row["uploader"]
    description = row.get("description", "")

    object_key = f"songs/{public_id}.nbs"

    try:
        data = download_object(client, bucket, object_key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            print(f"Could not download {object_key}: object not found in bucket")
            return
        raise

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
    load_env()
    client = get_b2_client()
    bucket = get_bucket_name()

    if not CSV_PATH.is_file():
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    with CSV_PATH.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list[dict[str | Any, str | Any]](reader)

    if len(sys.argv) > 1:
        requested_ids = set[str](sys.argv[1:])
        rows = [row for row in rows if row["publicId"] in requested_ids]
        if not rows:
            raise SystemExit("No matching songs found in CSV for the given public IDs")

    for row in rows:
        process_song(client, bucket, row)


if __name__ == "__main__":
    main()
