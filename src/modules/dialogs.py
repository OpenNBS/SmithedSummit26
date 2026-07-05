from typing import NotRequired, TypedDict

from beet import Context

from src.modules.utilities.dialog import DialogHelper


class LinkData(TypedDict):
    action_id: str

    icon: NotRequired[str]

    label: str
    url: str


class LinkDialog(TypedDict):
    dialog_id: str

    title: str
    body: str

    links: list[LinkData]


DISCORD_ACTION: LinkData = {
    "action_id": "discord",
    "icon": "discord",
    "label": "Discord",
    "url": "https://discord.gg/w35BqQp",
}


LINK_DIALOGS: list[LinkDialog] = [
    {
        "dialog_id": "world",
        "title": "Note Block World",
        "body": "A website to share, discover and listen to note block music.",
        "links": [
            {
                "action_id": "homepage",
                "label": "Homepage",
                "url": "https://noteblock.world",
            },
            {
                "action_id": "blog",
                "label": "Blog",
                "url": "https://noteblock.world/blog",
            },
            {
                "action_id": "search",
                "label": "🔎 #summit26",
                "url": "https://noteblock.world/search?q=%23summit26",
            },
            DISCORD_ACTION,
            {
                "action_id": "source",
                "icon": "github",
                "label": "GitHub",
                "url": "https://github.com/OpenNBS/NoteBlockWorld",
            },
        ],
    },
    {
        "dialog_id": "studio",
        "title": "Note Block Studio",
        "body": "An open-source Minecraft music maker.",
        "links": [
            {
                "action_id": "homepage",
                "label": "Homepage",
                "url": "https://noteblock.studio",
            },
            {
                "action_id": "download",
                "label": "Download",
                "url": "https://github.com/OpenNBS/NoteBlockStudio/releases/latest/download/Minecraft.Note.Block.Studio.exe",
            },
            DISCORD_ACTION,
            {
                "action_id": "source",
                "icon": "github",
                "label": "GitHub",
                "url": "https://github.com/OpenNBS/NoteBlockStudio",
            },
        ],
    },
]


def create_link_dialog(ctx: Context, link_dialog: LinkDialog):
    dialog_helper = DialogHelper(ctx, f"links/{link_dialog['dialog_id']}")

    dialog_helper.create_root(
        link_dialog["title"],
        link_dialog["body"],
        {"columns": 1, "after_action": "none", "pause": False},
    )

    for link in link_dialog["links"]:
        icon = None

        if "icon" in link:
            icon = link["icon"]

        dialog_helper.create_action(
            link["action_id"],
            link["label"],
            action={"type": "open_url", "url": link["url"]},
            icon=icon,
        )


def generate_link_dialogs(ctx: Context):
    for link_dialog in LINK_DIALOGS:
        create_link_dialog(ctx, link_dialog)
