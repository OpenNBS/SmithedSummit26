from beet import Context

from src.utilities import resource
from src.utilities.model import (
    create_item_model,
    create_item_models_from_base,
    create_models_from_base,
)
from src.utilities.resource import Resource, TextureType

BLOCK_MODELS = [
    "logos/studio/icon",
    "logos/studio/text",
    "logos/studio/text_shadow",
    "logos/world/block",
    "logos/world/text_background",
    "logos/world/text_variant_cafe",
    "logos/world/text_variant_world",
    "logos/world/text_variant_world_shadow",
    "logos/world/wordmark",
    "props/guitar",
    "props/open_sign",
    "props/piano",
    "props/speaker",
]

ITEM_MODELS = [
    "props/headphones",
    "wall_art",
]

UNUSED_NOTE_VARIANTS = [
    "blue",
    "cyan",
    "light_blue",
    "lime",
    "orange",
    "pink",
    "purple",
]

UNUSED_THUMBNAIL_VARIANTS = []

UNUSED_GLOBE_VARIANTS = []

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
    create_dynamic_pair(ctx, TextureType.BLOCK, "globes", UNUSED_GLOBE_VARIANTS)
    create_dynamic_pair(ctx, TextureType.BLOCK, "thumbnails", UNUSED_THUMBNAIL_VARIANTS)

    create_dynamic_models(
        ctx, TextureType.ITEM, "balloons", UNUSED_BALLOON_VARIANTS, ["string"]
    )
