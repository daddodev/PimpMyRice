from pathlib import Path
from typing import Any, Union

from pimpmyrice import files
from pimpmyrice.colors import GlobalPalette, Palette
from pimpmyrice.config import CLIENT_OS, MODULES_DIR, Os
from pimpmyrice.logger import get_logger
from pimpmyrice.module_utils import (
    FileAction,
    IfRunningAction,
    LinkAction,
    Module,
    ModuleInit,
    ModuleRun,
    PythonAction,
    ShellAction,
)
from pimpmyrice.theme_utils import Style, Theme, Wallpaper
from pimpmyrice.utils import Result, parse_string_vars

log = get_logger(__name__)


# TODO use pydantic


def parse_wallpaper(
    wallpaper: Union[dict[str, Any], str], theme_path: Path
) -> Wallpaper:
    match wallpaper:
        case str(wallpaper):
            return Wallpaper(path=theme_path / wallpaper)
        case dict(wallpaper):
            return Wallpaper(**{**wallpaper, "path": theme_path / wallpaper["path"]})
        case _:
            raise Exception('"wallpaper" must be a string or a dict')


def parse_theme(
    path: Path,
    global_styles: dict[str, Style],
    global_palettes: dict[str, GlobalPalette],
) -> Theme:
    name = path.name

    data = files.load_json(path / "theme.json")

    data["wallpaper"] = parse_wallpaper(data["wallpaper"], path)

    modes = data.get("modes")
    if isinstance(modes, dict):
        for mode_name, mode in modes.items():
            mode["name"] = mode_name
            if isinstance(mode, dict):
                if "wallpaper" not in mode:
                    mode["wallpaper"] = data.get("wallpaper")
                else:
                    mode["wallpaper"] = parse_wallpaper(mode["wallpaper"], path)

    theme = Theme(**data, name=name, path=path)
    # TODO global style
    return theme


def parse_module(module_path: Path) -> Result[Module]:
    res: Result[Module] = Result()

    module_name = module_path.name
    module_yaml = module_path / "module.yaml"
    module_json = module_path / "module.json"

    try:
        if module_yaml.exists():
            data = files.load_yaml(module_yaml)
        elif module_json.exists():
            data = files.load_json(module_json)
        else:
            return res

        for param in ["init", "pre_run", "run"]:
            for action in data.get(param, []):
                if isinstance(action, dict):
                    action["module_name"] = module_name

        for cmd_name, cmd in data.get("commands", {}).items():
            cmd["module_name"] = module_name

        module = Module(**data, name=module_name)

        res.value = module

    except Exception as e:
        res.exception(e)
        res.error(f'failed loading module in "{module_path}": {e}')
    finally:
        return res
