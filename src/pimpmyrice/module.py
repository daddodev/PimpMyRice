from __future__ import annotations

import asyncio
import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pimpmyrice import module_utils as mutils
from pimpmyrice.config import LOCK_FILE, MODULES_DIR, REPOS_BASE_ADDR
from pimpmyrice.files import load_yaml, save_json, save_yaml
from pimpmyrice.logger import get_logger
from pimpmyrice.module_utils import FileAction, Module
from pimpmyrice.parsers import parse_module
from pimpmyrice.utils import AttrDict, Lock, Result, Timer, is_locked, parse_string_vars

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = get_logger(__name__)


class ModuleManager:
    def __init__(self) -> None:
        self.modules: dict[str, Module] = {}
        self.load_modules()

    def load_modules(self) -> dict[str, Module]:
        modules: dict[str, Module] = {}
        timer = Timer()

        for module_dir in MODULES_DIR.iterdir():
            self.load_module(module_dir)

        log.debug(f"{len(modules)} modules loaded in {timer.elapsed():.4f} sec")

        return modules

    def load_module(self, module_dir: Path) -> Module | None:
        module_res = parse_module(module_dir)

        if module_res.value:
            self.modules[module_res.value.name] = module_res.value
            log.debug(f'module "{module_res.value.name}" loaded')
            return module_res.value
        return None

    async def run_modules(
        self,
        theme_dict: AttrDict,
        include_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
        out_dir: Path | None = None,
    ) -> Result[set[str]]:

        res: Result[set[str]] = Result()

        executed_modules: set[str] = set()

        timer = Timer()

        for m in [*(include_modules or []), *(exclude_modules or [])]:
            if m not in self.modules:
                return res.error(f'module "{m}" not found')

        if is_locked(LOCK_FILE)[0]:
            return res.error("another instance is applying a theme!")

        with Lock(LOCK_FILE):
            runners = []
            pre_runners = []
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

                if module.pre_run:
                    pre_runners.append(name)

                if module.run:
                    runners.append(name)

            if len(runners) == 0:
                res.error(
                    "no modules to run!\n"
                    f"See {REPOS_BASE_ADDR} for available modules"
                )
                return res

            for name in pre_runners:
                mod_timer = Timer()

                mod_res = await self.modules[name].execute_pre_run(deepcopy(theme_dict))
                res += mod_res

                if mod_res.value:
                    theme_dict = mod_res.value
                    res.info(
                        f"modifier applied in {mod_timer.elapsed():.2f} seconds", name
                    )
                    executed_modules.add(name)

            modules_state = {m: {"done": False} for m in self.modules}

            tasks = [
                self.modules[name].execute_run(
                    theme_dict, modules_state=modules_state, out_dir=out_dir
                )
                for name in runners
            ]

            for t in asyncio.as_completed(tasks):
                task_res = await t
                if isinstance(task_res, Result):
                    if task_res.name:
                        executed_modules.add(task_res.name)
                        modules_state[task_res.name]["done"] = True
                    else:
                        task_res.error(f"Result has no name")

                    module_res = task_res
                else:
                    module_res = Result(name="how did this happen?")
                    module_res.exception(task_res)

                res += module_res

            res.info(
                f"{len({*pre_runners, *runners})} modules applied in {timer.elapsed():.2f} sec"
            )

            res.value = executed_modules

            res.ok = True
            return res

    async def run_module_command(
        self,
        tm: ThemeManager,
        module_name: str,
        command: str,
        *args: Any,
        **kwargs: Any,
    ) -> Result:
        res = Result()
        if module_name not in self.modules:
            return res.error(f'module "{module_name}" not found')

        module = self.modules[module_name]
        res += await module.execute_command(command, tm, *args, **kwargs)

        res.ok = True
        return res

    async def rewrite_modules(
        self,
        name_includes: str | None = None,
    ) -> Result:
        res = Result()

        for module in self.modules.values():
            if name_includes and name_includes not in module.name:
                continue

            try:
                dump = module.model_dump(mode="json")

                save_yaml(MODULES_DIR / module.name / "module.yaml", dump)
                # save_json(MODULES_DIR / module.name / "module.json", dump)
                res.success(f'module "{module.name}" rewritten')
            except Exception as e:
                res.exception(e)
        return res

    async def init_module(self, module_name: str) -> Result:
        res = Result()

        if not module_name in self.modules:
            return res.error(f'module "{module_name}" not found')

        module = self.modules[module_name]
        init_res = await module.execute_init()
        res += init_res

        res.ok = True
        return res

    async def clone_module(self, source: str | list[str]) -> Result:
        res = Result()

        sources = source if isinstance(source, list) else [source]

        for source in sources:
            try:
                source = str(source)

                if source.startswith(("git@", "http://", "https://")):
                    name = await mutils.clone_from_git(source)

                elif source.startswith("pimp://"):
                    url = f'{REPOS_BASE_ADDR}/{source.removeprefix("pimp://")}'
                    name = await mutils.clone_from_git(url)

                else:
                    name = await mutils.clone_from_folder(Path(source))

                parse_res = parse_module(MODULES_DIR / name)
                res += parse_res
                if parse_res.value:
                    module = parse_res.value
                else:
                    continue

                for action in module.run:
                    if isinstance(action, FileAction):
                        target = Path(parse_string_vars(action.target))
                        if target.exists():
                            copy_path = f"{target}.bkp"
                            try:
                                shutil.copyfile(target, copy_path)
                                res.info(
                                    f'"{target.name}" copied to "{target.name}.bkp"'
                                )
                            except Exception as e:
                                res.exception(
                                    e, f'could not copy "{target}" to "{target}.bkp"'
                                )

                        link_path = Path(str(target) + ".j2")
                        if link_path.exists() or link_path.is_symlink():
                            res.info(
                                f'skipping linking "{link_path}" to "{action.template}", destination already exists'
                            )
                            continue
                        else:
                            link_path.parent.mkdir(exist_ok=True, parents=True)

                        os.symlink(action.template, link_path)
                        res.info(f'linked "{link_path}" to "{action.template}"')

                if module.init:
                    init_res = await module.execute_init()
                    res += init_res

                # TODO clean up files
                if res.errors:
                    res.error("failed cloning module")
                    continue

                self.modules[name] = module
                res.success(f'module "{name}" cloned')

            except Exception as e:
                res.exception(e)
                continue

        res.ok = True
        return res

    async def delete_module(self, module_name: str) -> Result:
        res = Result()

        if module_name not in self.modules:
            return res.error(f'module "{module_name}" not found')

        module = self.modules[module_name]

        try:
            await mutils.delete_module(module)
        except Exception as e:
            res.exception(e)
        else:
            self.modules.pop(module_name)
            res.ok = True
            res.success(f'module "{module_name}" deleted')
        finally:
            return res

    async def list_modules(self) -> Result:
        res = Result()

        for module in self.modules:
            res.info(module)

        res.ok = True
        return res
