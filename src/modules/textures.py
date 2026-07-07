import io

from beet import Context, Texture, TextureMcmeta
from oxipng import StripChunks, optimize_from_memory
from PIL import Image

from src.utilities import resource
from src.utilities.model import create_item_model
from src.utilities.resource import NAMESPACE, TextureType


def create_scrolling_texture(img: Image.Image, scroll_factor: int = 4) -> Texture:
    width, height = img.size
    tile_size = img.height

    frames = []

    # Grow the image to the left to allow for scrolling
    src = Image.new("RGBA", (width + tile_size, height), (0, 0, 0, 0))
    src.paste(img, (tile_size, 0))

    for x in range(-tile_size, width + tile_size, scroll_factor):
        frame = img.crop((x, 0, x + tile_size, height))
        frames.append(frame)

    output = Image.new("RGBA", (tile_size, height * len(frames)), (0, 0, 0, 0))

    for i, frame in enumerate(frames):
        output.paste(frame, (0, i * height))

    return Texture(output)


def create_scrolling_mcmetas(
    texture: Texture, scroll_factor: int = 4, panel_count: int = 5
) -> list[TextureMcmeta]:
    mcmetas = []

    tile_size, height = texture.image.size
    frames = height // tile_size

    # This is how many frames it takes to reach the second slice of the panel
    frames_per_slice = tile_size // scroll_factor

    for i in range(panel_count):
        start_frame = i * frames_per_slice
        mcmeta = {
            "animation": {
                "interpolate": False,
                "frametime": 1,
                "frames": [
                    i % frames for i in range(start_frame, start_frame + frames)
                ],
            }
        }
        mcmetas.append(TextureMcmeta(mcmeta))

    return mcmetas


def generate_scrolling_panel(ctx: Context) -> None:
    target_parent = "signs/world"

    static_texture_resource = resource.get_texture(
        TextureType.BLOCK, target_parent, "static_panel"
    )

    static_panel_texture = ctx.assets.textures[static_texture_resource.value]

    scrolling_panel_texture = create_scrolling_texture(static_panel_texture.image)
    scrolling_panel_mcmetas = create_scrolling_mcmetas(scrolling_panel_texture)

    for i, mcmeta in enumerate(scrolling_panel_mcmetas, start=1):
        part_texture_resource = resource.get_texture(
            TextureType.BLOCK, target_parent, f"scrolling_panel_{i}"
        )

        ctx.assets.textures[part_texture_resource.value] = scrolling_panel_texture
        ctx.assets.textures_mcmeta[part_texture_resource.value] = mcmeta

    scrolling_model_resource = resource.get_asset(target_parent, "scrolling_panel")
    scrolling_texture_resource = resource.get_texture(
        TextureType.BLOCK, target_parent, "scrolling_panel"
    )

    create_item_model(ctx, scrolling_model_resource, scrolling_texture_resource)

    del ctx.assets.textures[static_texture_resource.value]


def optimize_textures(ctx: Context):
    namespaced_assets = filter(
        lambda name: name.startswith(NAMESPACE),
        ctx.assets.textures,
    )

    for texture in namespaced_assets:
        texture_image = ctx.assets.textures[texture].image
        texture_bytes = ctx.assets.textures[texture].to_bytes(texture_image)

        optimized_texture_bytes = optimize_from_memory(
            texture_bytes, level=6, strip=StripChunks.all()
        )
        optimized_texture_image = Image.open(io.BytesIO(optimized_texture_bytes))

        ctx.assets.textures[texture].image = optimized_texture_image


def beet_default(ctx: Context):
    generate_scrolling_panel(ctx)
