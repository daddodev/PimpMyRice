import os
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pimpmyrice.config import (
    BASE_STYLE_FILE,
    CONFIG_FILE,
    MODULES_DIR,
    PALETTES_DIR,
    STYLES_DIR,
    THEMES_DIR,
)
from pimpmyrice.files import load_json
from pimpmyrice.logger import get_logger

log = get_logger(__name__)


async def process_edit_args(args: dict[str, Any]) -> None:
    def open_editor(dir: Path) -> None:
        os.system(f'$EDITOR "{dir}"')

    if not args["edit"]:
        return

    if args["base-style"]:
        open_editor(BASE_STYLE_FILE)
    elif args["theme"]:
        theme = args["THEME"]

        if not theme:
            config = load_json(CONFIG_FILE)
            theme = config["theme"]

        theme_json_path = THEMES_DIR / theme / "theme.json"
        if not theme_json_path.is_file():
            log.error(f'theme "{theme}" not found')
            return

        open_editor(theme_json_path)

    elif args["style"]:
        style = args["STYLE"]

        style_path = STYLES_DIR / f"{style}.json"
        if not style_path.is_file():
            log.error(f'style "{style}" not found')
            return

        open_editor(style_path)

    elif args["palette"]:
        palette = args["PALETTE"]

        palette_path = PALETTES_DIR / f"{palette}.json"
        if not palette_path.is_file():
            log.error(f'palette "{palette}" not found')
            return

        open_editor(palette_path)

    elif args["module"]:
        module = args["MODULE"]

        module_path = MODULES_DIR / module
        if not (module_path / "module.yaml").is_file():
            log.error(f'module "{module}" not found')
            return

        open_editor(module_path)
