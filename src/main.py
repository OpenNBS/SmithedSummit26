from beet import Context, subproject


def beet_default(ctx: Context):
    from src.modules.models import (
        generate_block_models,
        generate_dynamic_models,
        generate_item_models,
    )
    from src.modules.paintings import generate_paintings
    from src.modules.textures import generate_scrolling_panel, optimize_textures
    from src.modules.thumbnails import generate_thumbnails

    generate_paintings(ctx)
    generate_thumbnails(ctx)

    generate_block_models(ctx)
    generate_item_models(ctx)
    generate_dynamic_models(ctx)

    generate_scrolling_panel(ctx)

    optimize_textures(ctx)

    ctx.require(
        subproject(
            {
                "require": ["bolt"],
                "data_pack": {"load": {"data/nbs/modules": "src/modules/functions"}},
                "pipeline": ["mecha"],
                "meta": {"bolt": {"entrypoint": "nbs:*"}},
            }
        )
    )
