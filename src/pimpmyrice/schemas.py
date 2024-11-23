from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field, create_model

from pimpmyrice.theme_utils import Theme

from .config import JSON_SCHEMA_DIR
from .files import save_json
from .utils import Result

if TYPE_CHECKING:
    from .theme import ThemeManager


def create_dynamic_model(name: str, source: dict[str, Any]) -> BaseModel:
    fields = {}
    for key, value in source.items():
        if isinstance(value, dict):
            nested_model = create_dynamic_model(f"{name}_{key}", value)
            fields[key] = (nested_model, {})
        else:
            fields[key] = (type(value), value)

    return create_model(name, **fields)  # type: ignore


def generate_json_schemas(tm: ThemeManager) -> Result:
    def rm(field: str, schema: dict[str, Any]) -> None:
        if field in schema:
            schema.pop(field)

        if field in schema.get("properties", {}):
            schema["properties"].pop(field)

        if field in schema.get("required", []):
            schema["required"].remove(field)

    res = Result()

    style_model = create_dynamic_model("Style", tm.base_style)
    style_schema = style_model.model_json_schema()

    theme_schema = Theme.model_json_schema()

    theme_schema["$defs"] = {**theme_schema["$defs"], **style_schema["$defs"]}
    style_schema.pop("$defs")
    style_schema["required"] = []

    theme_schema["$defs"]["Style"] = style_schema

    rm("name", theme_schema)
    rm("path", theme_schema)

    rm("name", theme_schema["$defs"]["Mode"])
    rm("path", theme_schema["$defs"]["Mode"])

    # theme_schema["$defs"]["Mode"]["required"].remove("wallpaper")

    schema_path = JSON_SCHEMA_DIR / "theme.json"
    save_json(schema_path, theme_schema)

    return res.debug(f'theme schema saved to "{schema_path}"')
