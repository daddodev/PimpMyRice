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
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Union
from uuid import uuid4

from pydantic import BaseModel, Field

from pimpmyrice import files, utils
from pimpmyrice.config import CLIENT_OS, MODULES_DIR, TEMP_DIR, Os
from pimpmyrice.logger import get_logger
from pimpmyrice.utils import AttrDict, Result, Timer

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = get_logger(__name__)


class ShellAction(BaseModel):
    module_name: str = Field(exclude=True)
    command: str

    async def run(self, theme_dict: AttrDict) -> Result:
        res = Result()

        try:
            cmd = utils.parse_string_vars(
                string=self.command,
                module_name=self.module_name,
                theme_dict=theme_dict,
            )

            out, err = await run_shell_command(cmd)

            if out:
                res.debug(out, self.module_name)
            if err:
                res.warning(
                    f'command "{cmd}" returned an error:\n{err}', self.module_name
                )

            res.debug(
                f'executed "{cmd}"',
                self.module_name,
            )
            res.ok = True
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res


class FileAction(BaseModel):
    module_name: str = Field(exclude=True)
    template: str
    target: str

    async def run(self, theme_dict: AttrDict) -> Result:
        res = Result()

        try:
            template = Path(
                utils.parse_string_vars(
                    string=self.template,
                    module_name=self.module_name,
                    theme_dict=theme_dict,
                )
            )
            target = Path(
                utils.parse_string_vars(
                    string=self.target,
                    module_name=self.module_name,
                    theme_dict=theme_dict,
                )
            )

            if not target.parent.exists():
                target.parent.mkdir(parents=True)

            with open(template, "r") as f:
                data = f.read()
            processed_data = utils.process_template(data, theme_dict)

            with open(target, "w") as f:
                f.write(processed_data)

            res.debug(
                f'generated "{target.name}"',
                self.module_name,
            )
            res.ok = True
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res


class PythonAction(BaseModel):
    module_name: str = Field(exclude=True)
    py_file_path: Path = Field(exclude=True)
    function_name: str

    async def run(self, *args: Any, **kwargs: Any) -> Result[Any]:
        res = Result()

        try:
            spec = importlib.util.spec_from_file_location(
                self.module_name, self.py_file_path
            )
            if not spec or not spec.loader:
                raise ImportError(f'could not load "{self.py_file_path}"')
            py_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(py_module)

            fn = getattr(py_module, self.function_name)

            res.debug(
                f"{self.py_file_path.name}:{self.function_name} loaded",
                self.module_name,
            )

            if asyncio.iscoroutinefunction(fn):
                res.value = await fn(*args, **kwargs)
            else:
                res.value = fn(*args, **kwargs)

            res.debug(
                f"{self.py_file_path.name}:{self.function_name} returned:\n{res.value}",
                self.module_name,
            )
            res.ok = True
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res


class IfRunningAction(BaseModel):
    module_name: str = Field(exclude=True)
    program_name: str
    should_be_running: bool

    async def run(self, theme_map: AttrDict) -> Result:
        res = Result()

        try:
            running = utils.is_process_running(self.program_name)
            if self.should_be_running:
                res.ok = running
            else:
                res.ok = not running
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res

    def __str__(self) -> str:
        return f'if "{self.program_name}" {"running" if self.should_be_running
                                           else "not running"}'


class LinkAction(BaseModel):
    module_name: str = Field(exclude=True)
    origin: Path
    destination: Path

    async def run(self) -> Result:
        res = Result()

        try:
            if self.destination.exists():
                return res.error(
                    f'cannot link "{self.destination}" to "{self.origin}", destination already exists'
                )

            self.destination.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(
                self.origin,
                self.destination,
                target_is_directory=True,
            )
            # action.destination.hardlink_to(action.origin)
            res.debug(f'init: "{self.destination}" linked to "{self.origin}"')
            res.ok = True
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res


ModuleInit = Union[LinkAction]

ModulePreRun = Union[PythonAction]

ModuleRun = Union[ShellAction, FileAction, PythonAction, IfRunningAction]

ModuleCommand = Union[PythonAction]


class Module(BaseModel):
    name: str = Field(exclude=True)
    enabled: bool = True
    os: list[Os] = [o for o in Os]
    init_actions: list[ModuleInit] = []
    pre_run_actions: list[ModulePreRun] = []
    run_actions: list[ModuleRun] = []
    commands: dict[str, ModuleCommand] = {}

    async def init(self) -> Result:
        res = Result()

        for action in self.init_actions:
            try:
                action_res = await action.run()
                res += action_res
                if not action_res.ok:
                    break

            except Exception as e:
                res.exception(e, f"{action} encountered an error:", self.name)
                break

        return res

    async def pre_run(self, theme_dict: AttrDict) -> Result[AttrDict]:
        res: Result[AttrDict] = Result()

        try:
            for action in self.pre_run_actions:
                action_res = await action.run(theme_dict)
                res += action_res
                if action_res.value:
                    theme_dict = action_res.value

        except Exception as e:
            res.exception(e, self.name)
        finally:
            res.value = theme_dict
            return res

    async def run(self, theme_dict: AttrDict) -> Result:
        res = Result(name=self.name)
        timer = Timer()

        theme_dict = (
            theme_dict + theme_dict["modules_styles"][self.name]
            if self.name in theme_dict["modules_styles"]
            else deepcopy(theme_dict)
        )

        for action in self.run_actions:
            try:
                action_res = await action.run(theme_dict)
                res += action_res
                if not action_res.ok:
                    break

            except Exception as e:
                res.exception(e, f"{action} encountered an error:", self.name)
                break

        res.time = timer.elapsed()
        res.info(f"done in {res.time:.2f} sec", self.name)
        res.ok = True
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


async def delete_module(module: Module) -> None:
    path = MODULES_DIR / module.name
    shutil.rmtree(path)
