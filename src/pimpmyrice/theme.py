import random
import shutil
from pathlib import Path
from typing import Any

import rich

from pimpmyrice import parsers, schemas
from pimpmyrice import theme_utils as tutils
from pimpmyrice.colors import (
    GlobalPalette,
    LinkPalette,
    Palette,
    exp_gen_palette,
    get_palettes,
)
from pimpmyrice.completions import generate_shell_suggestions
from pimpmyrice.config import BASE_STYLE_FILE, CONFIG_FILE, STYLES_DIR, THEMES_DIR
from pimpmyrice.events import EventHandler
from pimpmyrice.files import (
    check_config_dirs,
    download_file,
    load_json,
    save_json,
    save_yaml,
)
from pimpmyrice.logger import get_logger
from pimpmyrice.module import ModuleManager
from pimpmyrice.theme_utils import Mode, Style, Theme, ThemeConfig
from pimpmyrice.utils import AttrDict, Result, Timer

log = get_logger(__name__)


class ThemeManager:
    def __init__(self) -> None:
        timer = Timer()
        check_config_dirs()
        self.base_style = self.get_base_style()
        self.styles = self.get_styles()
        self.palettes = self.get_palettes()
        self.tags: set[str] = set()
        self.themes = self.get_themes()
        self.config = self.get_config()
        self.event_handler = EventHandler()
        self.mm = ModuleManager()

        # TODO move
        try:
            schemas.generate_theme_json_schema(self)
            schemas.generate_module_json_schema()
            generate_shell_suggestions(self)
        except Exception as e:
            log.exception(e)
            log.error("failed to generate suggestions")

        log.debug(f"ThemeManager initialized in {timer.elapsed():.4f} sec")

    def get_config(self) -> ThemeConfig:
        config = ThemeConfig(**load_json(CONFIG_FILE))
        if config.theme not in self.themes:
            config.theme = None
        return config

    def save_config(self) -> None:
        save_json(CONFIG_FILE, vars(self.config))

    @staticmethod
    def get_base_style() -> dict[str, Any]:
        try:
            return load_json(BASE_STYLE_FILE)
        except Exception:
            log.error("failed loading base_style.json")
            raise

    def save_base_style(self, base_style: dict[str, Any]) -> None:
        save_json(BASE_STYLE_FILE, base_style)
        self.base_style = base_style
        schemas.generate_theme_json_schema(self)

    @staticmethod
    def get_styles() -> dict[str, Style]:
        styles: dict[str, Style] = {f.stem: load_json(f) for f in STYLES_DIR.iterdir()}
        return styles

    @staticmethod
    def get_palettes() -> dict[str, GlobalPalette]:
        return get_palettes()

    def parse_theme(self, theme_path: Path) -> Theme:
        theme = parsers.parse_theme(theme_path, self.styles, self.palettes)

        return theme

    def get_themes(self) -> dict[str, Theme]:
        timer = Timer()

        themes: dict[str, Theme] = {}

        for directory in THEMES_DIR.iterdir():
            if not (directory / "theme.json").is_file():
                continue

            try:
                theme = self.parse_theme(directory)
            except Exception as e:
                log.exception(e)
                log.error(f'Error parsing theme "{directory.name}": {str(e)}')
                continue

            themes[directory.name] = theme

            for tag in theme.tags:
                self.tags.add(tag)

        log.debug(f"{len(themes)} themes loaded in {timer.elapsed():.4f} sec")

        return themes

    async def generate_theme(
        self,
        image: str,
        name: str | None = None,
        tags: set[str] | None = None,
        apply: bool = False,
    ) -> Result:
        res = Result()

        if image.startswith(("http://", "https://")):
            download_res = download_file(image)
            if download_res.value is None:
                res += download_res
                return res.error("could not download file")
            file = download_res.value
            res.info(f'downloaded "{file.name}"')
        else:
            file = Path(image)

        gen_res = await tutils.gen_from_img(image=file, name=name, themes=self.themes)
        res += gen_res
        if not gen_res.value:
            return res.error("could not generate theme")

        if tags:
            gen_res.value.tags = tags

        # TODO generate name here
        save_res = await self.save_theme(gen_res.value)
        res += save_res
        if save_res.value:
            res.success(f'theme "{save_res.value}" generated')
        else:
            return res.error("could not generate theme")

        if apply:
            apply_res = await self.apply_theme(save_res.value)
            res += apply_res

        res.ok = True
        return res

    async def rename_theme(
        self,
        theme_name: str,
        new_name: str,
    ) -> Result:
        res = Result()

        if theme_name not in self.themes:
            return res.error(f'theme "{theme_name}" not found')

        theme = self.themes[theme_name]
        old_name = theme.name
        theme.name = new_name

        save_res = await self.save_theme(theme, old_name=old_name)
        res += save_res

        if not save_res.value:
            return res.error(f'failed renaming theme "{theme_name}"')

        res.ok = True
        return res.success(f'renamed theme "{theme_name}" to "{new_name}"')

    async def save_theme(
        self,
        theme: Theme,
        old_name: str | None = None,
    ) -> Result[str]:
        res: Result[str] = Result()

        if not old_name:
            theme.name = tutils.valid_theme_name(name=theme.name, themes=self.themes)
            theme_dir = THEMES_DIR / theme.name
            theme_dir.mkdir()

        elif old_name != theme.name:
            theme.name = tutils.valid_theme_name(name=theme.name, themes=self.themes)
            theme_dir = THEMES_DIR / theme.name
            (THEMES_DIR / old_name).rename(theme_dir)
        else:
            theme_dir = THEMES_DIR / theme.name

        # NOTE full path update on rename is handled by dump_theme
        #      as it leaves only the filename
        theme.wallpaper.path = tutils.import_image(theme.wallpaper.path, theme_dir)
        for mode in theme.modes.values():
            if mode.wallpaper:
                mode.wallpaper.path = tutils.import_image(
                    mode.wallpaper.path, theme_dir
                )

        dump = tutils.dump_theme_for_file(theme)
        save_json(theme_dir / "theme.json", dump)
        # save_yaml(theme_dir / "theme.yaml", dump)

        parsed_theme = self.parse_theme(THEMES_DIR / theme.name)

        self.themes[theme.name] = parsed_theme

        if old_name and old_name != theme.name:
            self.themes.pop(old_name)

            if self.config.theme == old_name:
                self.config.theme = theme.name

        res.value = theme.name
        res.ok = True
        return res

    async def rewrite_themes(
        self,
        regen_colors: bool = False,
        name_includes: str | None = None,
        include_tags: set[str] | None = None,
        exclude_tags: set[str] | None = None,
    ) -> Result:
        res = Result()

        for theme in self.themes.values():
            if name_includes and name_includes not in theme.name:
                continue

            if include_tags and not any(tag in include_tags for tag in theme.tags):
                continue

            if exclude_tags and any(tag in exclude_tags for tag in theme.tags):
                continue

            mode_names = {"light", "dark", *theme.modes.keys()}

            if regen_colors:
                for mode_name in mode_names:
                    if mode_name not in theme.modes:
                        palette = await exp_gen_palette(
                            img=theme.wallpaper.path, light=("light" in mode_name)
                        )
                        theme.modes[mode_name] = Mode(
                            name=mode_name,
                            wallpaper=theme.wallpaper,
                            palette=palette,
                        )
                    else:
                        mode = theme.modes[mode_name]
                        if mode.wallpaper:
                            mode.palette = await exp_gen_palette(
                                img=mode.wallpaper.path, light=("light" in mode.name)
                            )
            save_res = await self.save_theme(theme=theme, old_name=theme.name)
            if save_res.value:
                res.success(f'theme "{theme.name}" rewritten')
            else:
                res += save_res

        res.ok = True
        return res

    def delete_theme(self, theme_name: str) -> Result:
        res = Result()

        if theme_name not in self.themes:
            return res.error(f'theme "{theme_name}" not found')

        theme = self.themes[theme_name]

        if not str(theme.path).startswith(str(THEMES_DIR)) or theme.path == THEMES_DIR:
            return res.error(f'"{theme.path}" not in "{THEMES_DIR}"')

        shutil.rmtree(theme.path)

        if theme_name == self.config.theme:
            self.config.theme = None
        self.themes.pop(theme_name)

        res.ok = True
        return res.success(f'theme "{theme_name}" deleted')

    async def apply_theme(
        self,
        theme_name: str | None = None,
        mode_name: str | None = None,
        palette_name: str | None = None,
        styles_names: list[str] | None = None,
        include_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
        print_theme_dict: bool = False,
    ) -> Result:
        res = Result()

        if not theme_name:
            if not self.config.theme:
                return res.error("No current theme")
            theme_name = self.config.theme
        elif theme_name not in self.themes:
            return res.error(f'"{theme_name}" not found')

        if not mode_name:
            mode_name = self.config.mode

        r = tutils.gen_theme_dict(
            self,
            theme_name=theme_name,
            mode_name=mode_name,
            styles_names=styles_names,
            palette_name=palette_name,
        )
        res += r

        if not r.value:
            return res.error(
                f'error generating the theme_dict for theme "{theme_name}"'
            )

        theme_dict = r.value

        if print_theme_dict:
            pretty = rich.pretty.pretty_repr(theme_dict)
            res.info("generated theme_dict:\r\n" + pretty)

        res.info(f'applying theme "{theme_name}"...')

        modules_res = await self.mm.run_modules(
            theme_dict, include_modules, exclude_modules
        )

        res += modules_res

        self.config.theme = theme_name
        self.config.mode = mode_name
        self.save_config()

        # display_color_palette(palette.term)
        if res.errors:
            res.warning(f'theme "{theme_name}" {mode_name} applied with errors')
        else:
            res.success(f'theme "{theme_name}" {mode_name} applied')

        await self.event_handler.publish("theme_applied")

        res.ok = True
        return res

    async def set_random_theme(
        self,
        mode_name: str | None = None,
        styles_names: list[str] | None = None,
        palette_name: str | None = None,
        name_includes: str | None = None,
        include_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
        include_tags: set[str] | None = None,
        exclude_tags: set[str] | None = None,
        print_theme_dict: bool = False,
    ) -> Result:
        res = Result()

        themes_list: list[Theme] = []

        for theme in self.themes.values():
            if theme.name == self.config.theme:
                continue

            if name_includes and name_includes not in theme.name:
                continue

            if include_tags and not any(tag in include_tags for tag in theme.tags):
                continue

            if exclude_tags and any(tag in exclude_tags for tag in theme.tags):
                continue

            themes_list.append(theme)

        if len(themes_list) < 1:
            return res.error("no theme found")

        theme_name = random.choice(themes_list).name
        apply_res = await self.apply_theme(
            theme_name,
            mode_name=mode_name,
            styles_names=styles_names,
            palette_name=palette_name,
            include_modules=include_modules,
            exclude_modules=exclude_modules,
            print_theme_dict=print_theme_dict,
        )

        res += apply_res

        res.ok = True
        return res

    async def toggle_mode(self) -> Result:
        if not self.config.theme:
            return Result().error("no theme set")

        mode_name = "light" if self.config.mode == "dark" else "dark"

        return await self.apply_theme(mode_name=mode_name)

    async def set_mode(self, mode_name: str) -> Result:
        if not self.config.theme:
            return Result().error("no theme set")

        return await self.apply_theme(mode_name=mode_name)

    async def add_tags(self, themes_names: list[str], tags: set[str]) -> Result:
        res = Result()

        for theme_name in themes_names:
            if theme_name not in self.themes:
                res.error('theme "{theme_name}" not found')
                continue

            theme = self.themes[theme_name]

            for tag in tags:
                theme.tags.add(tag)
                save_res = await self.save_theme(theme, theme.name)
                res += save_res
                if not save_res.errors:
                    res.info(f'tag "{tag}" added to theme "{theme.name}"')

        res.ok = True
        return res

    async def remove_tags(self, themes_names: list[str], tags: set[str]) -> Result:
        res = Result()

        if len(themes_names) == 0:
            themes_names = list(self.themes.keys())

        for theme_name in themes_names:
            if theme_name not in self.themes:
                res.error('theme "{theme_name}" not found')
                continue

            theme = self.themes[theme_name]

            for tag in tags:
                if tag in theme.tags:
                    theme.tags.remove(tag)
                    save_res = await self.save_theme(theme, theme.name)
                    res += save_res
                    if not save_res.errors:
                        res.info(f'tag "{tag}" removed from theme "{theme.name}"')

        res.ok = True
        return res

    async def list_themes(self) -> Result:
        res = Result()

        res.info("\nNAME\t\t\tTAGS\n")
        for theme in self.themes.values():
            res.info(f"{theme.name:10}\t\t{', '.join(theme.tags)}")

        res.ok = True
        return res

    async def list_tags(self) -> Result:
        res = Result()

        res.info("\n".join(self.tags))

        res.ok = True
        return res

    async def list_palettes(self) -> Result:
        res = Result()

        for palette in self.palettes:
            res.info(f"{palette}")

        res.ok = True
        return res

    async def list_styles(self) -> Result:
        res = Result()

        for style in self.styles:
            res.info(f"{style}")

        res.ok = True
        return res

    async def export_theme(
        self,
        theme_name: str,
        out_dir: Path,
        mode_name: str | None = None,
        palette_name: str | None = None,
        styles_names: list[str] | None = None,
        include_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
        print_theme_dict: bool = False,
    ) -> Result:

        res = Result()

        if theme_name not in self.themes:
            return res.error(f'theme "{theme_name}" not found')

        if not mode_name:
            mode_name = self.config.mode

        dump_dir = out_dir / f"{theme_name}_{mode_name}"

        if dump_dir.exists():
            return res.error(f'directory "{dump_dir}" already exists')

        gen_res = tutils.gen_theme_dict(
            self,
            theme_name=theme_name,
            mode_name=mode_name,
            styles_names=styles_names,
            palette_name=palette_name,
        )
        res += gen_res

        if not gen_res.value:
            return res.error(
                f'error generating the theme_dict for theme "{theme_name}"'
            )
        theme_dict = gen_res.value

        if print_theme_dict:
            pretty = rich.pretty.pretty_repr(theme_dict)
            res.info("generated theme_dict:\r\n" + pretty)

        modules_res = await self.mm.run_modules(
            theme_dict, include_modules, exclude_modules, dump_dir
        )

        res += modules_res
        if not modules_res.value:
            return res.error(f'error exporting theme "{theme_name}"')

        theme = self.themes[theme_name]

        wp = theme.modes[mode_name].wallpaper
        if not wp:
            return res

        shutil.copy(wp.path, dump_dir)

        readme = f"""# "{theme_name}" {mode_name} theme dotfiles

Dump generated with [pimp](https://github.com/daddodev/pimpmyrice) `export theme`

## Requirements:

"""

        for module_name in modules_res.value:
            readme += f"- {module_name}\n"

        with open(dump_dir / "README.md", "w") as f:
            f.write(readme)

        res.success(f'theme "{theme_name}" exported to {dump_dir}')

        res.ok = True
        return res
