from __future__ import annotations

import asyncio
import json
import mimetypes
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests
import yaml
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import (BASE_STYLE_FILE, CONFIG_FILE, LOG_FILE, MODULES_DIR,
                     PALETTES_DIR, PIMP_CONFIG_DIR, STYLES_DIR, TEMP_DIR,
                     THEMES_DIR)
from .keywords import base_style
from .logger import get_logger
from .utils import Result

if TYPE_CHECKING:
    from .theme import ThemeManager

log = get_logger(__name__)


class ConfigDirWatchdog(FileSystemEventHandler):
    def __init__(self, tm: ThemeManager) -> None:
        self.observer = Observer()
        self.tm = tm
        self.debounce_table: dict[str, float] = {}

    def on_any_event(self, event: FileSystemEvent) -> None:
        loop = asyncio.new_event_loop()
        path = Path(event.src_path)

        if path == BASE_STYLE_FILE:
            log.info(f"{event.event_type} keywords")

            if event.event_type == "modified":
                event_id = f"{event.src_path}:{event.event_type}"
                if event_id in self.debounce_table:
                    time_passed = time.time() - self.debounce_table[event_id]
                    if time_passed < 2:
                        return

                self.debounce_table[event_id] = time.time()

                self.tm.base_style = self.tm.get_base_style()

                loop.run_until_complete(self.tm.apply_theme())

        # elif path.name == "theme.json" and path.parents[2] == THEMES_DIR:
        #     log.info(
        #         f'{event.event_type} theme "{path.parent.name}" \
        #                 in album {path.parents[1].name}'
        #     )

    def __enter__(self) -> None:
        self.observer.schedule(self, PIMP_CONFIG_DIR, recursive=True)
        self.observer.start()

    def __exit__(self, *_: Any) -> None:
        self.observer.stop()
        self.observer.join()


def load_yaml(file: Path) -> dict[str, Any]:
    with open(file) as f:
        return dict(yaml.load(f, Loader=yaml.Loader))


def load_json(file: Path) -> dict[str, Any]:
    with open(file) as f:
        return json.load(f)  # type: ignore


def save_json(file: Path, data: dict[str, Any]) -> None:
    jsn = json.dumps(data, indent=4)
    with open(file, "w") as f:
        f.write(jsn)


def import_image(image_path: Path, theme_dir: Path) -> Path:
    if (
        not image_path.exists() or not image_path.is_file()
    ):  # to do: process files/folders
        raise FileNotFoundError(f'file not found at "{image_path}"')

    dest = theme_dir / image_path.name
    if (dest).exists():
        raise Exception(f'file already exists at "{dest}"')

    shutil.copy(image_path, theme_dir)
    log.debug(f'image "{image_path.name}" imported')
    return dest


def check_config_dirs() -> None:
    for dir in [
        PIMP_CONFIG_DIR,
        THEMES_DIR,
        THEMES_DIR / "default",
        STYLES_DIR,
        PALETTES_DIR,
        MODULES_DIR,
        TEMP_DIR,
    ]:
        dir.mkdir(exist_ok=True)

    if not BASE_STYLE_FILE.exists():
        save_json(BASE_STYLE_FILE, base_style)
    if not CONFIG_FILE.exists():
        config = {"theme": None, "mode": "dark"}
        save_json(CONFIG_FILE, config)
    if not LOG_FILE.exists():
        LOG_FILE.touch()

    # if not VENV_DIR.exists():
    #     create_venv()


def download_file(url: str, destination: Path = TEMP_DIR) -> Result[Path]:
    # TODO better filename

    res = Result[Path]()

    try:
        response = requests.get(url, stream=True)

        if response.status_code != 200:
            return res.error(
                f"Failed to download image. Status code: {response.status_code}"
            )

        content_type = response.headers.get("content-type")
        file_extension = (
            mimetypes.guess_extension(content_type) if content_type else None
        )

        if not file_extension:
            file_extension = ".jpg"

        filename = url.split("/")[-1].split("?")[0]

        if not filename.endswith(file_extension):
            filename = filename + file_extension

        save_path = destination / filename

        tries = 1
        while save_path.exists():
            save_path = (
                save_path.parent / f"{save_path.stem}_{tries+1}{save_path.suffix}"
            )

        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        res.value = save_path
        return res

    except Exception as e:
        return res.exception(e)
