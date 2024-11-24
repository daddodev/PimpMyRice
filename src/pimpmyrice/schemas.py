from __future__ import annotations

import json
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field, create_model

from pimpmyrice.theme_utils import Theme

from .config import JSON_SCHEMA_DIR
from .files import save_json
from .utils import Result

if TYPE_CHECKING:
    from .theme import ThemeManager


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


def generate_json_schemas(tm: ThemeManager) -> Result:
    def rm(field: str, schema: dict[str, Any]) -> None:
        if field in schema:
            schema.pop(field)

        if field in schema.get("properties", {}):
            schema["properties"].pop(field)

        if field in schema.get("required", []):
            schema["required"].remove(field)

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
                    "enum": [t for t in tm.tags],
                    "type": "string",
                },
            ]
        },
        "title": "Tags",
        "type": "array",
        "uniqueItems": True,
    }

    theme_schema["properties"]["tags"] = tags_schema

    theme_schema["$defs"] = {**theme_schema["$defs"], **style_schema["$defs"]}
    style_schema.pop("$defs")
    style_schema["required"] = []

    theme_schema["$defs"]["Style"] = style_schema

    rm("name", theme_schema)
    rm("path", theme_schema)

    rm("name", theme_schema["$defs"]["Mode"])
    rm("path", theme_schema["$defs"]["Mode"])

    # theme_schema["$defs"]["Mode"]["required"].remove("wallpaper")

    # print(json.dumps(theme_schema, indent=4))

    schema_path = JSON_SCHEMA_DIR / "theme.json"
    save_json(schema_path, theme_schema)

    return res.debug(f'theme schema saved to "{schema_path}"')
