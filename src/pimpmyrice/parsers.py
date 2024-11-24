from pathlib import Path
from typing import Any, Union

from . import files
from .colors import Palette, ensure_color
from .config import CLIENT_OS, MODULES_DIR, Os
from .logger import get_logger
from .module_utils import (FileAction, IfRunning, InitAction, LinkAction,
                           Module, PythonAction, RunAction, ShellAction)
from .theme_utils import Mode, Style, Theme, Wallpaper, WallpaperMode
from .utils import parse_string_vars

log = get_logger(__name__)


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
    global_palettes: dict[str, Palette],
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


def parse_module(yaml_path: Path) -> Module:
    name = yaml_path.parent.name
    data = files.load_yaml(yaml_path)

    supported_os = []
    if "os" in data:
        os_data = data["os"]
        match os_data:
            case list():
                for os in [o.upper() for o in os_data]:
                    if os in [o.name for o in Os]:
                        supported_os.append(Os[os])
                    else:
                        log.debug(f"unknown os {os}")
            case str():
                supported_os.append(Os[os_data.upper()])
            case _:
                log.error('"os" must be a string or a list')
    if len(supported_os) == 0:
        supported_os = [o for o in Os]
        enabled = True
    elif CLIENT_OS in supported_os:
        enabled = True
    else:
        enabled = False
        log.warning(f'module "{name}" disabled: not compatible with your OS')

    # it's possible to override os compatibility check
    # using "enabled: true" in module.yaml
    if "enabled" in data:
        if not isinstance(data["enabled"], bool):
            raise Exception(f'in "{name}": "enabled" must be "true" or "false"')
        enabled = data["enabled"]

    init: list[InitAction] = []
    if "init" in data:
        for init_action in data["init"]:
            for action_name, action in init_action.items():
                match (action_name):
                    case "link":
                        origin = MODULES_DIR / name / "init_files" / action["what"]
                        destination = (
                            Path(parse_string_vars(action["to"])) / action["what"]
                        )
                        init.append(LinkAction(origin, destination))
                    case _:
                        raise Exception(
                            f'unknow action "{action_name}" in module "{name}'
                        )

    map_modifier = ""
    if "map_modifier" in data:
        modifier = data["map_modifier"]
        if isinstance(modifier, str):
            map_modifier = modifier
        else:
            raise Exception(
                f'in "{name}": "map_modifier" must be a string representing "file.function"'
            )

    run: list[RunAction] = []
    if "run" in data:
        for run_action in data["run"]:
            if not isinstance(run_action, dict):
                raise Exception(
                    f'in "{name}": "run" must be a list of "action: content"'
                )

            for action, content in run_action.items():
                match action:
                    case "if_running":
                        if content[0] == "!":
                            should_be_running = False
                            content = content[1:]
                        else:
                            should_be_running = True
                        run.append(IfRunning(content, should_be_running))

                    case "shell":
                        if not isinstance(content, str):
                            raise Exception('"shell" action value must be a string')
                        run.append(ShellAction(command=content))

                    case "file":
                        match content:
                            case str(content):
                                target = content
                                template_name = f"{Path(target).name}.j2"
                            case dict(content):
                                template_name, target = next(iter(content.items()))
                            case _:
                                raise Exception(
                                    '"file:" must be either a string or a dict'
                                )
                        run.append(
                            FileAction(
                                template=str(
                                    MODULES_DIR / name / "templates" / template_name
                                ),
                                target=target,
                            )
                        )

                    case "python":
                        match content:
                            case str(content):
                                run.append(PythonAction(function=content))
                            case _:
                                raise Exception(
                                    '"python:" must be a string indicating "file.function"'
                                )

                    case _:
                        raise Exception(
                            f'Unknown action {action}. Must be one of: "shell", "file", "python", "if_running".'
                        )

    module = Module(
        name=name,
        map_modifier=map_modifier,
        run=run,
        enabled=enabled,
        os=supported_os,
        init=init,
    )

    return module
