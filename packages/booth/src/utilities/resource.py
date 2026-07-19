import json
from enum import Enum
from typing import Any

from beet import Context
from nbs_shared.constants import NAMESPACE
from nbs_shared.project import DATA_DIRECTORY


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

        self.value = f"{self.__base__}{self.__merge__()}"

    def __merge__(self) -> str:
        return self.__delimiter__.join(self.__paths__)

    def __str__(self) -> str:
        return self.value

    def append(self, *paths: str):
        return Resource(self.__base__, self.__delimiter__, *[*self.__paths__, *paths])

    def suffix(self, value: str):
        last_path = self.__paths__[-1]
        rest_paths = self.__paths__[:-1]

        suffixed_last_path = f"{last_path}_{value}"

        return Resource(
            self.__base__, self.__delimiter__, *[*rest_paths, suffixed_last_path]
        )

    def path(self) -> str:
        return self.__merge__()


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
    with open(DATA_DIRECTORY / file_name, "r") as file:
        return json.load(file)
