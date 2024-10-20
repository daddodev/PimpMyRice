from __future__ import annotations

import asyncio
import json
import mimetypes
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import requests
import yaml
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import (ALBUMS_DIR, BASE_STYLE_FILE, CONFIG_FILE, LOG_FILE,
                     MODULES_DIR, PALETTES_DIR, PIMP_CONFIG_DIR, STYLES_DIR,
                     TEMP_DIR)
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
        self.loop = asyncio.new_event_loop()

    def on_any_event(self, event: FileSystemEvent) -> None:
        path = Path(event.src_path)

        event_id = f"{event.src_path}:{event.event_type}"
        if event_id in self.debounce_table:
            time_passed = time.time() - self.debounce_table[event_id]
            if time_passed < 2:
                return

        self.debounce_table[event_id] = time.time()

        # print(event)

        if path == BASE_STYLE_FILE and (
            event.event_type == "modified" or event.event_type == "created"
        ):
            log.info("reloading base_style.json")
            self.tm.base_style = self.tm.get_base_style()
            self.run_async(self.tm.apply_theme())

        elif path.parent == ALBUMS_DIR and event.is_directory:
            album_name = path.name
            if event.event_type == "created":
                self.tm.albums[album_name] = {}
                log.info(f'album "{album_name}" created')
            elif event.event_type == "deleted":
                self.tm.albums.pop(album_name)
                log.info(f'album "{album_name}" deleted')
            elif event.dest_path:  # type: ignore
                new_album_name = Path(event.dest_path).name  # type: ignore
                self.tm.albums[new_album_name] = self.tm.get_themes(
                    Path(event.dest_path)  # type:ignore
                )
                self.tm.albums.pop(album_name)
                log.info(f'album "{album_name}" renamed to "{new_album_name}"')

                if self.tm.config.album == album_name:
                    self.tm.config.album = new_album_name

        elif path.name == "theme.json" and path.parents[2] == ALBUMS_DIR:
            theme_name = path.parent.name
            album_name = path.parents[1].name
            if event.event_type == "modified":
                self.tm.albums[album_name][theme_name] = self.tm.get_theme(path.parent)
                log.info(
                    f'theme "{theme_name}" \
                            in album {album_name} loaded'
                )

                if (
                    self.tm.config.theme == theme_name
                    and self.tm.config.album == album_name
                ):
                    self.run_async(self.tm.apply_theme())

    def run_async(self, f: Awaitable[Any]) -> None:
        self.loop.run_until_complete(f)

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
        ALBUMS_DIR,
        ALBUMS_DIR / "default",
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
