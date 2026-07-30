import warnings

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
    ctx: Context, translation_resource: Resource, value: str, force: bool = False
) -> str:
    language_data = get_language_data(ctx)

    if force:
        if translation_resource.value in language_data:
            warnings.warn(
                f'translation "{translation_resource.value}" has already been created, but will be overwritten'
            )
    else:
        iteration: int = 1
        while translation_resource.value in language_data:
            translation_resource = translation_resource.suffix(str(iteration))

            iteration += 1

    language_data[translation_resource.value] = value

    return translation_resource.value
