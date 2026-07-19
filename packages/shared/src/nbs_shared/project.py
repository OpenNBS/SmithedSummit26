from pathlib import Path


def find_repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file() and (parent / "data").is_dir():
            return parent
    raise RuntimeError("Could not locate the repository root from nbs_shared")


REPOSITORY_ROOT = find_repository_root()
DATA_DIRECTORY = REPOSITORY_ROOT / "data"
