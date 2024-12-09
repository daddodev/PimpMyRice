import json
import mimetypes
import shutil
from pathlib import Path
from typing import Any

import requests
import yaml

from pimpmyrice.config import (
    BASE_STYLE_FILE,
    CONFIG_FILE,
    JSON_SCHEMA_DIR,
    LOG_FILE,
    MODULES_DIR,
    PALETTES_DIR,
    PIMP_CONFIG_DIR,
    STYLES_DIR,
    TEMP_DIR,
    THEMES_DIR,
)
from pimpmyrice.keywords import default_base_style
from pimpmyrice.logger import get_logger
from pimpmyrice.utils import Result

log = get_logger(__name__)


def load_yaml(file: Path) -> dict[str, Any]:
    with open(file) as f:
        return dict(yaml.load(f, Loader=yaml.Loader))


def save_yaml(file: Path, data: dict[str, Any]) -> None:
    dump = yaml.dump(data, indent=4, default_flow_style=False)

    if file.name in ("module.yaml", "theme.yaml"):
        schema_str = f'# yaml-language-server: $schema=../../.json_schemas/{file.name.split(".")[0]}.json\n\n'
        dump = schema_str + dump

    with open(file, "w") as f:
        f.write(dump)


def load_json(file: Path) -> dict[str, Any]:
    with open(file) as f:

        data = json.load(f)
        data.pop("$schema", None)

        return data  # type: ignore


def save_json(file: Path, data: dict[str, Any]) -> None:
    if file.name in ("module.json", "theme.json") and file.parent != JSON_SCHEMA_DIR:
        data["$schema"] = f'../../.json_schemas/{file.name.split(".")[0]}.json'

    dump = json.dumps(data, indent=4)

    with open(file, "w") as f:
        f.write(dump)


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
        THEMES_DIR,
        STYLES_DIR,
        PALETTES_DIR,
        MODULES_DIR,
        TEMP_DIR,
        JSON_SCHEMA_DIR,
    ]:
        dir.mkdir(exist_ok=True, parents=True)

    if not BASE_STYLE_FILE.exists():
        save_json(BASE_STYLE_FILE, default_base_style)
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
