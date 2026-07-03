from beet import Context

from src.utilities import resource
from src.utilities.model import (
    create_item_model,
    create_item_models_from_base,
    create_models_from_base,
)
from src.utilities.resource import TextureType

BLOCK_MODELS = [
    "props/piano",
    "props/guitar",
    "props/speaker",
    "props/open_sign",
    "logos/world/block",
    "logos/world/wordmark",
    "logos/world/text_variant_world",
    "logos/world/text_variant_world_shadow",
    "logos/world/text_variant_cafe",
    "logos/world/text_background",
    "logos/studio/icon",
    "logos/studio/text",
    "logos/studio/text_shadow",
]

ITEM_MODELS = [
    "props/headphones",
    "wall_art",
]

IGNORED_NOTE_VARIANTS = [
    "blue",
    "cyan",
    "light_blue",
    "lime",
    "orange",
    "pink",
    "purple",
]

IGNORED_THUMBNAIL_VARIANTS = []

IGNORED_GLOBE_VARIANTS = []

IGNORED_BALLOON_VARIANTS = []


def create_static_models(ctx: Context, type: TextureType, path: str) -> None:
    model_resource = resource.get_asset(path)
    texture_resource = resource.get_texture(type, path)

    create_item_model(ctx, model_resource, texture_resource)


def create_dynamic_models(
    ctx: Context, type: TextureType, path: str, ignored_variants=[]
) -> None:
    texture_resource = resource.get_texture(type, path)

    create_models_from_base(ctx, texture_resource, ignored_variants)


def create_dynamic_pair(
    ctx: Context, type: TextureType, path: str, ignored_variants=[]
) -> None:
    model_resource = resource.get_asset(path)
    texture_resource = resource.get_texture(type, path)

    create_models_from_base(ctx, texture_resource, ignored_variants)
    create_item_models_from_base(
        ctx, model_resource, texture_resource, ignored_variants
    )


def generate_block_models(ctx: Context) -> None:
    for path in BLOCK_MODELS:
        create_static_models(ctx, TextureType.BLOCK, path)


def generate_item_models(ctx: Context) -> None:
    for path in ITEM_MODELS:
        create_static_models(ctx, TextureType.ITEM, path)


def generate_dynamic_models(ctx: Context) -> None:
    create_dynamic_pair(ctx, TextureType.BLOCK, "notes", IGNORED_NOTE_VARIANTS)
    create_dynamic_pair(ctx, TextureType.BLOCK, "globe", IGNORED_GLOBE_VARIANTS)
    create_dynamic_pair(
        ctx, TextureType.BLOCK, "thumbnails", IGNORED_THUMBNAIL_VARIANTS
    )

    create_dynamic_models(
        ctx, TextureType.ITEM, "balloons", ["string", *IGNORED_BALLOON_VARIANTS]
    )
