import os
from pathlib import Path
from typing import Any

from .colors import palette_display_string
from .config import (BASE_STYLE_FILE, MODULES_DIR, PALETTES_DIR, STYLES_DIR,
                     THEMES_DIR)
from .logger import get_logger
from .theme import ThemeManager
from .utils import Result

log = get_logger(__name__)


async def process_edit_args(args: dict[str, Any]) -> None:
    def open_editor(dir: Path) -> None:
        os.system(f'$EDITOR "{dir}"')

    if not args["edit"]:
        return

    album = args["--album"] or "default"

    if args["keywords"]:
        open_editor(BASE_STYLE_FILE)
    elif args["theme"]:
        theme = args["THEME"]

        theme_path = THEMES_DIR / album / theme / "theme.json"
        if not theme_path.is_file():
            log.error(f'theme "{theme}" not found in album "{album}"')
            return

        open_editor(theme_path)

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


async def process_args(tm: ThemeManager, args: dict[str, Any]) -> Result:
    res = Result()

    options = {
        "album": args["--album"],
        "mode_name": args["--mode"],
        "styles_names": args["--style"],
        "palette_name": args["--palette"],
    }

    if modules := args["--use_modules"]:
        options["use_modules"] = modules.split(",")
    elif modules := args["--exclude_modules"]:
        options["exclude_modules"] = modules.split(",")

    if args["random"]:
        if name_includes := args["--name"]:
            options["theme_name_includes"] = name_includes
        return await tm.set_random_theme(**options)

    elif args["refresh"]:
        return await tm.apply_theme(**options)

    elif args["theme"]:
        if args["set"]:
            return await tm.apply_theme(theme_name=args["THEME"], **options)

        elif args["rename"]:
            return await tm.rename_theme(
                theme_name=args["THEME"],
                new_name=args["NEW_NAME"],
                album=args["--album"],
            )

        elif args["delete"]:
            return tm.delete_theme(args["THEME"], args["--album"])

    elif args["module"]:
        module_name = args["MODULE"]
        if args["clone"]:
            return await tm.mm.clone(module_name)

        elif args["delete"]:
            return await tm.mm.delete(module_name)

        elif args["run"]:
            return await tm.mm.run_module_command(
                tm, module_name=module_name, command=args["COMMAND"]
            )

    elif args["toggle"]:
        return await tm.toggle_mode()

    elif args["mode"]:
        mode = args["MODE"]

        return await tm.set_mode(mode)

    elif args["gen"]:
        a = {"album": options["album"]}
        if args["--name"]:
            a["name"] = args["--name"]

        if b := args["--backend"]:
            a["backend"] = b

        if apply := args["--apply"]:
            a["apply"] = apply

        for img in args["IMAGE"]:
            r = await tm.generate_theme(image=img, **a)
            res += r

        return res

    elif args["list"]:
        if args["modules"]:
            return await tm.mm.list()
        elif args["themes"]:
            return await tm.list_themes()
        elif args["palettes"]:
            return await tm.list_palettes()
        elif args["styles"]:
            return await tm.list_styles()

    elif args["info"]:
        # TODO use Rich Table?
        msg = f"""🍙 PimpMyRice 0.0.1

name: {tm.config.theme}
album: {tm.config.album}
mode: {tm.config.mode}
"""

        # if tm.config.theme:
        #     msg += "\r\n" + palette_display_string(
        #         tm.albums[tm.config.album][tm.config.theme]
        #         .modes[tm.config.mode]
        #         .palette.term
        #     )

        return res.info(msg)

    elif args["regen"]:
        return await tm.rewrite_themes(
            regen_colors=True, album=options["album"], name_includes=args["--name"]
        )

    elif args["rewrite"]:
        return await tm.rewrite_themes(
            album=options["album"], name_includes=args["--name"]
        )

    return res.error("not implemented")
