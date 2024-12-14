import os
from importlib.metadata import version
from pathlib import Path
from typing import Any

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
from pimpmyrice.theme import ThemeManager
from pimpmyrice.theme_utils import ThemeConfig
from pimpmyrice.utils import Result

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
            theme = ThemeConfig(**config).theme

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


async def process_args(tm: ThemeManager, args: dict[str, Any]) -> Result:
    res = Result()

    options = {
        "mode_name": args["--mode"],
        "palette_name": args["--palette"],
        "print_theme_dict": args["--print-theme-dict"],
    }

    if t := args["--tags"]:
        tags = set(t.split(","))
    else:
        tags = set()

    if t := args["--exclude-tags"]:
        exclude_tags = set(t.split(","))
    else:
        exclude_tags = set()

    if styles_names := args["--style"]:
        options["styles_names"] = styles_names.split(",")

    if modules := args["--modules"]:
        options["include_modules"] = modules.split(",")
    elif modules := args["--exclude-modules"]:
        options["exclude_modules"] = modules.split(",")

    if args["random"]:
        if name_includes := args["--name"]:
            options["name_includes"] = name_includes
        if tags:
            options["include_tags"] = tags
        if t := args["--exclude-tags"]:
            options["exclude_tags"] = set(t.split(","))
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
            )

        elif args["delete"]:
            return tm.delete_theme(args["THEME"])
        elif args["export"]:
            return await tm.export_theme(
                args["THEME"], out_dir=Path(args["OUT_DIR"]).absolute(), **options
            )

    elif args["module"]:
        if args["clone"]:
            return await tm.mm.clone_module(args["MODULE_URL"])

        elif args["delete"]:
            return await tm.mm.delete_module(args["MODULE"])

        elif args["run"]:
            return await tm.mm.run_module_command(
                tm,
                module_name=args["MODULE"],
                command=args["COMMAND"],
                cmd_args=args["COMMAND_ARGS"],
            )

        elif args["reinit"]:
            return await tm.mm.init_module(module_name=args["MODULE"])

    elif args["tags"]:
        if args["add"]:
            return await tm.add_tags(args["THEMES"], tags)
        elif args["remove"]:
            return await tm.remove_tags(args["THEMES"], tags)

    elif args["toggle"]:
        return await tm.toggle_mode()

    elif args["mode"]:
        mode = args["MODE"]

        return await tm.set_mode(mode)

    elif args["gen"]:
        a = {}

        if args["--name"]:
            a["name"] = args["--name"]

        if tags:
            a["tags"] = tags

        if apply := args["--apply"]:
            a["apply"] = apply

        for img in args["IMAGE"]:
            r = await tm.generate_theme(image=img, **a)
            res += r

        return res

    elif args["list"]:
        if args["modules"]:
            return await tm.mm.list_modules()
        elif args["themes"]:
            return await tm.list_themes()
        elif args["tags"]:
            return await tm.list_tags()
        elif args["palettes"]:
            return await tm.list_palettes()
        elif args["styles"]:
            return await tm.list_styles()

    elif args["info"]:
        # TODO use Rich Table?
        msg = f"""🍙 PimpMyRice {version("pimpmyrice")}
name: {tm.config.theme}
mode: {tm.config.mode}
"""

        return res.info(msg)

    elif args["regen"]:
        return await tm.rewrite_themes(regen_colors=True, name_includes=args["--name"])

    elif args["rewrite"]:
        if args["themes"]:
            return await tm.rewrite_themes(name_includes=args["--name"])
        elif args["modules"]:
            return await tm.mm.rewrite_modules(name_includes=args["--name"])

    return res.error("not implemented")
