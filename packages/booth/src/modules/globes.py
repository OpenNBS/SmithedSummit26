from typing import TypedDict

from beet import Context

from nbs_shared.manifest import validate_song_manifest
from src.utilities import resource
from src.utilities.dialog import DialogHelper


class Region(TypedDict):
    id: str
    title: str


REGIONS: list[Region] = [
    {"id": "patched_plateaus", "title": "Patched Plateaus"},
    {"id": "textured_tropics", "title": "Textured Tropics"},
    {"id": "welded_woodlands", "title": "Welded Woodlands"},
]


def generate_globes(ctx: Context) -> None:
    dialog_base_asset = resource.get_asset("credits")

    songs_data = validate_song_manifest(
        resource.read_resource("generated/songs/manifest.json")
    )

    for region in REGIONS:
        dialog_asset = dialog_base_asset.append(region["id"])

        dialog_helper = DialogHelper(ctx, dialog_asset.path())

        dialog_helper.create_root(
            title=f"{region['title']} Credits",
            body="All songs that play throughout this region have been provided by community members who participated in the Summit jam.",
            extra={"columns": 2},
        )

        region_songs_data = filter(
            lambda song_data: song_data["region"] == region["id"], songs_data
        )
        region_songs_data = sorted(
            region_songs_data, key=lambda x: (x["author"], x["title"])
        )

        for region_song_data in region_songs_data:
            id = region_song_data["id"]

            title = region_song_data["title"]
            author = region_song_data["author"]
            url = region_song_data["url"]

            label = f"{author} - {title}"

            dialog_helper.create_action(
                id,
                label,
                action={
                    "type": "open_url",
                    "url": f"https://noteblock.world/song/{url}",
                },
                other={"width": 200},
            )


def beet_default(ctx: Context):
    generate_globes(ctx)
