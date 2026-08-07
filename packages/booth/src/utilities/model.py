import warnings
from typing import TypedDict

from beet import Context, Model
from beet.library.resource_pack import ItemModel
from pydantic.config import JsonDict

from src.utilities.resource import Resource

NO_SHADE_TINT = {
    "type": "minecraft:constant",
    "value": 66046,
}

DARKENED_TINT = {
    "type": "minecraft:constant",
    "value": -13426150,
}


class ItemModelTints(TypedDict):
    tints: list[JsonDict]

    no_shade_index: int | None
    darkened_index: int | None


def apply_model_tints(model: Model) -> ItemModelTints | None:
    if "parent" in model.data:
        file_name: str = str(model.original.ensure_source_path).split("/")[-1]

        warnings.warn(
            f'"parent" will not be modified when applying model tints in "{file_name}"'
        )

        return

    tints: list[JsonDict] = []

    no_shade_index = None
    darkened_index = None

    if "elements" not in model.data:
        return None

    for element in model.data["elements"]:
        for _, value in element["faces"].items():
            if "tintindex" not in value:
                continue

            if value["tintindex"] == "#noshade":
                if no_shade_index is None:
                    tints.append(NO_SHADE_TINT)

                    no_shade_index = len(tints) - 1

                value["tintindex"] = no_shade_index

            if value["tintindex"] == "#darkened":
                if darkened_index is None:
                    tints.append(DARKENED_TINT)

                    darkened_index = len(tints) - 1

                value["tintindex"] = darkened_index

    return ItemModelTints(
        {
            "tints": tints,
            "no_shade_index": no_shade_index,
            "darkened_index": darkened_index,
        }
    )


def apply_item_model_tints(
    item_model: ItemModel, item_model_tints: ItemModelTints | None
) -> None:
    if item_model_tints is None:
        return

    if (
        item_model_tints["no_shade_index"] is not None
        or item_model_tints["darkened_index"] is not None
    ):
        item_model.data["model"]["tints"] = item_model_tints["tints"]


def create_tinted_item_model(
    ctx: Context,
    model_resource: Resource,
    texture_resource: Resource,
    model_tints: ItemModelTints | None = None,
) -> None:
    item_model = ItemModel(
        {"model": {"type": "minecraft:model", "model": texture_resource.value}}
    )

    apply_item_model_tints(item_model, model_tints)

    ctx.assets.item_models[model_resource.value] = item_model


def create_item_model(
    ctx: Context,
    model_resource: Resource,
    texture_resource: Resource,
) -> None:
    model = ctx.assets.models[texture_resource.value]

    model_tints = apply_model_tints(model)

    create_tinted_item_model(ctx, model_resource, texture_resource, model_tints)


def get_variants(
    ctx: Context, texture_resource: Resource, unused_variants: list[str] = []
) -> list[tuple[str, str]]:
    variant_texture_resources = list(
        filter(
            lambda path: path.startswith(texture_resource.value), ctx.assets.textures
        )
    )

    variants = list(
        map(lambda path: (path.split("/")[-1], path), variant_texture_resources)
    )

    return list(filter(lambda variant: variant[0] not in unused_variants, variants))


def create_model(
    ctx: Context, base_model_resource: Resource, variant_texture_resource: Resource
) -> None:
    model = Model(
        {
            "parent": base_model_resource.value,
            "textures": {"variant": variant_texture_resource.value},
        }
    )

    ctx.assets.models[variant_texture_resource.value] = model


def create_models_from_base(
    ctx: Context, texture_resource: Resource, unused_variants: list[str] = []
) -> None:
    base_model_resource = texture_resource.append("base")

    texture_variants = get_variants(ctx, texture_resource, unused_variants)

    for variant_name, variant_texture_resource in texture_variants:
        variant_texture_resource = texture_resource.append(variant_name)

        create_model(ctx, base_model_resource, variant_texture_resource)


def create_item_models_from_base(
    ctx: Context,
    model_resource: Resource,
    texture_resource: Resource,
    unused_variants: list[str] = [],
) -> None:
    base_texture_resource = texture_resource.append("base")

    base_model = ctx.assets.models[base_texture_resource.value]
    base_model_tints = apply_model_tints(base_model)

    texture_variants = get_variants(ctx, texture_resource, unused_variants)

    for variant_name, _ in texture_variants:
        variant_texture_resource = texture_resource.append(variant_name)
        variant_model_resource = model_resource.append(variant_name)

        create_tinted_item_model(
            ctx, variant_model_resource, variant_texture_resource, base_model_tints
        )
