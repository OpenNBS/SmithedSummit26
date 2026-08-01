import json
from pathlib import Path

from src.songs import SONGS_PATH

SPEAKER_RANGES = [
    {
        "name": "short",
        "range": 16,
    },
    {
        "name": "mid",
        "range": 32,
    },
    {
        "name": "long",
        "range": 48,
    },
]

# Number of 'play' animation variants in the AJ speaker model
ANIM_COUNT = 6

# memo:
INSTRUMENTS = set()

SOUNDS = Path("sounds")

SONG_DATA = SONGS_PATH.parent / "manifest.json"

# Load song manifest
with open(SONG_DATA, "r", encoding="utf-8") as f:
    SONG_MANIFEST = json.load(f)

# Load regions
regions: set[str] = set()
region_counts: dict[str, int] = {}
for song_data in SONG_MANIFEST:
    region = song_data["region"]
    if region is None:
        continue
    regions.add(region)
    region_counts[region] = region_counts.get(region, 0) + 1

REGIONS = regions
REGION_COUNTS = region_counts
