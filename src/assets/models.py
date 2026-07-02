from beet import Context

from src.utilities import resource
from src.utilities.model import create_from_base, create_item_model
from src.utilities.resource import TextureType

BLOCK_MODELS = [
    "globe/sandstone",
    "globe/stone",
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

# TODO: ignored models


def create_static_model(ctx: Context, type: TextureType, path: str) -> None:
    model_resource = resource.get_asset(path)
    texture_resource = resource.get_texture(type, path)

    create_item_model(ctx, model_resource, texture_resource)


def create_base_model(ctx: Context, type: TextureType, path: str) -> None:
    model_resource = resource.get_asset(path)
    texture_resource = resource.get_texture(type, path)

    create_from_base(ctx, model_resource, texture_resource)


def generate_block_models(ctx: Context) -> None:
    for path in BLOCK_MODELS:
        create_static_model(ctx, TextureType.BLOCK, path)


def generate_item_models(ctx: Context) -> None:
    for path in ITEM_MODELS:
        create_static_model(ctx, TextureType.ITEM, path)


def generate_base_models(ctx: Context) -> None:
    create_base_model(ctx, TextureType.BLOCK, "notes")
    create_base_model(ctx, TextureType.BLOCK, "thumbnails")

    create_base_model(ctx, TextureType.ITEM, "balloons")
