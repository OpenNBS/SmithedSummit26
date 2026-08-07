from beet import Context, Dialog
from beet.core.utils import JsonDict

from src.utilities import resource
from src.utilities.resource import Resource, TranslationType
from src.utilities.translation import create_translation


def get_dialog(ctx: Context, asset_resource: Resource) -> Dialog:
    if asset_resource.value not in ctx.data.dialogs:
        ctx.data.dialogs[asset_resource.value] = Dialog()

    return ctx.data.dialogs[asset_resource.value]


def get_action(dialog: Dialog) -> list[JsonDict]:
    if "actions" not in dialog.data:
        dialog.data["actions"] = []

    return dialog.data["actions"]


class DialogHelper:
    __ctx__: Context

    __dialog_resource__: Resource
    __translation_resource__: Resource

    __dialog__: Dialog
    __action_data__: list[JsonDict]

    def __init__(self, ctx: Context, dialog_asset_id: str):
        self.__ctx__ = ctx

        self.__dialog_resource__ = resource.get_asset(dialog_asset_id)
        self.__translation_resource__ = resource.get_translation(
            TranslationType.DICTIONARY, dialog_asset_id.replace("/", ".")
        )

        self.__dialog__ = get_dialog(ctx, self.__dialog_resource__)

    def create_root(self, title: str, body: str, extra: JsonDict = {}) -> None:
        title_translation_resource = self.__translation_resource__.append("title")
        body_translation_resource = self.__translation_resource__.append("body")

        title_translation_string = create_translation(
            self.__ctx__, title_translation_resource, title
        )

        body_translation_string = create_translation(
            self.__ctx__, body_translation_resource, body
        )

        self.__dialog__.data = {
            "type": "minecraft:notice",
            "title": {"translate": title_translation_string},
            "body": {
                "type": "minecraft:plain_message",
                "contents": {"translate": body_translation_string},
            },
            **extra,
        }

    def create_action(
        self,
        action_asset_id: str,
        label: str,
        action: JsonDict,
        icon: str | None = None,
        other: JsonDict = {},
    ) -> None:
        try:
            self.__action_data__
        except AttributeError:
            self.__dialog__.data["type"] = "minecraft:multi_action"
            self.__action_data__ = get_action(self.__dialog__)

        translation_resource = self.__translation_resource__.append(
            "action", action_asset_id
        )

        translation_string = create_translation(
            self.__ctx__, translation_resource, label
        )

        label_component = {"translate": translation_string}

        if icon is not None:
            label_component["font"] = "minecraft:default"

            label_component = [
                {"font": "summit_icons:icons", "translate": f"summit_icons.{icon}"},
                {"font": "minecraft:default", "text": " "},
                label_component,
            ]

        self.__action_data__.append(
            {
                "label": label_component,
                "action": action,
                **other,
            }
        )

        self.__dialog__.data["actions"] = [*self.__action_data__]
