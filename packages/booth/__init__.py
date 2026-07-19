from beet import Context, subproject


def beet_default(ctx: Context) -> None:
    ctx.require(subproject("@booth"))
