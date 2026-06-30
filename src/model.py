from collections import namedtuple
from fnmatch import fnmatch

from beet import Context, ItemModel, Model, Texture, TextureMcmeta
from PIL import Image

models = [
    "logos/world/block",
    "logos/world/wordmark",
    "logos/world/scrolling_panel",
    "props/speaker",
    "props/headphones",
    "props/piano",
    "props/guitar",
    "props/open_sign",
    "globe/sandstone",
    "globe/stone",
    "wall_art",
    "balloon_nbs",
]

NAMESPACE = "nbs"


AssetPaths = namedtuple("AssetPaths", ["texture", "model"])


def get_asset_paths(path: str) -> AssetPaths:
    return AssetPaths(texture=f"{NAMESPACE}:item/{path}", model=f"{NAMESPACE}:{path}")


def create_item_definition(ctx: Context, asset_paths: AssetPaths) -> None:
    ctx.assets.item_models[asset_paths.model] = ItemModel(
        {
            "model": {
                "type": "minecraft:model",
                "model": asset_paths.texture,
                "tints": [
                    {
                        # no shading
                        "type": "minecraft:constant",
                        "value": 66046,
                    },
                    {
                        # darkened
                        "type": "minecraft:constant",
                        "value": -13426150,
                    },
                ],
            }
        }
    )


def create_item_models(ctx: Context) -> None:
    for model in models:
        paths = get_asset_paths(model)

        create_item_definition(ctx, paths)


def generate_scrolling_texture(img: Image.Image, scroll_factor: int = 4) -> Texture:
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


def generate_scrolling_mcmetas(
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


def generate_scrolling_animation(ctx: Context) -> None:
    target_parent = "logos/world"

    static_panel_paths = get_asset_paths(f"{target_parent}/static_panel")

    static_panel_texture = ctx.assets.textures[static_panel_paths.texture]
    scrolling_panel_texture = generate_scrolling_texture(static_panel_texture.image)
    mcmetas = generate_scrolling_mcmetas(scrolling_panel_texture)
    for i, mcmeta in enumerate(mcmetas, start=1):
        scrolling_panel_path = get_asset_paths(f"{target_parent}/scrolling_panel_{i}")

        ctx.assets.textures[scrolling_panel_path.texture] = scrolling_panel_texture
        ctx.assets.textures_mcmeta[scrolling_panel_path.texture] = mcmeta
    del ctx.assets.textures[static_panel_paths.texture]


def create_note_models(ctx: Context) -> None:
    target_parent = "notes"

    target_variant_paths = get_asset_paths(f"{target_parent}/")
    base_texture_paths = get_asset_paths(f"{target_parent}/base")

    note_variants = filter(
        lambda name: name.startswith(target_variant_paths.texture), ctx.assets.textures
    )

    global models
    for i, texture in enumerate(note_variants):
        note_model = Model(
            {
                "parent": base_texture_paths.texture,
                "textures": {"0": texture},
            }
        )
        filename = texture.split("/")[-1]

        note_paths = get_asset_paths(f"{target_parent}/{filename}")

        ctx.assets.models[note_paths.texture] = note_model
        create_item_definition(ctx, note_paths)


def apply_alpha(img: Image.Image, alpha_texture: Image.Image) -> Image.Image:
    def get_alpha_from_level(level: int) -> int:
        if level < 64:
            return 8
        elif level < 128:
            return 7
        elif level < 192:
            return 6
        else:
            return 5

    img = img.convert("RGBA")
    alpha_texture = alpha_texture.convert("L")
    for x in range(img.width):
        for y in range(img.height):
            pixel = img.getpixel((x, y))
            if not isinstance(pixel, tuple):
                raise ValueError(f"Expected RGBA pixel, got {pixel}")
            r, g, b, a = pixel
            if a == 0:
                continue
            level = alpha_texture.getpixel((x, y))
            if not isinstance(level, int):
                raise ValueError(f"Alpha mask image must be in grayscale (L) mode")
            alpha = get_alpha_from_level(level)
            img.putpixel((x, y), (r, g, b, alpha))
    return img


def create_balloon_models(ctx: Context) -> None:
    target_parent = "balloons"

    base_texture_path = get_asset_paths(f"{target_parent}/base")
    alpha_texture_path = get_asset_paths(f"{target_parent}/balloon_alpha")

    balloon_variants = filter(
        lambda name: name.startswith(f"{target_parent}/balloon_"),
        ctx.assets.textures,
    )

    for i, texture in enumerate(balloon_variants):
        if "alpha" in texture:
            continue

        # Create models for each balloon variant
        balloon_model = Model(
            {
                "parent": base_texture_path.texture,
                "textures": {"balloon": texture},
            }
        )

        filename = texture.split("/")[-1]

        balloon_paths = get_asset_paths(f"{target_parent}/{filename}")

        ctx.assets.models[balloon_paths.model] = balloon_model
        create_item_definition(ctx, balloon_paths)

        # Apply alpha to the balloon texture
        balloon_texture = ctx.assets.textures[texture].image
        alpha_texture = ctx.assets.textures[alpha_texture_path.texture].image
        balloon_texture = apply_alpha(balloon_texture, alpha_texture)

        ctx.assets.textures[texture] = Texture(balloon_texture)
    del ctx.assets.textures[alpha_texture_path.texture]


def beet_default(ctx: Context):
    create_item_models(ctx)
    create_note_models(ctx)
    create_balloon_models(ctx)
    generate_scrolling_animation(ctx)
