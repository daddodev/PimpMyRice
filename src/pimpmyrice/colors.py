from __future__ import annotations

import colorsys
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Tuple

import cv2
from colour import Color as Colour
from sklearn.cluster import KMeans

from . import files
from .config import PALETTES_DIR
from .logger import get_logger
from .utils import Timer

log = get_logger(__name__)


class Color(Colour):  # type: ignore
    def __init__(
        self,
        *args: Any,
        hsv: tuple[float, float, float] | None = None,
        **kwargs: Any,
    ) -> None:
        if hsv:
            h, s, v = hsv
            r, g, b = colorsys.hsv_to_rgb(h / 360, s, v)
            super(Color, self).__init__(*args, **kwargs, rgb=(r, g, b))
        else:
            super(Color, self).__init__(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.get_hex_l())

    @property
    def alt(self) -> Color:
        c = Color(self)
        lum = c.get_luminance()
        if lum > 0.5:
            c.set_luminance(lum - 0.05)
        else:
            c.set_luminance(lum + 0.05)
        return c

    @property
    def maxsat(self) -> Color:
        c = Color(self)
        c.set_saturation(1)
        c.set_luminance(0.5)
        return c

    @property
    def hsv(self) -> Tuple[float, ...]:
        h, s, v = colorsys.rgb_to_hsv(*self.get_rgb())
        h = h * 360
        hsv = tuple(round(n, 2) for n in (h, s, v))
        return hsv

    @property
    def hsl(self) -> Tuple[float, ...]:
        color = tuple(round(v, 2) for v in self.get_hsl())
        return color

    @property
    def nohash(self) -> str:
        return str(self)[1:]

    @property
    def int_rgb(self) -> Tuple[int, ...]:
        return tuple(int(v * 255) for v in self.rgb)


@dataclass
class Palette:
    name: str | None = None
    path: Path | None = None
    term: dict[str, Color] | None = None
    normal: dict[str, Color] | None = None
    panel: dict[str, Color] | None = None
    dialog: dict[str, Color] | None = None
    input: dict[str, Color] | None = None
    border: dict[str, Color] | None = None
    muted: dict[str, Color] | None = None
    primary: dict[str, Color] | None = None
    secondary: dict[str, Color] | None = None
    accent: dict[str, Color] | None = None
    destructive: dict[str, Color] | None = None

    def copy(self) -> Palette:
        return Palette(**deepcopy(vars(self)))

    def dump(self, color_class: bool = False) -> dict[str, Any]:
        dump = ensure_color(deepcopy(vars(self)), color=color_class)
        dump.pop("name")
        dump.pop("path")

        sorted_term = dict(
            sorted(dump["term"].items(), key=lambda v: int(v[0].removeprefix("color")))
        )

        dump["term"] = sorted_term

        return dump


def get_palettes() -> dict[str, Palette]:
    palettes = {}
    for file in PALETTES_DIR.iterdir():
        try:
            palette = files.load_json(file)
            palette = ensure_color(palette)
            palettes[file.stem] = Palette(name=file.stem, path=file, **palette)
        except Exception as e:
            log.exception(e)
            log.error(f'Failed to load palette "{file.stem}"')
    return palettes


def palette_display_string(colors: Any) -> str:
    circles = []
    for i in range(16):
        circles.append(f"[{Color(colors[f'color{i}']).hex}]🔘[/]")

    palette_string = " ".join(circles[0:8]) + "\r\n" + " ".join(circles[8:])

    return palette_string


def ensure_color(
    dic: dict[str, Any], color: bool = True, hsv: bool = False
) -> dict[str, Any]:
    for k, v in dic.items():
        if k == "name" or k == "path":
            continue

        if isinstance(v, dict):
            dic[k] = ensure_color(v, color, hsv)
        elif color:
            if hsv:
                dic[k] = Color(hsv=v)
            else:
                dic[k] = Color(v)
        else:
            dic[k] = str(v)
    return dic


def exp_extract_colors(img: Path) -> list[tuple[tuple[float, ...], int]]:
    def preprocess(raw: Any) -> Any:
        image = cv2.resize(raw, (600, 600), interpolation=cv2.INTER_AREA)
        image = image.reshape(image.shape[0] * image.shape[1], 3)
        return image

    def analyze(img: Any) -> list[tuple[Color, int]]:
        clf = KMeans(n_clusters=5, random_state=0, n_init="auto")
        color_labels = clf.fit_predict(img)
        center_colors = clf.cluster_centers_
        counts = Counter(color_labels)
        ordered_colors = [center_colors[i] for i in counts.keys()]

        color_objects = [
            (Color(rgb=[v / 255 for v in ordered_colors[i]]), c // 1000)
            for i, c in counts.items()
        ]

        color_objects.sort(key=lambda x: x[1], reverse=True)

        # display_color_palette({count: color.hex for color, count in color_objects})
        return color_objects

    image = cv2.imread(str(img))
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    modified_image = preprocess(image)
    colors = analyze(modified_image)

    hsv_colors = [(color.hsv, count) for (color, count) in colors]

    return hsv_colors


async def exp_gen_palette(img: Path, light: bool = False) -> Palette:
    # TODO refactor everything

    def apply_rule(clr: Tuple[float, ...], rule: dict[str, float]) -> Tuple[float, ...]:
        h, s, v = clr

        if s < rule["min_sat"]:
            s = rule["min_sat"]
        elif s > rule["max_sat"]:
            s = rule["max_sat"]

        if v < rule["min_val"]:
            v = rule["min_val"]
        elif v > rule["max_val"]:
            v = rule["max_val"]

        return h, s, v

    def are_hues_close(h1: float, h2: float, r: int = 30) -> bool:
        if abs(h1 - h2) < r:
            return True
        elif h1 - r < 0 and h1 + 360 - h2 < r:
            return True
        elif h2 - r < 0 and h2 + 360 - h1 < r:
            return True
        return False

    timer = Timer()

    extracted_hsv_colors = exp_extract_colors(img)

    main_color = extracted_hsv_colors[0][0]

    by_sat = sorted(extracted_hsv_colors, reverse=True, key=lambda x: x[0][1])
    by_sat_no_dark = [c for c in by_sat if c[0][2] > 0.3]

    saturated_colors = [
        c[0] for c in sorted(by_sat_no_dark, reverse=True, key=lambda x: x[1])
    ]

    if are_hues_close(saturated_colors[0][0], main_color[0]):
        saturated_colors.pop(0)

    primary = saturated_colors[0] if len(saturated_colors) > 0 else by_sat.pop(0)[0]
    secondary = saturated_colors[1] if len(saturated_colors) > 1 else by_sat.pop(0)[0]
    accent = saturated_colors[2] if len(saturated_colors) > 2 else by_sat.pop(0)[0]

    most_saturated = primary

    dark_rules: dict[str, Any] = {
        "normal": {
            "color": main_color,
            "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0, "max_val": 0.1},
            "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "panel": {
            "color": main_color,
            "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0.15, "max_val": 0.2},
            "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "dialog": {
            "color": main_color,
            "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0.25, "max_val": 0.35},
            "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "primary": {
            "color": primary,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "secondary": {
            "color": secondary,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 1},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "term": {"min_sat": 0.2, "max_sat": 0.45, "min_val": 0.8, "max_val": 1},
        "input": {
            "color": primary,
            "bg": {"min_sat": 0.1, "max_sat": 0.5, "min_val": 0.25, "max_val": 0.35},
            "fg": {"min_sat": 0.1, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "border": {
            "color": primary,
            "active": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.5, "max_val": 0.9},
            "inactive": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.2},
        },
        "accent": {
            "color": accent,
            "bg": {"min_sat": 0.2, "max_sat": 0.45, "min_val": 0.8, "max_val": 1},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "muted": {
            "color": main_color,
            "bg": {"min_sat": 0.1, "max_sat": 0.3, "min_val": 0.8, "max_val": 1},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
        "destructive": {
            "color": accent,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 1},
        },
    }

    light_rules: dict[str, Any] = {
        "normal": {
            "color": main_color,
            "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.9, "max_val": 0.95},
            "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
        },
        "panel": {
            "color": main_color,
            "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.85, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
        },
        "dialog": {
            "color": main_color,
            "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.7, "max_val": 0.8},
            "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
        },
        "primary": {
            "color": primary,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
        },
        "secondary": {
            "color": secondary,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
        },
        "term": {"min_sat": 0.55, "max_sat": 0.8, "min_val": 0.3, "max_val": 0.5},
        "input": {
            "color": primary,
            "bg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.7, "max_val": 0.8},
            "fg": {"min_sat": 0, "max_sat": 0.3, "min_val": 0, "max_val": 0.12},
        },
        "border": {
            "color": primary,
            "active": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.6, "max_val": 0.9},
            "inactive": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.9, "max_val": 0.9},
        },
        "accent": {
            "color": accent,
            "bg": {"min_sat": 0.55, "max_sat": 0.8, "min_val": 0.45, "max_val": 0.65},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
        },
        "muted": {
            "color": main_color,
            "bg": {"min_sat": 0.3, "max_sat": 0.5, "min_val": 0.45, "max_val": 0.65},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
        },
        "destructive": {
            "color": accent,
            "bg": {"min_sat": 0.4, "max_sat": 0.7, "min_val": 0.4, "max_val": 0.9},
            "fg": {"min_sat": 0, "max_sat": 0.1, "min_val": 0.8, "max_val": 0.6},
        },
    }

    rules = light_rules if light else dark_rules

    palette: dict[str, Any] = {}

    for outer_name, outer in rules.items():
        if outer_name == "term":
            palette["term"] = {
                "color0": apply_rule(main_color, rules["normal"]["bg"]),
                "color15": apply_rule(main_color, rules["normal"]["fg"]),
            }
            continue
        if outer_name not in palette:
            palette[outer_name] = {}
        for inner_name, rule in outer.items():
            if inner_name == "color":
                continue
            palette[outer_name][inner_name] = apply_rule(outer["color"], rule)

    for k, v in palette.items():
        if "bg" in v and "fg" in v:
            if v["bg"][2] > 0.7 and v["bg"][2] - v["fg"][2] < 0.65:
                new_fg_v = v["bg"][2] - 0.65
                if new_fg_v < 0.1:
                    new_fg_v = 0.1
                v["fg"] = (v["fg"][0], v["fg"][1], new_fg_v)
            elif v["bg"][2] < 0.7 and v["fg"][2] - v["bg"][2] < 0.65:
                new_fg_v = v["bg"][2] + 0.65
                if new_fg_v > 0.9:
                    new_fg_v = 0.9
                v["fg"] = (v["fg"][0], v["fg"][1], new_fg_v)

    base = palette["term"]["color0"]
    palette["term"][f"color{8}"] = apply_rule(
        (base[0], 0.3, base[2] + (-0.3 if light else 0.3)), rules["term"]
    )

    for i in range(1, 8):
        hue = most_saturated[0] + 45 * (i - 1)
        if hue > 360:
            hue -= 360

        palette["term"][f"color{i}"] = apply_rule(
            (hue, most_saturated[1], most_saturated[2]), rules["term"]
        )

    for i in range(9, 15):
        h, s, v = palette["term"][f"color{i-8}"]

        palette["term"][f"color{i}"] = apply_rule(
            (
                h,
                s - 0.1,
                v - 0.1,
            ),
            rules["term"],
        )

    palette = ensure_color(palette, hsv=True)

    # palette_display_string(palette["term"])

    p = Palette(**palette)

    log.info(
        f'{"light" if light else "dark"} colors for "{img.name}" generated in {timer.elapsed():.2f} seconds'
    )

    return p
