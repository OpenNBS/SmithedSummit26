import io
import logging

from beet import Context
from oxipng import StripChunks, optimize_from_memory
from PIL import Image

from src.utilities.resource import NAMESPACE

logger = logging.getLogger(__name__)


def optimize_textures(ctx: Context):
    logger.info("Optimizing textures...")

    namespaced_assets = filter(
        lambda name: name.startswith(NAMESPACE),
        ctx.assets.textures,
    )

    for texture in namespaced_assets:
        logger.debug(f"Optimizing texture: {texture}")

        texture_image = ctx.assets.textures[texture].image
        texture_bytes = ctx.assets.textures[texture].to_bytes(texture_image)

        optimized_texture_bytes = optimize_from_memory(
            texture_bytes, level=6, strip=StripChunks.all()
        )
        optimized_texture_image = Image.open(io.BytesIO(optimized_texture_bytes))

        ctx.assets.textures[texture].image = optimized_texture_image
