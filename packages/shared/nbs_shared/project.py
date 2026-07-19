from pathlib import Path


def find_repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "data").is_dir():
            return parent
    raise RuntimeError("Could not locate the repository root from nbs_shared")


REPOSITORY_ROOT = find_repository_root()
DATA_DIRECTORY = REPOSITORY_ROOT / "data"
SOURCE_DIRECTORY = DATA_DIRECTORY / "source"
GENERATED_DIRECTORY = DATA_DIRECTORY / "generated"

SONGS_MANIFEST_PATH = GENERATED_DIRECTORY / "songs" / "manifest.json"
SONGS_FILES_DIRECTORY = GENERATED_DIRECTORY / "songs" / "files"
THUMBNAILS_DIRECTORY = GENERATED_DIRECTORY / "thumbnails"
