from __future__ import annotations

import asyncio
import importlib.util
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Union
# from contextlib import redirect_stdout
from uuid import uuid4

from . import files, utils
from .config import CLIENT_OS, MODULES_DIR, TEMP_DIR, Os
from .logger import get_logger
from .utils import AttrDict, Result, Timer

if TYPE_CHECKING:
    from .theme import ThemeManager

log = get_logger(__name__)


# class ModuleException(Exception):
#     def __init__(self, module_name: str, message: str):
#         self.module_name = module_name
#         self.message = f'error in "{self.module_name}": {message}'
#
#         super().__init__(self.message)


@dataclass
class ShellAction:
    command: str


@dataclass
class FileAction:
    template: str
    target: str


@dataclass
class PythonAction:
    function: str


class IfAction(ABC):
    @abstractmethod
    def check(self) -> bool: ...


class IfRunning(IfAction):
    def __init__(self, program_name: str, should_be_running: bool = True):
        self.program_name = program_name
        self.should_be_running = should_be_running

    def check(self) -> bool:
        running = utils.is_process_running(self.program_name)
        if self.should_be_running:
            return running
        else:
            return not running

    def __str__(self) -> str:
        return f'if "{self.program_name}" {"running" if self.should_be_running
                                           else "not running"}'


RunAction = Union[ShellAction, FileAction, PythonAction, IfAction]


@dataclass
class LinkAction:
    origin: Path
    destination: Path


InitAction = Union[LinkAction]


@dataclass
class Module:
    name: str
    map_modifier: str  # module_name.function_name
    run: list[RunAction]
    enabled: bool
    init: list[InitAction]
    os: list[Os]


@dataclass
class ModuleResult(Result):
    name: str = ""


async def run_module(module: Module, theme_dict: AttrDict) -> ModuleResult:
    res = ModuleResult(name=module.name)
    timer = Timer()

    for action in module.run:
        try:
            match action:
                case IfAction():
                    check_ok = action.check()
                    if not check_ok:
                        return res.debug(
                            f'interrupted, condition "{action}" returned false',
                            module.name,
                        )

                case ShellAction():
                    cmd = utils.parse_string_vars(
                        string=action.command,
                        module_name=module.name,
                        theme_dict=theme_dict,
                    )
                    out, err = await run_shell_command(cmd)
                    if out:
                        res.debug(out, module.name)
                    if err:
                        res.warning(
                            f'command "{cmd}" returned an error:\n{err}', module.name
                        )

                case FileAction():
                    template = Path(
                        utils.parse_string_vars(
                            string=action.template,
                            module_name=module.name,
                            theme_dict=theme_dict,
                        )
                    )
                    target = Path(
                        utils.parse_string_vars(
                            string=action.target,
                            module_name=module.name,
                            theme_dict=theme_dict,
                        )
                    )
                    if not target.parent.exists():
                        target.parent.mkdir(parents=True)

                    gen_file(
                        template=template,
                        target=target,
                        theme_dict=theme_dict,
                    )

                case PythonAction():
                    await run_py_module(
                        name=module.name,
                        fn_name=action.function,
                        theme_dict=theme_dict,
                    )

                case _:
                    raise Exception(f'unknown action "{action}"')

        except Exception as e:
            res.exception(e, f"{action} encountered an error:", module.name)

    res.time = timer.elapsed()
    res.info(f"done in {res.time:.2f} sec", module.name)
    return res


async def run_module_init(module: Module) -> ModuleResult:
    result = ModuleResult(name=module.name)

    try:
        for action in module.init:
            match action:
                case LinkAction():
                    if action.destination.exists():
                        return result.error(
                            f'cannot link "{action.destination}" to\
                                    "{action.origin}", destination already exists'
                        )

                    action.destination.parent.mkdir(parents=True, exist_ok=True)
                    os.symlink(
                        action.origin, action.destination, target_is_directory=True
                    )
                    # action.destination.hardlink_to(action.origin)
                    result.debug(
                        f'init: "{action.destination}" linked to "{action.origin}"'
                    )
        return result
    except Exception as e:
        return result.exception(e, module.name)


def gen_file(
    template: Path,
    target: Path,
    theme_dict: AttrDict,
) -> None:
    with open(template, "r") as f:
        data = f.read()
    parsed_data = utils.process_template(data, theme_dict)

    with open(target, "w") as f:
        f.write(parsed_data)


def load_py_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise ImportError
    module = importlib.util.module_from_spec(spec)
    sys.modules["pimpmyrice_" + name] = module
    spec.loader.exec_module(module)
    return module


async def run_py_module(
    name: str,
    fn_name: str,
    theme_dict: AttrDict,
) -> None:
    py_module = load_py_module(name, MODULES_DIR / name / f"{name}.py")
    fn = getattr(py_module, fn_name)

    if asyncio.iscoroutinefunction(fn):
        await fn(theme_dict)
    else:
        await asyncio.to_thread(fn, theme_dict)


def gen_module_theme_dict(name: str, theme_dict: AttrDict) -> AttrDict:
    m: AttrDict = (
        theme_dict + theme_dict["modules_styles"][name]
        if name in theme_dict["modules_styles"]
        else deepcopy(theme_dict)
    )
    return m


async def run_module_py_command(tm: ThemeManager, name: str, command: str) -> Result:
    res = Result()

    py_module = load_py_module(name, MODULES_DIR / name / f"{name}.py")
    fn = getattr(py_module, command)

    if asyncio.iscoroutinefunction(fn):
        await fn(tm)
    else:
        await asyncio.to_thread(fn, tm)

    return res


async def run_module_modifier(name: str, theme_dict: AttrDict) -> Result[AttrDict]:
    res: Result[AttrDict] = Result()

    try:
        py_module = load_py_module(name, MODULES_DIR / name / "modifier.py")
        modified: AttrDict = await py_module.modify(theme_dict)

        res.value = modified
    except Exception as e:
        res.exception(e, "module modifier failed", name)
    finally:
        return res


async def run_shell_command(command: str, cwd: Path | None = None) -> tuple[str, str]:
    if command.endswith("&"):
        detached = True
        command = command[:-1].strip()
    else:
        detached = False

    if detached:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            start_new_session=True,
            shell=True,
        )
        return f'command "{command}" started in background', ""
    else:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        out, err = await proc.communicate()
        # print(f"{out.decode()=}\n{err.decode()=}")
        return out.decode(), err.decode()


def load_module_conf(module_name: str) -> dict[str, Any]:
    data = files.load_yaml(MODULES_DIR / module_name / "conf.yaml")
    return data


async def clone_from_folder(source: Path) -> str:
    if not (source / "module.yaml").exists():
        raise Exception(f'module not found at "{source}"')
    shutil.copytree(source, MODULES_DIR / source.name)
    return source.name


async def clone_from_git(url: str) -> str:
    name = url.split("/")[-1].removesuffix(".git")
    dest_dir = MODULES_DIR / name
    if dest_dir.exists():
        raise Exception(f'module "{name}" already present')
    random = str(uuid4())
    if CLIENT_OS == Os.WINDOWS:
        cmd = f'set GIT_TERMINAL_PROMPT=0 && git clone "{url}" {random}'
    else:
        cmd = f'GIT_TERMINAL_PROMPT=0 git clone "{url}" {random}'
    res, err = await run_shell_command(cmd, cwd=TEMP_DIR)

    if res:
        log.debug(res)

    if err:
        for line in err.split("\n"):
            if line and "Cloning into" not in line:
                if "terminal prompts disabled" in line:
                    raise Exception("repository not found")
                raise Exception(err)

    shutil.move(TEMP_DIR / random, dest_dir)

    return name


async def delete(module: Module) -> None:
    path = MODULES_DIR / module.name
    shutil.rmtree(path)
