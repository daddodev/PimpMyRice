from __future__ import annotations

import os
import re
import subprocess
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Generator

from pydantic import BaseModel, create_model

from pimpmyrice.config import CLIENT_OS, HOME_DIR, JSON_SCHEMA_DIR, Os
from pimpmyrice.doc import __doc__ as cli_doc
from pimpmyrice.files import save_json
from pimpmyrice.logger import get_logger
from pimpmyrice.module_utils import Module
from pimpmyrice.theme_utils import Theme
from pimpmyrice.utils import Result

if TYPE_CHECKING:
    from pimpmyrice.theme import ThemeManager

log = get_logger(__name__)


def create_dynamic_model(name: str, source: dict[str, Any]) -> BaseModel:
    fields: dict[str, Any] = {}
    for key, value in source.items():
        if isinstance(value, dict):
            nested_model = create_dynamic_model(f"{name}_{key}", value)
            fields[key] = (nested_model, {})
        else:
            fields[key] = (type(value), value)

    model: BaseModel = create_model(name, **fields)

    return model


def get_fonts(mono: bool = False) -> list[str]:
    # TODO windows
    if CLIENT_OS == Os.WINDOWS:
        log.warning("getting font list not yet supported on Windows")
        return []

    try:
        output = subprocess.check_output(
            ["fc-list", ":spacing=mono" if mono else ":family"], text=True
        )
        font_names = [line.split(":")[1].strip() for line in output.splitlines()]
        return sorted(set(font_names))

    except FileNotFoundError:
        log.warning("fontconfig not installed")
        return []


def generate_theme_json_schema(tm: ThemeManager) -> Result:
    res = Result()

    base_style = deepcopy(tm.base_style)

    for module in tm.mm.modules:
        if module not in base_style["modules_styles"]:
            base_style["modules_styles"][module] = {}

    style_model = create_dynamic_model("Style", base_style)
    style_schema = style_model.model_json_schema()

    theme_schema = Theme.model_json_schema()

    tags_schema = {
        "default": [],
        "items": {
            "anyOf": [
                {"type": "string"},
                {
                    "const": "",
                    "enum": list(tm.tags),
                    "type": "string",
                },
            ]
        },
        "title": "Tags",
        "type": "array",
        "uniqueItems": True,
    }

    normal_fonts = get_fonts()
    normal_font_schema = {
        "anyOf": [
            {"type": "string"},
            {
                "const": "",
                "enum": normal_fonts,
                "type": "string",
            },
        ],
        "title": "Normal font",
        "default": "",
    }

    mono_fonts = get_fonts(mono=True)
    mono_font_schema = {
        "anyOf": [
            {"type": "string"},
            {
                "const": "",
                "enum": mono_fonts,
                "type": "string",
            },
        ],
        "title": "Mono font",
        "default": "",
    }

    theme_schema["properties"]["tags"] = tags_schema

    theme_schema["$defs"] = {**theme_schema["$defs"], **style_schema["$defs"]}
    style_schema.pop("$defs")
    style_schema["required"] = []

    theme_schema["$defs"]["Style"] = style_schema

    theme_schema["$defs"]["Mode"]["properties"]["style"] = {"$ref": "#/$defs/Style"}

    theme_schema["properties"]["style"] = {"$ref": "#/$defs/Style"}

    theme_schema["$defs"]["Style_font_normal"]["properties"][
        "family"
    ] = normal_font_schema
    theme_schema["$defs"]["Style_font_mono"]["properties"]["family"] = mono_font_schema

    theme_schema["properties"].pop("name")
    theme_schema["properties"].pop("path")
    theme_schema["required"].remove("name")
    theme_schema["required"].remove("path")

    schema_path = JSON_SCHEMA_DIR / "theme.json"
    save_json(schema_path, theme_schema)

    return res.debug(f'theme schema saved to "{schema_path}"')


def generate_module_json_schema() -> Result:
    res = Result()

    module_schema = Module.model_json_schema()

    schema_path = JSON_SCHEMA_DIR / "module.json"
    save_json(schema_path, module_schema)

    return res.debug(f'module schema saved to "{schema_path}"')
