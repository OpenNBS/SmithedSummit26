import json
from enum import Enum
from typing import Any

from beet import Context

NAMESPACE = "nbs"


class TranslationType(Enum):
    DICTIONARY = "dialog"
    ITEM = "item"
    PAINTING = "painting"


class TextureType(Enum):
    BLOCK = "block"
    ITEM = "item"


class Resource:
    __base__: str
    __delimiter__: str
    __paths__: tuple[str, ...]

    value: str

    def __init__(self, base: str, delimiter: str, *paths: str):
        self.__base__ = base
        self.__delimiter__ = delimiter
        self.__paths__ = paths

        self.value = f"{self.__base__}{self.__delimiter__.join(self.__paths__)}"

    def __str__(self):
        return self.value

    def append(self, *paths: str):
        return Resource(self.__base__, self.__delimiter__, *[*self.__paths__, *paths])


def get_translation(translation_type: TranslationType, *paths: str) -> Resource:
    return Resource(f"{translation_type.value}.{NAMESPACE}.", ".", *paths)


def get_asset(*paths: str) -> Resource:
    return Resource(f"{NAMESPACE}:", "/", *paths)


def get_texture(texture_type: TextureType, *paths: str) -> Resource:
    texture_path = [texture_type.value, *paths]

    return get_asset(*texture_path)


def serialize_path(path: str) -> str:
    return path.lower().replace(".", "")


def read_resource(ctx: Context, file_name: str) -> Any:
    with open(ctx.directory / "src" / "resources" / "data" / file_name, "r") as file:
        return json.load(file)
