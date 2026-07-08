import os
from io import BytesIO
from pathlib import Path

import boto3
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


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


def download_object(client, bucket: str, key: str) -> bytes:
    buffer = BytesIO()
    client.download_fileobj(bucket, key, buffer)
    return buffer.getvalue()
