from beet import Context

from nbs_shared.thumbnails import validate_thumbnail_catalog
from src.utilities import resource
from src.utilities.dialog import DialogHelper
from src.utilities.model import create_model, create_tinted_item_model
from src.utilities.resource import TextureType, read_resource


def generate_thumbnails(ctx: Context) -> None:
    dialog_asset_id = "credits/thumbnails"
    dialog_helper = DialogHelper(ctx, dialog_asset_id)

    dialog_helper.create_root(
        title="Thumbnail Credits",
        body="All thumbnails have been sourced from songs uploaded to Note Block World. That's right, these pixels are note blocks!",
        extra={"columns": 1},
    )

    thumbnail_data = validate_thumbnail_catalog(
        read_resource("source/thumbnails.json")
    )

    thumbnail_texture_resource = resource.get_texture(TextureType.BLOCK, "thumbnails")
    thumbnail_asset_resource = resource.get_asset("thumbnails")

    base_model_resource = thumbnail_texture_resource.append("base")

    for thumbnail in thumbnail_data:
        author = thumbnail["author"]
        title = thumbnail["title"]
        url = thumbnail["url"]

        id = author.lower()

        variant_texture_resource = thumbnail_texture_resource.append(id)
        variant_asset_resource = thumbnail_asset_resource.append(id)

        create_model(ctx, base_model_resource, variant_texture_resource)
        create_tinted_item_model(ctx, variant_asset_resource, variant_texture_resource)

        action_asset_id = resource.serialize_path(author)

        label = f"{author} - {title}"

        dialog_helper.create_action(
            action_asset_id,
            label,
            action={
                "type": "open_url",
                "url": f"https://noteblock.world/song/{url}",
            },
            other={"width": 200},
        )


def beet_default(ctx: Context):
    generate_thumbnails(ctx)
