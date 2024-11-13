from __future__ import annotations

import string
import unicodedata
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Tuple

from . import colors as clr
from . import files
from .logger import get_logger
from .utils import AttrDict, DictOrAttrDict, Result, get_thumbnail

log = get_logger(__name__)


@dataclass
class Style:
    name: str
    path: Path
    keywords: dict[str, Any]


@dataclass
class ThemeConfig:
    theme: str | None = None
    mode: str = "dark"


@dataclass
class Mode:
    name: str
    wallpaper: Wallpaper
    palette: clr.Palette
    style: Style | None = None


@dataclass
class Theme:
    path: Path
    name: str
    wallpaper: Wallpaper
    modes: dict[str, Mode] = field(default_factory=dict)
    style: Style | None = None
    tags: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"Theme(name: {self.name})"


def dump_theme(theme: Theme, for_api: bool = False) -> dict[str, Any]:

    def prettify(dic: dict[str, Any]) -> dict[str, Any]:
        new_dic: dict[str, Any] = {}

        for k, v in dic.items():
            if not v:
                continue

            match (v):
                case dict():
                    new_dic[k] = prettify(v)
                case Path():
                    new_dic[k] = str(v)
                case Mode():
                    mode = deepcopy(vars(v))

                    if mode["wallpaper"].path == theme.wallpaper.path:
                        mode.pop("wallpaper")
                    else:
                        mode["wallpaper"] = (
                            mode["wallpaper"].path
                            if for_api
                            else mode["wallpaper"]._path.name
                        )
                    mode.pop("name")
                    mode["palette"] = mode["palette"].dump()

                    new_dic[k] = prettify(mode)
                case Style():
                    if v.name and v.path:
                        new_dic[k] = v.name
                    else:
                        new_dic[k] = v.keywords
                case _:
                    new_dic[k] = v
        return new_dic

    dump = prettify(deepcopy(vars(theme)))
    if not for_api:
        dump.pop("name")
        dump.pop("path")
    dump["wallpaper"] = theme.wallpaper.path if for_api else theme.wallpaper._path.name

    if for_api:
        try:
            thumb = get_thumbnail(theme.wallpaper._path)
            dump["wallpaper_thumb"] = thumb
        except Exception as e:
            log.exception(e)
            log.error(f'failed generating thumbnail for theme "{theme.name}"')
            dump["wallpaper_thumb"] = ""

    return dump


class WallpaperMode(Enum):
    FILL = auto()
    FIT = auto()


@dataclass
class Wallpaper:
    _path: Path
    _mode: WallpaperMode = WallpaperMode.FIT

    @property
    def path(self) -> str:
        return self._path.as_posix()

    @property
    def mode(self) -> str:
        mode = self._mode.name.lower()
        return mode

    def __str__(self) -> str:
        return self.path


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
        "dark": Mode("dark", wallpaper=Wallpaper(image), palette=dark_colors),
        "light": Mode("light", wallpaper=Wallpaper(image), palette=light_colors),
    }

    theme_name = valid_theme_name(name or image.stem, themes)
    theme = Theme(name=theme_name, path=Path(), wallpaper=Wallpaper(image), modes=modes)

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
        theme_dict += theme.modes[mode_name].style.keywords  # type: ignore

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
