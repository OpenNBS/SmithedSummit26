from beet import Context, PaintingVariant

from src.modules.utilities.resource import Resource


def get_painting_variant(ctx: Context, asset_resource: Resource):
    if asset_resource.value not in ctx.data.painting_variants:
        ctx.data.painting_variants[asset_resource.value] = PaintingVariant()

    return ctx.data.painting_variants[asset_resource.value]
