from __future__ import annotations

import asyncio
import shutil
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

from . import module_utils as mutils
from .config import LOCK_FILE, MODULES_DIR, REPOS_BASE_ADDR
from .logger import get_logger
from .module_utils import FileAction, Module
from .parsers import parse_module
from .utils import AttrDict, Lock, Result, Timer, is_locked, parse_string_vars

if TYPE_CHECKING:
    from .theme import ThemeManager

log = get_logger(__name__)


class ModuleManager:
    def __init__(self) -> None:
        self.modules = self.get_modules()

    def get_modules(self) -> dict[str, Module]:
        modules = {}
        timer = Timer()

        for module_dir in MODULES_DIR.iterdir():
            module_yaml = module_dir / "module.yaml"
            if not module_yaml.exists():
                continue
            try:
                module = parse_module(yaml_path=module_yaml)
                modules[module.name] = module
            except Exception as e:
                log.exception(e)
                log.error(f'failed loading module "{module_dir.name}": {e}')

        log.debug(f"{len(modules)} modules loaded in {timer.elapsed():.4f} sec")

        return modules

    def load_module(self, name: str) -> None:
        module_yaml = MODULES_DIR / name / "module.yaml"
        if not module_yaml.exists():
            return
        try:
            module = parse_module(yaml_path=module_yaml)
            self.modules[module.name] = module
            log.info(f'module "{module.name}" loaded')
        except Exception as e:
            log.exception(e)
            log.error(f'failed loading module "{name}": {e}')

    async def run(
        self,
        theme_dict: AttrDict,
        include_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
    ) -> Result:
        res = Result()
        timer = Timer()

        for m in [*(include_modules or []), *(exclude_modules or [])]:
            if m not in self.modules:
                return res.error(f'module "{m}" not found')

        if is_locked(LOCK_FILE)[0]:
            return res.error("another instance is applying a theme!")

        with Lock(LOCK_FILE):
            runners = []
            modifiers = []
            if include_modules:
                modules = {
                    name: self.modules[name]
                    for name in include_modules
                    if name in self.modules
                }
            elif exclude_modules:
                modules = {
                    name: self.modules[name]
                    for name in self.modules
                    if name not in exclude_modules
                }
            else:
                modules = self.modules

            for name, module in modules.items():
                if not module.enabled:
                    continue

                if module.map_modifier:
                    modifiers.append(name)

                if module.run:
                    runners.append(name)

            if len(runners) == 0:
                res.error(
                    "no modules to run!\n"
                    f"See {REPOS_BASE_ADDR} for available modules"
                )
                return res

            for name in modifiers:
                mod_timer = Timer()
                mod_res = await mutils.run_module_modifier(name, deepcopy(theme_dict))
                res += mod_res

                if mod_res.value:
                    theme_dict = mod_res.value
                    res.info(
                        f"modifier applied in {mod_timer.elapsed():.2f} seconds", name
                    )

            tasks = [
                mutils.run_module(
                    self.modules[name], mutils.gen_module_theme_dict(name, theme_dict)
                )
                for name in runners
            ]

            for t in asyncio.as_completed(tasks):
                task_res = await t
                if isinstance(task_res, Exception):
                    module_res = mutils.ModuleResult(name="how did this happen")
                    module_res.exception(task_res)
                else:
                    module_res = task_res

                res += module_res

            res.info(
                f"{len({*modifiers, *runners})} modules applied in {timer.elapsed():.2f} sec"
            )

            return res

    async def run_module_command(
        self, tm: ThemeManager, module_name: str, command: str
    ) -> Result:
        if module_name not in self.modules:
            return Result().error(f'module "{module_name}" not found')

        return await mutils.run_module_py_command(tm, name=module_name, command=command)

    async def clone(self, source: str | Path) -> Result:
        # TODO refactor exceptions
        res = Result()

        try:
            if isinstance(source, Path):
                name = await mutils.clone_from_folder(source)
            elif source.startswith("pimp://"):
                url = f"{REPOS_BASE_ADDR}/{source.removeprefix("pimp://")}"
                name = await mutils.clone_from_git(url)
            else:
                name = await mutils.clone_from_git(source)

            module = parse_module(
                yaml_path=MODULES_DIR / name / "module.yaml",
            )

            for action in module.run:
                if isinstance(action, FileAction):
                    target = Path(parse_string_vars(action.target))
                    if target.exists():
                        copy_path = f"{target}.bkp"
                        try:
                            shutil.copyfile(target, copy_path)
                            res.info(f'"{target.name}" copied to "{target.name}.bkp"')
                        except Exception as e:
                            res.exception(
                                e, f'could not copy "{target}" to "{target}.bkp"'
                            )

            if module.init:
                init_res = await mutils.run_module_init(module)

                res += init_res

            # TODO clean up files
            if res.errors:
                return res.error("failed cloning module")

            self.modules[name] = module
            return res.success(f"module {name} cloned")

        except Exception as e:
            return res.exception(e)

    # async def init_module(self, module_name: str) -> Result:
    #     result = Result()
    #     return result

    async def delete(self, module_name: str) -> Result:
        res = Result()

        if module_name not in self.modules:
            return res.error(f'module "{module_name}" not found')

        module = self.modules[module_name]

        try:
            await mutils.delete(module)
        except Exception as e:
            res.exception(e)
        else:
            self.modules.pop(module_name)
            res.success(f'module "{module_name}" deleted')
        finally:
            return res

    async def list(self) -> Result:
        res = Result()

        for module in self.modules:
            res.info(module)

        return res
