from beet import Context


def beet_default(ctx: Context):
    from src.assets.models import (
        generate_base_models,
        generate_block_models,
        generate_item_models,
    )
    from src.assets.paintings import generate_paintings
    from src.assets.textures import generate_scrolling_animation, optimize_textures
    from src.assets.thumbnails import generate_thumbnails

    generate_paintings(ctx)
    generate_thumbnails(ctx)

    generate_block_models(ctx)
    generate_item_models(ctx)
    generate_base_models(ctx)

    generate_scrolling_animation(ctx)

    optimize_textures(ctx)
