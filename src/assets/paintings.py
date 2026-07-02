from beet import Context

from src.utilities import resource
from src.utilities.dialog import DialogHelper
from src.utilities.painting import get_painting_variant
from src.utilities.resource import TranslationType, read_data, serialize_path
from src.utilities.translation import create_translation


def generate_paintings(ctx: Context) -> None:
    dialog_asset_id = "painting_credits"
    dialog_helper = DialogHelper(ctx, dialog_asset_id)

    dialog_helper.create_root(
        title="Painting Credits", body="Lorem ipsum", other={"columns": 1}
    )

    painting_data = read_data(ctx, "paintings.json")

    for painting in painting_data:
        author = painting["author"]
        title = painting["title"]
        size = painting["size"]

        painting_asset_id = serialize_path(author)

        translation_resource = resource.get_translation(
            TranslationType.PAINTING, painting_asset_id
        )

        author_translation_resource = translation_resource.append("author")
        title_translation_resource = translation_resource.append("title")

        painting_variant_resource = resource.get_asset(painting_asset_id)

        create_translation(ctx, author_translation_resource, author)
        create_translation(ctx, title_translation_resource, title)

        painting_variant = get_painting_variant(ctx, painting_variant_resource)

        painting_variant.data = {
            "asset_id": painting_variant_resource.value,
            "author": author,
            "title": title,
            "height": size,
            "width": size,
        }

        label = f"{title} by {author}"

        dialog_helper.create_action(
            painting_asset_id,
            label,
            {"type": "copy_to_clipboard", "value": label},
            {"width": 200},
        )
