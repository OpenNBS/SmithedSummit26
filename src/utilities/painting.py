from beet import Context, PaintingVariant

from src.utilities.resource import Resource


def get_painting_variant(ctx: Context, asset_path: Resource):
    if asset_path.value not in ctx.data.painting_variants:
        ctx.data.painting_variants[asset_path.value] = PaintingVariant()

    return ctx.data.painting_variants[asset_path.value]
