from __future__ import annotations

import asyncio
import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator, validator
from pydantic.json_schema import SkipJsonSchema
from typing_extensions import Annotated

from pimpmyrice import files, utils
from pimpmyrice.config import CLIENT_OS, HOME_DIR, MODULES_DIR, TEMP_DIR, Os
from pimpmyrice.logger import get_logger
from pimpmyrice.utils import AttrDict, Result, Timer, parse_string_vars

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = get_logger(__name__)


def add_action_type_to_schema(
    action_type: str,
    schema: dict[str, Any],
) -> None:
    schema["properties"]["action"] = {
        "title": "Action type",
        "type": "string",
        "const": action_type,
    }
    schema["required"].append("action")


class ShellAction(BaseModel):
    action: Literal["shell"] = Field(default="shell")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    command: str
    detached: bool = False

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "shell")
    )

    async def run(self, theme_dict: AttrDict) -> Result:
        res = Result()

        try:
            cmd = utils.parse_string_vars(
                string=self.command,
                module_name=self.module_name,
                theme_dict=theme_dict,
            )

            if self.detached:
                run_shell_command_detached(cmd)
                return res.debug(
                    f'command "{cmd}" started in background', self.module_name
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
    action: Literal["file"] = Field(default="file")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    target: str
    template: str = ""

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "file")
    )

    @model_validator(mode="before")
    @classmethod
    def set_fields(cls, data: Any) -> Any:
        if "target" in data and "template" not in data:
            template_path = f'{Path(data["target"]).name}.j2'
            data["template"] = template_path
        return data

    async def run(self, theme_dict: AttrDict, out_dir: Path | None = None) -> Result:
        res = Result()

        try:
            template = Path(
                utils.parse_string_vars(
                    string=str(
                        MODULES_DIR / self.module_name / "templates" / self.template
                    ),
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

            if out_dir:
                if target.is_relative_to(HOME_DIR):
                    target = out_dir / target.relative_to(HOME_DIR)
                else:
                    target = out_dir / target

            if not target.parent.exists():
                target.parent.mkdir(parents=True, exist_ok=True)

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
    action: Literal["python"] = Field(default="python")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    py_file_path: str
    function_name: str

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "python")
    )

    async def run(self, *args: Any, **kwargs: Any) -> Result[Any]:
        file_path = Path(self.py_file_path)

        if not file_path.is_absolute():
            file_path = MODULES_DIR / self.module_name / file_path

        res = Result()

        try:
            spec = importlib.util.spec_from_file_location(self.module_name, file_path)
            if not spec or not spec.loader:
                raise ImportError(f'could not load "{file_path}"')
            py_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(py_module)

            fn = getattr(py_module, self.function_name)

            res.debug(
                f"{file_path.name}:{self.function_name} loaded",
                self.module_name,
            )

            if asyncio.iscoroutinefunction(fn):
                res.value = await fn(*args, **kwargs)
            else:
                res.value = fn(*args, **kwargs)

            res.debug(
                f"{file_path.name}:{self.function_name} returned:\n{res.value}",
                self.module_name,
            )
            res.ok = True
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res


class WaitForAction(BaseModel):
    action: Literal["wait_for"] = Field(default="wait_for")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    module: str

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "wait_for")
    )

    async def run(self, theme_dict: AttrDict, modules_state: dict[str, Any]) -> Result:
        res = Result()

        try:
            res.debug(f'waiting for module "{self.module}"...')
            # TODO add timeout
            while not modules_state[self.module]["done"]:
                await asyncio.sleep(0.1)
            res.debug(f'done waiting for module "{self.module}"')
            res.ok = True

        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res

    def __str__(self) -> str:
        return f'wait for "{self.module}" to finish'


class IfRunningAction(BaseModel):
    action: Literal["if_running"] = Field(default="if_running")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    program_name: str
    should_be_running: bool = True

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "if_running")
    )

    async def run(self, theme_dict: AttrDict) -> Result:
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
        return f'if "{self.program_name}" {"running" if self.should_be_running else "not running"}'


class LinkAction(BaseModel):
    action: Literal["link"] = Field(default="link")
    module_name: SkipJsonSchema[str] = Field(exclude=True)
    origin: str
    destination: str

    model_config = ConfigDict(
        json_schema_extra=partial(add_action_type_to_schema, "link")
    )

    async def run(self) -> Result:
        res = Result()

        origin_path = Path(parse_string_vars(self.origin, module_name=self.module_name))
        destination_path = Path(
            parse_string_vars(self.destination, module_name=self.module_name)
        )

        if not origin_path.is_absolute():
            origin_path = MODULES_DIR / self.module_name / "files" / origin_path

        if destination_path.exists():
            return res.error(
                f'cannot link destination "{destination_path}" to origin "{origin_path}", destination already exists'
            )
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(
                origin_path,
                destination_path,
                target_is_directory=origin_path.is_dir(),
            )
            # action.destination.hardlink_to(action.origin)
            res.info(f'init: "{destination_path}" linked to "{origin_path}"')
            res.ok = True
        except Exception as e:
            res.exception(e, self.module_name)
        finally:
            return res


ModuleInit = Union[LinkAction]

ModulePreRun = Union[PythonAction]


ModuleRun = Union[ShellAction, FileAction, PythonAction, IfRunningAction, WaitForAction]

ModuleCommand = Union[PythonAction]


class Module(BaseModel):
    name: SkipJsonSchema[str] = Field(exclude=True)
    enabled: bool = True
    os: list[Os] = [o for o in Os]
    init: list[ModuleInit] = []
    pre_run: list[ModulePreRun] = []
    run: list[ModuleRun] = []
    commands: dict[str, ModuleCommand] = {}

    async def execute_command(
        self, command_name: str, tm: ThemeManager, *args: Any, **kwargs: Any
    ) -> Result:
        res = Result()

        if command_name not in self.commands:
            return res.error(
                f'command "{command_name}" not found in [{", ".join(self.commands.keys())}]'
            )

        try:
            action_res = await self.commands[command_name].run(tm=tm, *args, **kwargs)
        except Exception as e:
            return res.exception(
                e, f'command "{command_name}" encountered an error:', self.name
            )

        res += action_res
        return res

    async def execute_init(self) -> Result:
        res = Result()

        for action in self.init:
            try:
                action_res = await action.run()
                res += action_res
                if not action_res.ok:
                    break

            except Exception as e:
                res.exception(e, f"{action} encountered an error:", self.name)
                break

        return res

    async def execute_pre_run(self, theme_dict: AttrDict) -> Result[AttrDict]:
        res: Result[AttrDict] = Result()

        try:
            for action in self.pre_run:
                action_res = await action.run(theme_dict)
                res += action_res
                if action_res.value:
                    theme_dict = action_res.value

        except Exception as e:
            res.exception(e, self.name)
        finally:
            res.value = theme_dict
            return res

    async def execute_run(
        self,
        theme_dict: AttrDict,
        modules_state: dict[str, Any],
        out_dir: Path | None = None,
    ) -> Result:
        res = Result(name=self.name)
        timer = Timer()

        # get_module_dict
        theme_dict = (
            theme_dict + theme_dict["modules_styles"][self.name]
            if self.name in theme_dict["modules_styles"]
            else deepcopy(theme_dict)
        )

        # output to custom directory (needed for testing)
        if out_dir:
            for action in self.run:
                if isinstance(action, FileAction):
                    try:
                        action_res = await action.run(theme_dict, out_dir=out_dir)
                    except Exception as e:
                        res.exception(e, f"{action} encountered an error:", self.name)
                        break

                    res += action_res
                    if not action_res.ok:
                        res.debug(f"interrupted because res.ok is false:\n{action_res}")
                        break
                else:
                    res.debug(f"dumping {action} not implemented, skipping")

            return res

        for action in self.run:
            try:
                if isinstance(action, WaitForAction):
                    action_res = await action.run(theme_dict, modules_state)
                else:
                    action_res = await action.run(theme_dict)

                res += action_res
                if not action_res.ok:
                    res.debug(f"interrupted because res.ok is false:\n{action_res}")
                    break

            except Exception as e:
                res.exception(e, f"{action} encountered an error:", self.name)
                break

        res.time = timer.elapsed()
        res.info(f"done in {res.time:.2f} sec", self.name)
        res.ok = True
        return res


def run_shell_command_detached(command: str, cwd: Path | None = None) -> None:
    if sys.platform == "win32":
        subprocess.Popen(
            shlex.split(command),
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        return

    subprocess.Popen(
        shlex.split(command),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setpgrp,
    )


async def run_shell_command(command: str, cwd: Path | None = None) -> tuple[str, str]:
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    out, err = await proc.communicate()
    return out.decode(), err.decode()


def load_module_conf(module_name: str) -> dict[str, Any]:
    data = files.load_yaml(MODULES_DIR / module_name / "conf.yaml")
    return data


async def clone_from_folder(source: Path) -> str:
    if not (source / "module.yaml").exists():
        raise Exception(f'module not found at "{source}"')

    name = source.name
    dest_dir = MODULES_DIR / name
    if dest_dir.exists():
        raise Exception(f'module "{name}" already present')

    shutil.copytree(source, MODULES_DIR / name)
    return name


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
