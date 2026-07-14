from beet import Context, subproject


def beet_default(ctx: Context):
    ctx.require(
        subproject(
            {
                "require": ["bolt", "bolt_selectors"],
                "data_pack": {"load": {"data/nbs/modules": "src/functions"}},
                "pipeline": ["mecha"],
                "meta": {"bolt": {"entrypoint": "nbs:*"}},
            }
        )
    )
