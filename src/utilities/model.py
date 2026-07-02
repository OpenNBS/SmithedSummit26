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
        raise AttributeError("parent is not allowed when applying model tints")

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
    model_path: Resource,
    texture_path: Resource,
    model_tints: ItemModelTints | None,
) -> None:
    item_model = ItemModel(
        {"model": {"type": "minecraft:model", "model": texture_path.value}}
    )

    apply_item_model_tints(item_model, model_tints)

    ctx.assets.item_models[model_path.value] = item_model


def create_item_model(
    ctx: Context,
    model_path: Resource,
    texture_path: Resource,
) -> None:
    model = ctx.assets.models[texture_path.value]

    model_tints = apply_model_tints(model)

    create_tinted_item_model(ctx, model_path, texture_path, model_tints)


def create_from_base(
    ctx: Context, model_path: Resource, texture_path: Resource
) -> None:
    base_texture_path = texture_path.append("base")

    texture_variants = filter(
        lambda name: name.startswith(texture_path.value), ctx.assets.textures
    )

    base_model = ctx.assets.models[base_texture_path.value]
    base_model_tints = apply_model_tints(base_model)

    for texture_variant in texture_variants:
        model = Model(
            {
                "parent": base_texture_path.value,
                "textures": {"variant": texture_variant},
            }
        )

        file_name = texture_variant.split("/")[-1]

        variant_model_path = model_path.append(file_name)
        variant_texture_path = texture_path.append(file_name)

        ctx.assets.models[variant_texture_path.value] = model

        create_tinted_item_model(
            ctx, variant_model_path, variant_texture_path, base_model_tints
        )
