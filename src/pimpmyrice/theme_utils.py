from __future__ import annotations

import json
import string
import unicodedata
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Tuple

from pydantic import (BaseModel, Field, computed_field, model_serializer,
                      model_validator)
from pydantic.json_schema import SkipJsonSchema

from . import colors as clr
from . import files
from .config import JSON_SCHEMA_DIR
from .logger import get_logger
from .utils import AttrDict, DictOrAttrDict, Result, get_thumbnail

log = get_logger(__name__)


class Style(BaseModel):
    name: str | None = Field(default=None, exclude=True)
    path: Path | None = Field(default=None, exclude=True)
    keywords: dict[str, Any] = {}

    @model_serializer
    def ser_model(self) -> dict[str, Any]:
        return self.keywords

    @model_validator(mode="before")
    @classmethod
    def handle_input(cls, values: dict[str, Any] | str) -> Any:
        if isinstance(values, dict):
            if "path" in values:
                return values

            return {"keywords": values}

        return values


class ThemeConfig(BaseModel):
    theme: str | None = None
    mode: str = "dark"


class Mode(BaseModel):
    name: str = Field(exclude=True)
    palette: clr.Palette
    wallpaper: Wallpaper
    style: Style = Field(default_factory=lambda: Style())


class WallpaperMode(str, Enum):
    FILL = "fill"
    FIT = "fit"

    def __str__(self) -> str:
        return self.value


class Wallpaper(BaseModel):
    path: Path
    mode: WallpaperMode = WallpaperMode.FIT

    @computed_field  # type: ignore
    @property
    def thumb(self) -> Path:
        t = get_thumbnail(self.path)
        return t

    @model_validator(mode="before")
    def handle_input(cls, value: dict[str, Any] | str) -> Any:
        if isinstance(value, str):
            return {"path": value, "mode": "fill"}

        # if isinstance(path, str):
        #     values["path"] = Path(path)
        return value

    # @model_serializer
    # def ser_model(self) -> dict[str, Any]:
    #     return {"mode": self.mode, "path": self.path.name}

    # def __str__(self) -> str:
    #     return str(self.path)


class Theme(BaseModel):
    path: Path = Field()
    name: str = Field()
    wallpaper: Wallpaper
    modes: dict[str, Mode] = {}
    style: Style = Field(default_factory=Style)
    tags: list[str] = []

    @model_validator(mode="before")
    def handle_input(cls, values: dict[str, Any] | str) -> Any:
        # if isinstance(values, dict):
        #     if "path" in values:
        #         return values
        #
        #     return {"keywords": values}

        return values

    def __repr__(self) -> str:
        return f"Theme(name: {self.name})"


def dump_theme_for_file(theme: Theme) -> dict[str, Any]:
    dump = theme.model_dump(
        mode="json",
        exclude={
            "name": True,
            "path": True,
            "wallpaper": {"thumb"},
            "modes": {"__all__": {"wallpaper": {"thumb"}}},
        },
    )
    dump["$schema"] = str(JSON_SCHEMA_DIR / "theme.json")

    dump["wallpaper"]["path"] = str(Path(dump["wallpaper"]["path"]).name)

    for mode_name, mode in dump["modes"].items():
        mode["wallpaper"]["path"] = str(Path(mode["wallpaper"]["path"]).name)

    # print("dump for file:", json.dumps(dump, indent=4))
    return dump


async def gen_from_img(
    image: Path,
    themes: dict[str, Theme],
    name: str | None = None,
) -> Result[Theme]:
    res: Result[Theme] = Result()

    if not image.is_file():
        return res.error(f'image not found at "{image}"')

    dark_colors = await clr.exp_gen_palette(image)
    light_colors = await clr.exp_gen_palette(image, light=True)
    modes = {
        "dark": Mode(name="dark", wallpaper=Wallpaper(path=image), palette=dark_colors),
        "light": Mode(
            name="light", wallpaper=Wallpaper(path=image), palette=light_colors
        ),
    }

    theme_name = valid_theme_name(name or image.stem, themes)
    theme = Theme(
        name=theme_name, path=Path(), wallpaper=Wallpaper(path=image), modes=modes
    )

    res.value = theme

    return res


def resolve_refs(
    data: DictOrAttrDict, theme_dict: DictOrAttrDict | None = None
) -> Tuple[DictOrAttrDict, list[str]]:
    if not theme_dict:
        theme_dict = deepcopy(data)

    unresolved = []

    for key, value in data.items():
        if isinstance(value, dict):
            data[key], pending = resolve_refs(value, theme_dict)
            for p in pending:
                unresolved.append(f"{key}.{p}")
        elif isinstance(value, str) and value.startswith("$"):
            ref = value[1:]

            ref_slices = ref.split(".")
            d = theme_dict

            while len(ref_slices) > 1:
                if ref_slices[0] in d:
                    d = d[ref_slices[0]]
                else:
                    unresolved.append(key)
                    break
                ref_slices.pop(0)

            if isinstance(d, clr.Color):
                res = getattr(d, ref_slices[0])
                data[key] = clr.Color(res)
            elif ref_slices[0] in d and not str(d[ref_slices[0]]).startswith("$"):
                data[key] = d[ref_slices[0]]
            else:
                unresolved.append(key)

    return data, unresolved


def gen_theme_dict(
    theme: Theme,
    base_style: dict[str, Any],
    mode_name: str,
    palette: clr.Palette,
    styles: list[Style] | None = None,
) -> AttrDict:
    theme = deepcopy(theme)
    styles = deepcopy(styles)
    palette = palette.copy()
    base_style = deepcopy(base_style)

    theme_dict = AttrDict(palette.dump(color_class=True))

    theme_dict["theme_name"] = theme.name
    theme_dict["wallpaper"] = theme.modes[mode_name].wallpaper
    theme_dict["mode"] = mode_name

    theme_dict += base_style

    if theme.style:
        theme_dict += theme.style.keywords

    if theme.modes[mode_name].style:
        # idk why "type: ignore" is needed
        theme_dict += theme.modes[mode_name].style.keywords

    if styles:
        for style in styles:
            theme_dict += style.keywords

    theme_dict, pending = resolve_refs(theme_dict)
    while len(pending) > 0:
        c = len(pending)
        theme_dict, pending = resolve_refs(theme_dict)
        if len(pending) == c:
            break

    for p in pending:
        log.error(f'keyword reference for "{p}" not found')
    return theme_dict


def valid_theme_name(name: str, themes: dict[str, Theme]) -> str:
    whitelist = "-_.() %s%s" % (string.ascii_letters, string.digits)
    char_limit = 20
    cleaned_filename = (
        unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode()
    )
    cleaned_filename = "".join(c for c in cleaned_filename if c in whitelist)
    name = cleaned_filename[:char_limit].replace(" ", "_").lower().strip()

    tries = 1
    n = name
    while n in themes:
        n = f"{name}_{tries+1}"
        tries += 1
    return n


def import_image(wallpaper: Path, theme_dir: Path) -> Path:
    if wallpaper.parent != theme_dir and not (theme_dir / wallpaper.name).exists():
        wallpaper = files.import_image(wallpaper, theme_dir)
        log.info(f'"{wallpaper.name}" imported')
    return theme_dir / wallpaper.name
