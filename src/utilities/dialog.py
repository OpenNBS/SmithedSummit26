from beet import Context, Dialog
from beet.core.utils import JsonDict

import src.utilities.resource as resource
from src.utilities.resource import Resource, TranslationType
from src.utilities.translation import create_translation


def get_dialog(ctx: Context, asset_path: Resource) -> Dialog:
    if asset_path.value not in ctx.data.dialogs:
        ctx.data.dialogs[asset_path.value] = Dialog()

    return ctx.data.dialogs[asset_path.value]


def get_action(dialog: Dialog) -> list[JsonDict]:
    if "actions" not in dialog.data:
        dialog.data["actions"] = []

    return dialog.data["actions"]


class DialogHelper:
    __ctx__: Context

    __dialog_path__: Resource
    __translation_path__: Resource

    __dialog__: Dialog
    __action_data__: list[JsonDict]

    def __init__(self, ctx: Context, dialog_asset_id: str):
        self.__ctx__ = ctx

        self.__dialog_path__ = resource.get_resource(dialog_asset_id)
        self.__translation_path__ = resource.get_translation(
            TranslationType.DICTIONARY, dialog_asset_id
        )

        self.__dialog__ = get_dialog(ctx, self.__dialog_path__)

    def create_root(self, title: str, body: str, other: JsonDict = {}) -> None:
        title_translation_path = self.__translation_path__.append("title")
        body_translation_path = self.__translation_path__.append("body")

        create_translation(self.__ctx__, title_translation_path, title)
        create_translation(self.__ctx__, body_translation_path, body)

        self.__dialog__.data = {
            "type": "minecraft:notice",
            "title": {"translate": title_translation_path.value},
            "body": {
                "type": "minecraft:plain_message",
                "contents": {"translate": body_translation_path.value},
            },
            **other,
        }

    def create_action(
        self, action_asset_id: str, label: str, action: JsonDict, other: JsonDict = {}
    ) -> None:
        try:
            self.__action_data__
        except AttributeError:
            self.__dialog__.data["type"] = "minecraft:multi_action"
            self.__action_data__ = get_action(self.__dialog__)

        translation_path = self.__translation_path__.append("action", action_asset_id)

        create_translation(self.__ctx__, translation_path, label)

        self.__action_data__.append(
            {"label": {"translate": translation_path.value}, "action": action, **other}
        )

        self.__dialog__.data["actions"] = [*self.__action_data__]
