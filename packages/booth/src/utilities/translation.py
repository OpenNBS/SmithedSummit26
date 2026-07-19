from beet import Context, Language
from beet.core.utils import JsonDict
from src.utilities.resource import NAMESPACE, Resource


def get_language_data(ctx: Context) -> JsonDict:
    english_path = f"{NAMESPACE}:en_us"

    if english_path not in ctx.assets.languages:
        ctx.assets.languages[english_path] = Language()

    language_data = ctx.assets.languages[english_path].data

    return language_data


def create_translation(
    ctx: Context, translation_resource: Resource, value: str
) -> None:
    language_data = get_language_data(ctx)

    iteration: int = 1
    while translation_resource.value in language_data:
        translation_resource = translation_resource.suffix(str(iteration))

        iteration += 1

    language_data[translation_resource.value] = value
