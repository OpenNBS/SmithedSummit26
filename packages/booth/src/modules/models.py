from beet import Context
from src.utilities import resource
from src.utilities.model import (
    create_item_model,
    create_item_models_from_base,
    create_models_from_base,
)
from src.utilities.resource import Resource, TextureType

BLOCK_MODELS = [
    "props/guitar",
    "props/open_sign",
    "props/piano",
    "props/speaker",
    "screenshots/maestro",
    "screenshots/studio",
    "screenshots/world",
    "signs/studio/icon",
    "signs/studio/text",
    "signs/studio/text_shadow",
    "signs/world/block",
    "signs/world/text_background",
    "signs/world/text_variant_cafe",
    "signs/world/text_variant_world",
    "signs/world/text_variant_world_shadow",
    "signs/world/wordmark",
    "signs/wall_art",
]

ITEM_MODELS = ["props/headphones", "props/starreact", "signs/billboard"]

UNUSED_NOTE_VARIANTS = [
    "blue",
    "cyan",
    "light_blue",
    "lime",
    "orange",
    "pink",
    "purple",
]

UNUSED_BALLOON_VARIANTS = ["blue"]


def remove_unused_textures(
    ctx: Context,
    texture_resource: Resource,
    unused_variants: list[str],
) -> None:
    for variant in unused_variants:
        variant_texture_resource = texture_resource.append(variant)

        del ctx.assets.textures[variant_texture_resource.value]


def create_static_models(ctx: Context, type: TextureType, path: str) -> None:
    model_resource = resource.get_asset(path)
    texture_resource = resource.get_texture(type, path)

    create_item_model(ctx, model_resource, texture_resource)


def create_dynamic_models(
    ctx: Context,
    type: TextureType,
    path: str,
    unused_variants: list[str] = [],
    dependent_assets: list[str] = [],
) -> None:
    texture_resource = resource.get_texture(type, path)

    create_models_from_base(
        ctx, texture_resource, [*unused_variants, *dependent_assets]
    )

    remove_unused_textures(ctx, texture_resource, unused_variants)


def create_dynamic_pair(
    ctx: Context,
    type: TextureType,
    path: str,
    unused_variants: list[str] = [],
    dependent_assets: list[str] = [],
) -> None:
    model_resource = resource.get_asset(path)
    texture_resource = resource.get_texture(type, path)

    create_models_from_base(ctx, texture_resource, unused_variants)
    create_item_models_from_base(
        ctx, model_resource, texture_resource, [*unused_variants, *dependent_assets]
    )

    remove_unused_textures(ctx, texture_resource, unused_variants)


def generate_block_models(ctx: Context) -> None:
    for path in BLOCK_MODELS:
        create_static_models(ctx, TextureType.BLOCK, path)


def generate_item_models(ctx: Context) -> None:
    for path in ITEM_MODELS:
        create_static_models(ctx, TextureType.ITEM, path)


def generate_dynamic_models(ctx: Context) -> None:
    create_dynamic_pair(ctx, TextureType.BLOCK, "notes", UNUSED_NOTE_VARIANTS)

    create_dynamic_models(
        ctx, TextureType.ITEM, "balloons", UNUSED_BALLOON_VARIANTS, ["string"]
    )


def beet_default(ctx: Context):
    generate_block_models(ctx)
    generate_item_models(ctx)

    generate_dynamic_models(ctx)
