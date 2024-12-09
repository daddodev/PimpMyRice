from __future__ import annotations

import os
import time
from collections.abc import MutableMapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic

import cv2
import jinja2
import psutil
from typing_extensions import TypeVar

from pimpmyrice.config import CONFIG_DIR, HOME_DIR, MODULES_DIR
from pimpmyrice.logger import LogLevel, get_logger

# import jinja2schema


log = get_logger(__name__)


@dataclass
class ResultRecord:
    msg: str
    level: LogLevel

    def dump(self) -> dict[str, str]:
        d = {"msg": self.msg, "level": self.level.name}
        return d


T = TypeVar("T", default=None)


@dataclass
class Result(Generic[T]):
    value: T | None = None
    name: str | None = None
    errors: int = 0
    records: list[ResultRecord] = field(default_factory=list)
    time: float = 0
    ok: bool = False

    def __log(self, record: ResultRecord, name: str | None = None) -> None:
        if name:
            record.msg = f"{name}: {record.msg}"

        if log.isEnabledFor(record.level.value):
            log._log(level=record.level.value, msg=record.msg, args={})
        self.records.append(record)

    def debug(self, msg: str, name: str | None = None) -> Result[T]:
        self.__log(ResultRecord(msg, LogLevel.DEBUG), name)
        return self

    def info(self, msg: str, name: str | None = None) -> Result[T]:
        self.__log(ResultRecord(msg, LogLevel.INFO), name)
        return self

    def success(self, msg: str, name: str | None = None) -> Result[T]:
        self.__log(ResultRecord(msg, LogLevel.SUCCESS), name)
        return self

    def warning(self, msg: str, name: str | None = None) -> Result[T]:
        self.__log(ResultRecord(msg, LogLevel.WARNING), name)
        return self

    def error(self, msg: str, name: str | None = None) -> Result[T]:
        self.__log(ResultRecord(msg, LogLevel.ERROR), name)
        self.errors += 1
        return self

    def exception(
        self, exception: Exception, message: str | None = None, name: str | None = None
    ) -> Result[T]:
        exc_str = str(exception).strip()

        if message:
            msg = f"{message}:\r\n{' '*(len(name)+2 if name else 0)}{exc_str}"
        else:
            msg = exc_str

        self.__log(ResultRecord(msg, LogLevel.ERROR), name)

        self.errors += 1

        if log.isEnabledFor(LogLevel.DEBUG.value):
            log.exception(exception)

        return self

    def __add__(self, other: Result[Any]) -> Result[T]:
        r: Result[T] = Result(
            name=self.name,
            value=self.value,
            errors=self.errors + other.errors,
            records=[*self.records, *other.records],
        )
        return r

    def dump(self) -> dict[str, Any]:
        d = deepcopy(vars(self))
        d["records"] = [r.dump() for r in self.records]
        return d


class Timer:
    def __init__(self) -> None:
        self.start = time.perf_counter()

    def elapsed(self) -> float:
        return time.perf_counter() - self.start


# def get_template_keywords(template: str) -> list[str]:


class AttrDict(dict[str, Any]):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.__dict__ = self
        super().__init__(*args, **kwargs)

        for k in self:
            if isinstance(self[k], dict):
                self[k] = AttrDict(self[k])

    def __setitem__(self, key: Any, value: Any) -> None:
        if isinstance(value, dict):
            value = AttrDict(value)
        super().__setitem__(key, value)

    def __add__(self, other: DictOrAttrDict) -> AttrDict:
        def merged(base: AttrDict, to_add: AttrDict) -> AttrDict:
            base = deepcopy(base)
            to_add = deepcopy(to_add)
            for k, v in to_add.items():
                if isinstance(v, (dict, AttrDict)):
                    if k in base:
                        base[k] = merged(base[k], to_add[k])
                    else:
                        base[k] = to_add[k]
                else:
                    base[k] = v
            return base

        return merged(self, AttrDict(other))


DictOrAttrDict = TypeVar("DictOrAttrDict", dict[str, Any], AttrDict)


def process_template(template: str, values: dict[str, Any]) -> str:
    # get_template_keywords(template)
    templ = jinja2.Environment(undefined=jinja2.StrictUndefined).from_string(template)
    rendered: str = templ.render(**values)
    return rendered


def parse_string_vars(
    string: str,
    theme_dict: dict[str, Any] | None = None,
    module_name: str | None = None,
) -> str:
    # TODO capitalize

    d = {"home_dir": HOME_DIR, "config_dir": CONFIG_DIR}
    if module_name:
        d["module_dir"] = MODULES_DIR / module_name
        d["templates_dir"] = MODULES_DIR / module_name / "templates"
        d["files_dir"] = MODULES_DIR / module_name / "files"
    if not theme_dict:
        theme_dict = d
    else:
        theme_dict |= d
    res = process_template(string, theme_dict)
    expanded: str = os.path.expanduser(res)
    return expanded


def is_process_running(name: str | None = None, pid: int | None = None) -> bool:
    if (not name and not pid) or (name and pid):
        raise Exception("provide either process pid or name")

    attr = "name" if name else "pid"
    val = name if name else pid

    for proc in psutil.process_iter([attr]):
        if proc.info[attr] == val:
            return True
    return False


def is_locked(lockfile: Path) -> tuple[bool, int]:
    if lockfile.exists():
        with open(lockfile, "r") as f:
            file_pid = int(f.read())

        if is_process_running(pid=file_pid):
            return True, file_pid

        lockfile.unlink()
    return False, 0


class Lock:
    def __init__(self, lockfile: Path) -> None:
        self.lockfile = lockfile

    def __enter__(self) -> None:
        pid = os.getpid()
        with open(self.lockfile, "w") as f:
            f.write(str(pid))

    def __exit__(self, *_: Any) -> None:
        self.lockfile.unlink()


def get_thumbnail(image_path: Path, max_px: int = 1024) -> Path:
    thumb_path = (
        image_path.parent / f".{image_path.stem}_thumb_{max_px}{image_path.suffix}"
    )

    if thumb_path.is_file():
        return thumb_path

    img = cv2.imread(str(image_path))
    fx = max_px / img.shape[1]
    fy = max_px / img.shape[0]
    f = min(fx, fy)
    size = (int(img.shape[1] * f), int(img.shape[0] * f))
    resized = cv2.resize(img, size)

    cv2.imwrite(str(thumb_path), resized)

    log.debug(f'{max_px}x{max_px} thumbnail generated for "{image_path}"')

    return thumb_path
