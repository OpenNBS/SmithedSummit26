import os
from io import BytesIO
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

NOT_FOUND_ERROR_CODES = frozenset({"404", "NoSuchKey", "NotFound"})


class FileStoreError(Exception):
    pass


class ObjectNotFoundError(FileStoreError):
    def __init__(self, key: str):
        self.key = key
        super().__init__(f"Object not found: {key}")


def load_env() -> None:
    load_dotenv()


def _get_b2_client():
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


def _get_bucket_name() -> str:
    bucket = os.environ.get("B2_BUCKET_NAME")
    if not bucket:
        raise SystemExit("Missing required environment variable: B2_BUCKET_NAME")
    return bucket


def _is_not_found(exc: ClientError) -> bool:
    error_code = exc.response.get("Error", {}).get("Code", "")
    return error_code in NOT_FOUND_ERROR_CODES


class FileStore:
    def __init__(self):
        load_env()
        self._client = _get_b2_client()
        self._bucket = _get_bucket_name()

    def download_object(self, key: str) -> bytes:
        try:
            buffer = BytesIO()
            self._client.download_fileobj(self._bucket, key, buffer)
            return buffer.getvalue()
        except ClientError as exc:
            if _is_not_found(exc):
                raise ObjectNotFoundError(key) from exc
            raise FileStoreError(f"Failed to download {key}") from exc
