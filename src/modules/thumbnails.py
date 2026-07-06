from beet import Context

from src.utilities import resource
from src.utilities.dialog import DialogHelper
from src.utilities.resource import read_resource


def generate_thumbnails(ctx: Context) -> None:
    dialog_asset_id = "credits/thumbnails"
    dialog_helper = DialogHelper(ctx, dialog_asset_id)

    dialog_helper.create_root(
        title="Thumbnail Credits",
        body="These thumbnails have been sourced from songs uploaded to Note Block World. That's right, these are note blocks!",
        other={"columns": 1},
    )

    thumbnail_data = read_resource(ctx, "thumbnails.json")

    for thumbnail in thumbnail_data:
        author = thumbnail["author"]
        title = thumbnail["title"]
        song_id = thumbnail["id"]

        action_asset_id = resource.serialize_path(author)

        label = f"{author} - {title}"

        dialog_helper.create_action(
            action_asset_id,
            label,
            action={
                "type": "open_url",
                "url": f"https://noteblock.world/song/{song_id}",
            },
            other={"width": 200},
        )
