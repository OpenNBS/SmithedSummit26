from beet import Context, subproject


def beet_default(ctx: Context):
    from src.modules.textures import optimize_textures

    ctx.require(
        subproject(
            {
                "require": ["bolt"],
                "data_pack": {"load": {"data/nbs/modules": "src/functions"}},
                "pipeline": ["mecha"],
                "meta": {"bolt": {"entrypoint": "nbs:*"}},
            }
        )
    )

    optimize_textures(ctx)
