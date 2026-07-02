from beet import Context, Language
from beet.core.utils import JsonDict

from src.utilities.resource import NAMESPACE, Resource


def get_language_data(ctx: Context) -> JsonDict:
    english_path = f"{NAMESPACE}:en_us"

    if english_path not in ctx.assets.languages:
        ctx.assets.languages[english_path] = Language()

    language_data = ctx.assets.languages[english_path].data

    return language_data


def create_translation(ctx: Context, translation_path: Resource, value: str) -> None:
    language_data = get_language_data(ctx)

    language_data[translation_path.value] = value
