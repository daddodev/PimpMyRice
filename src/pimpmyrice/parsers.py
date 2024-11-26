from pathlib import Path
from typing import Any, Union

from pimpmyrice import files
from pimpmyrice.colors import Palette
from pimpmyrice.config import CLIENT_OS, MODULES_DIR, Os
from pimpmyrice.logger import get_logger
from pimpmyrice.module_utils import (FileAction, IfRunningAction, LinkAction,
                                     Module, ModuleInit, ModuleRun,
                                     PythonAction, ShellAction)
from pimpmyrice.theme_utils import Style, Theme, Wallpaper
from pimpmyrice.utils import parse_string_vars

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
    module_name = yaml_path.parent.name
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
        log.warning(f'module "{module_name}" disabled: not compatible with your OS')

    # it's possible to override os compatibility check
    # using "enabled: true" in module.yaml
    if "enabled" in data:
        if not isinstance(data["enabled"], bool):
            raise Exception(f'in "{module_name}": "enabled" must be "true" or "false"')
        enabled = data["enabled"]

    init: list[ModuleInit] = []
    if "init" in data:
        for init_action in data["init"]:
            for action_name, action in init_action.items():
                match (action_name):
                    case "link":
                        origin = (
                            MODULES_DIR / module_name / "init_files" / action["what"]
                        )
                        destination = (
                            Path(parse_string_vars(action["to"])) / action["what"]
                        )
                        init.append(
                            LinkAction(
                                module_name=module_name,
                                origin=origin,
                                destination=destination,
                            )
                        )
                    case _:
                        raise Exception(
                            f'unknow action "{action_name}" in module "{module_name}'
                        )

    pre_run = []
    if "pre_run" in data:
        for pre_run_action in data["pre_run"]:
            for action, content in pre_run_action.items():
                match action:
                    case "python":
                        match content:
                            case str(content):
                                filename, fn_name = content.split(":")
                                pre_run.append(
                                    PythonAction(
                                        module_name=module_name,
                                        py_file_path=MODULES_DIR
                                        / module_name
                                        / filename,
                                        function_name=fn_name,
                                    )
                                )
                            case _:
                                raise Exception(
                                    '"python:" must be a string indicating "file:function"'
                                )
                    case _:
                        raise Exception(
                            f'Unknown pre_run action {action}. Must be one of: "python".'
                        )

    run: list[ModuleRun] = []
    if "run" in data:
        for run_action in data["run"]:
            if not isinstance(run_action, dict):
                raise Exception(
                    f'in "{module_name}": "run" must be a list of "action: content"'
                )

            for action, content in run_action.items():
                match action:
                    case "if_running":
                        if content[0] == "!":
                            should_be_running = False
                            content = content[1:]
                        else:
                            should_be_running = True
                        run.append(
                            IfRunningAction(
                                module_name=module_name,
                                program_name=content,
                                should_be_running=should_be_running,
                            )
                        )

                    case "shell":
                        if not isinstance(content, str):
                            raise Exception('"shell" action value must be a string')
                        run.append(
                            ShellAction(module_name=module_name, command=content)
                        )

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
                                module_name=module_name,
                                template=str(
                                    MODULES_DIR
                                    / module_name
                                    / "templates"
                                    / template_name
                                ),
                                target=target,
                            )
                        )

                    case "python":
                        match content:
                            case str(content):
                                filename, fn_name = content.split(":")
                                run.append(
                                    PythonAction(
                                        module_name=module_name,
                                        py_file_path=MODULES_DIR
                                        / module_name
                                        / filename,
                                        function_name=fn_name,
                                    )
                                )
                            case _:
                                raise Exception(
                                    '"python:" must be a string indicating "file.function"'
                                )

                    case _:
                        raise Exception(
                            f'Unknown run action "{action}". Must be one of: "shell", "file", "python", "if_running".'
                        )

    module = Module(
        name=module_name,
        pre_run_actions=pre_run,
        run_actions=run,
        enabled=enabled,
        os=supported_os,
        init_actions=init,
    )

    return module
