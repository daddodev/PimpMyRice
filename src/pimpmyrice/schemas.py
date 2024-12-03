from __future__ import annotations

import os
import re
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Generator

from docopt import formal_usage, parse_defaults, parse_pattern, printable_usage
from infi.docopt_completion.common import (
    CommandParams,
    build_command_tree,
    get_options_descriptions,
)
from infi.docopt_completion.docopt_completion import _autodetect_generators
from pydantic import BaseModel, create_model

from pimpmyrice.config import JSON_SCHEMA_DIR
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

    theme_schema["properties"]["tags"] = tags_schema

    theme_schema["$defs"] = {**theme_schema["$defs"], **style_schema["$defs"]}
    style_schema.pop("$defs")
    style_schema["required"] = []

    theme_schema["$defs"]["Style"] = style_schema

    theme_schema["$defs"]["Mode"]["properties"]["style"] = {"$ref": "#/$defs/Style"}

    theme_schema["properties"]["style"] = {"$ref": "#/$defs/Style"}

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


def add_zsh_suggestions(file_content: str, arg_name: str, values: list[str]) -> str:
    if arg_name == "--tags":
        replaced = ""

        found_tags = False
        for i, line in enumerate(file_content.splitlines()):
            if "(--tags=-)--tags=-" in line:
                found_tags = True
                line = "		'--tags=:flag:->flags' \\"
            elif "}" in line and found_tags:
                found_tags = False
                line = f"""
    case "$state" in flags)
        _values -s , 'flags' {" ".join(f'"{x}"' for x in values)}
    esac
}}
"""

            replaced += line + "\n"

    elif arg_name == "IMAGE":

        replaced = file_content.replace(
            f"""
        myargs=('{arg_name.upper()}')
        _message_next_arg
""",
            f"""
        myargs=('{arg_name.upper()}')
        _files
""",
        )
    else:

        replaced = file_content.replace(
            f"""
        myargs=('{arg_name.upper()}')
        _message_next_arg
""",
            f"""
        local -a available_{arg_name}s
        available_{arg_name}s=({" ".join(f'"{x}"' for x in values)})

        _describe '{arg_name} name' available_{arg_name}s
""",
        )

    return replaced


def generate_shell_suggestions(tm: ThemeManager) -> None:
    # TODO fork docopt_completion

    doc = cli_doc

    options = parse_defaults(doc)
    pattern = parse_pattern(formal_usage(printable_usage(doc)), options)
    param_tree = CommandParams()
    build_command_tree(pattern, param_tree)
    option_help = dict(list(get_options_descriptions(doc)))

    generators_to_use = _autodetect_generators()
    for generator in generators_to_use:
        content = generator.get_completion_file_content("pimp", param_tree, option_help)

        content = add_zsh_suggestions(content, "theme", [*tm.themes.keys()])
        content = add_zsh_suggestions(content, "module", [*tm.mm.modules.keys()])
        content = add_zsh_suggestions(content, "--tags", list(tm.tags))
        content = add_zsh_suggestions(content, "IMAGE", [])

        file_paths = generator.get_completion_filepath("pimp")
        if not isinstance(file_paths, Generator):
            file_paths = [file_paths]
        for file_path in file_paths:
            if not os.access(os.path.dirname(file_path), os.W_OK):
                log.debug(
                    "Skipping file {file_path}, no permissions".format(
                        file_path=file_path
                    )
                )
                return
            try:
                with open(file_path, "w") as fd:
                    fd.write(content)
            except IOError:
                log.debug("Failed to write {file_path}".format(file_path=file_path))
                return
            log.debug(
                "Completion file written to {file_path}".format(file_path=file_path)
            )
