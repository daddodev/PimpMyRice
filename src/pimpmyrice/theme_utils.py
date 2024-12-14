from __future__ import annotations

import string
import unicodedata
from copy import deepcopy
from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    ItemsView,
    KeysView,
    Literal,
    Tuple,
    TypedDict,
    TypeVar,
    ValuesView,
)

from pydantic import BaseModel, Field, computed_field, validator
from pydantic.json_schema import SkipJsonSchema

from pimpmyrice import files
from pimpmyrice.colors import Color, LinkPalette, Palette, exp_gen_palette
from pimpmyrice.config import JSON_SCHEMA_DIR
from pimpmyrice.logger import get_logger
from pimpmyrice.module_utils import FileAction, Module
from pimpmyrice.utils import AttrDict, DictOrAttrDict, Result, get_thumbnail

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = get_logger(__name__)


Style = dict[str, Any]


class ThemeConfig(BaseModel):
    theme: str | None = None
    mode: str = "dark"


class Mode(BaseModel):
    name: SkipJsonSchema[str] = Field(exclude=True)
    palette: LinkPalette | Palette
    wallpaper: Wallpaper | None = None
    style: Style = {}


class WallpaperMode(str, Enum):
    FILL = "fill"
    FIT = "fit"

    def __str__(self) -> str:
        return self.value


class Wallpaper(BaseModel):
    path: Path
    mode: WallpaperMode = WallpaperMode.FILL

    @computed_field  # type: ignore
    @property
    def thumb(self) -> Path:
        t = get_thumbnail(self.path)
        return t


class Theme(BaseModel):
    path: Path = Field()
    name: str = Field()
    wallpaper: Wallpaper
    modes: dict[str, Mode] = {}
    style: Style = {}
    tags: set[str] = set()

    @validator("tags", pre=True)
    def coerce_to_set(cls, value: Any) -> Any:
        if isinstance(value, list):
            return set(value)
        return value


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

    for mode in dump["modes"].values():
        if not mode["style"]:
            mode.pop("style")

        if mode["wallpaper"] == dump["wallpaper"]:
            mode.pop("wallpaper")
        else:
            mode["wallpaper"]["path"] = str(Path(mode["wallpaper"]["path"]).name)
            if mode["wallpaper"]["mode"] == "fill":
                mode["wallpaper"].pop("mode")

    if not dump["style"]:
        dump.pop("style")

    dump["wallpaper"]["path"] = str(Path(dump["wallpaper"]["path"]).name)

    if dump["wallpaper"]["mode"] == "fill":
        dump["wallpaper"].pop("mode")

    if not dump["tags"]:
        dump.pop("tags")

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

    dark_colors = await exp_gen_palette(image)
    light_colors = await exp_gen_palette(image, light=True)
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

            if isinstance(d, Color):
                res = getattr(d, ref_slices[0])
                data[key] = Color(res)
            elif ref_slices[0] in d and not str(d[ref_slices[0]]).startswith("$"):
                data[key] = d[ref_slices[0]]
            else:
                unresolved.append(key)

    return data, unresolved


def gen_theme_dict(
    tm: ThemeManager,
    theme_name: str,
    mode_name: str,
    palette_name: str | None = None,
    styles_names: list[str] | None = None,
) -> Result[AttrDict]:

    res: Result[AttrDict] = Result()

    theme = tm.themes[theme_name]

    if mode_name not in theme.modes:
        new_mode = [*theme.modes.keys()][0]
        res.warning(f'"{mode_name}" mode not present in theme, applying "{new_mode}"')
        mode_name = new_mode

    styles: list[Style] = []

    if theme.style:
        if from_global := theme.style.get("from_global"):
            if from_global not in tm.styles:
                return res.error(
                    f'global style "{from_global}" not found in {list(tm.styles)}'
                )
            theme_style = AttrDict(**tm.styles[from_global]) + theme.style
            styles.append(theme_style)
        else:
            styles.append(theme.style)

    if mode_style := theme.modes[mode_name].style:
        if from_global := mode_style.get("from_global"):
            if from_global not in tm.styles:
                return res.error(
                    f'global style "{from_global}" not found in {list(tm.styles)}'
                )
            mode_style = AttrDict(**tm.styles[from_global]) + mode_style

        styles.append(mode_style)

    if styles_names:
        for style in styles_names:
            if style not in tm.styles:
                return res.error(
                    f'global style "{style}" not found in {list(tm.styles)}'
                )
            styles.append(tm.styles[style])

    palette: Palette
    if palette_name:
        if palette_name in tm.palettes:
            palette = tm.palettes[palette_name]
        else:
            return res.error(f'palette "{palette_name}" not found')
    else:
        mode_palette = theme.modes[mode_name].palette
        if isinstance(mode_palette, LinkPalette):
            from_global = mode_palette.from_global

            if from_global not in tm.palettes:
                return res.error(
                    f'global style "{from_global}" not found in {list(tm.palettes)}'
                )

            palette = tm.palettes[from_global]
        else:
            palette = mode_palette

    theme = deepcopy(theme)
    styles = deepcopy(styles)
    palette = palette.copy()
    base_style = deepcopy(tm.base_style)

    theme_dict = AttrDict(palette.model_dump())

    theme_dict["theme_name"] = theme.name
    theme_dict["wallpaper"] = theme.modes[mode_name].wallpaper
    theme_dict["mode"] = mode_name

    theme_dict += base_style

    if theme.style:
        theme_dict += theme.style

    if theme.modes[mode_name].style:
        theme_dict += theme.modes[mode_name].style

    if styles:
        for s in styles:
            theme_dict += s

    theme_dict, pending = resolve_refs(theme_dict)
    while len(pending) > 0:
        c = len(pending)
        theme_dict, pending = resolve_refs(theme_dict)
        if len(pending) == c:
            break

    for p in pending:
        res.error(f'keyword reference for "{p}" not found')

    res.value = theme_dict

    res.ok = True
    return res


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
