import random
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import rich

from . import theme_utils as tutils
from .colors import Palette, exp_gen_palette, get_palettes
from .config import BASE_STYLE_FILE, CONFIG_FILE, STYLES_DIR, THEMES_DIR
from .files import download_file, load_json, save_json
from .logger import get_logger
from .module import ModuleManager
from .parsers import parse_theme
from .theme_utils import Mode, Style, Theme, ThemeConfig
from .utils import Result, Timer

log = get_logger(__name__)


class ThemeManager:
    def __init__(self) -> None:
        self.base_style = self.get_base_style()
        self.styles = self.get_styles()
        self.palettes = self.get_palettes()
        self.albums = self.get_albums()
        self.config = self.get_config()
        self.mm = ModuleManager()

    def get_config(self) -> ThemeConfig:
        config = ThemeConfig(**load_json(CONFIG_FILE))
        if config.album not in self.albums:
            config.album = "default"
        if config.theme not in self.albums[config.album]:
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

    @staticmethod
    def get_styles() -> dict[str, Style]:
        styles: dict[str, Style] = {
            f.stem: Style(name=f.stem, path=f, keywords=load_json(f))
            for f in STYLES_DIR.iterdir()
        }
        return styles

    @staticmethod
    def get_palettes() -> dict[str, Palette]:
        return get_palettes()

    def get_albums(self) -> dict[str, dict[str, Theme]]:
        timer = Timer()

        albums = {
            folder.name: self.get_themes(folder) for folder in THEMES_DIR.iterdir()
        }

        themes_n = 0
        for a in albums:
            themes_n += len(albums[a])

        log.debug(f"{themes_n} themes loaded in {timer.elapsed():.4f} sec")

        return albums

    def get_themes(self, path: Path) -> dict[str, Theme]:
        themes = {
            folder.name: parse_theme(folder.name, path, self.styles, self.palettes)
            for folder in path.iterdir()
            if (folder / "theme.json").exists()
        }
        return themes

    async def generate_theme(
        self,
        image: str,
        name: str | None = None,
        album: str | None = None,
        backend: str = "pimp",
        apply: bool = False,
    ) -> Result:
        res = Result()

        if image.startswith(("http://", "https://")):
            download_res = download_file(image)
            if download_res.value is None:
                res += download_res
                return res.error("could not download file")
            file = download_res.value
        else:
            file = Path(image)

        if not album:
            album = "default"
        elif album not in self.albums:
            return res.error(f'album "{album}" not found')

        gen_res = await tutils.gen_from_img(
            image=file, name=name, album=self.albums[album], backend=backend
        )
        res += gen_res
        if not gen_res.value:
            return res.error("could not generate theme")

        # TODO generate name here
        save_res = await self.save_theme(gen_res.value, album=album)
        res += save_res
        if save_res.value:
            res.success(f'theme "{save_res.value}" generated')
        else:
            return res.error("could not generate theme")

        if apply:
            apply_res = await self.apply_theme(save_res.value, album=album)
            res += apply_res

        return res

    async def rename_theme(
        self,
        theme_name: str,
        new_name: str,
        album: str | None = None,
    ) -> Result:
        res = Result()

        if not album:
            album = "default"
        elif album not in self.albums:
            return res.error(f'album "{album}" not found')

        if theme_name not in self.albums[album]:
            return res.error(f'theme "{theme_name}" not found in album "{album}"')

        theme = self.albums[album][theme_name]
        old_name = theme.name
        theme.name = new_name

        save_res = await self.save_theme(theme, album, old_name)
        res += save_res

        if not save_res.value:
            return res.error(f'failed renaming theme "{theme_name}" in album "{album}"')
        return res.success(
            f'renamed theme "{theme_name}" to "{new_name}" in album "{album}"'
        )

    async def save_theme(
        self,
        theme: Theme,
        album: str | None = None,
        old_name: str | None = None,
    ) -> Result[str]:
        res: Result[str] = Result()

        if not album:
            album = "default"
        elif album not in self.albums:
            return res.error(f'album "{album}" not found')

        if not old_name:
            theme.name = tutils.valid_theme_name(
                name=theme.name, album=self.albums[album]
            )
            theme_dir = THEMES_DIR / album / theme.name
            theme_dir.mkdir()

        elif old_name != theme.name:
            theme.name = tutils.valid_theme_name(
                name=theme.name, album=self.albums[album]
            )
            theme_dir = THEMES_DIR / album / theme.name
            (THEMES_DIR / album / old_name).rename(theme_dir)
        else:
            theme_dir = THEMES_DIR / album / theme.name

        # NOTE full path update on rename is handled by dump_theme
        #      as it leaves only the filename
        theme.wallpaper._path = tutils.import_image(theme.wallpaper._path, theme_dir)
        for mode in theme.modes.values():
            mode.wallpaper._path = tutils.import_image(mode.wallpaper._path, theme_dir)

        dump = tutils.dump_theme(theme)
        save_json(theme_dir / "theme.json", dump)

        parsed_theme = parse_theme(
            theme.name,
            path=THEMES_DIR / album,
            global_styles=self.styles,
            global_palettes=self.palettes,
        )

        self.albums[album][theme.name] = parsed_theme

        if old_name and old_name != theme.name:
            self.albums[album].pop(old_name)

            if self.config.theme == old_name:
                self.config.theme = theme.name

        res.value = theme.name
        return res

    async def rewrite_themes(
        self,
        regen_colors: bool = False,
        album: str | None = None,
        name_includes: str | None = None,
    ) -> Result:
        # TODO refactor
        res = Result()

        if not album:
            albums = self.albums
        elif album not in self.albums:
            return res.error(f'album "{album}" not found')
        else:
            albums = {album: self.albums[album]}

        for album_name, themes in albums.items():
            for theme_name, theme in themes.items():
                try:
                    if name_includes and name_includes not in theme_name:
                        continue
                    if regen_colors:
                        for k in ["light", "dark"]:
                            if k not in theme.modes:
                                theme.modes[k] = Mode(
                                    name=k,
                                    wallpaper=theme.wallpaper,
                                    palette=Palette(),
                                )
                        for mode in theme.modes.values():
                            mode.palette = await exp_gen_palette(
                                img=mode.wallpaper._path, light=("light" in mode.name)
                            )
                    save_res = await self.save_theme(
                        theme=theme, album=album_name, old_name=theme_name
                    )
                    if save_res.value:
                        res.success(
                            f'theme "{theme_name}" in album "{album_name}" rewritten'
                        )
                    else:
                        res += save_res
                except Exception as e:
                    res.exception(
                        e,
                        f'failed to rewrite theme "{theme_name}"',
                    )
                    continue
        return res

    def delete_theme(self, theme_name: str, album: str | None = None) -> Result:
        res = Result()

        if not album:
            album = "default"
        elif album not in self.albums:
            return res.error(f'album "{album}" not found')

        if theme_name not in self.albums[album]:
            return res.error(f'theme "{theme_name}" not found in album "{album}"')

        theme = self.albums[album][theme_name]

        if theme.path.parent.parent != THEMES_DIR:
            return res.error(f'"{theme.path}" not in "{THEMES_DIR}"')

        shutil.rmtree(theme.path)

        if theme_name == self.config.theme:
            self.config.theme = None
        self.albums[album].pop(theme_name)

        return res.success(f'theme "{theme_name}" deleted')

    async def apply_theme(
        self,
        theme_name: str | None = None,
        mode_name: str | None = None,
        styles_names: str | None = None,
        palette_name: str | None = None,
        album: str | None = None,
        use_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
        print_theme_dict: bool = False,
    ) -> Result:
        res = Result()

        try:
            if not album:
                album = "default"
            elif album not in self.albums:
                return res.error(f'album "{album}" not found')

            if not theme_name:
                if not self.config.theme:
                    return res.error("No current theme")
                theme_name = self.config.theme
                album = self.config.album
            elif theme_name not in self.albums[album]:
                return res.error(f'"{theme_name}" not found')

            if not mode_name:
                mode_name = self.config.mode

            theme: Theme = deepcopy(self.albums[album][theme_name])

            if mode_name not in theme.modes:
                new_mode = [*theme.modes.keys()][0]
                res.warning(
                    f'"{mode_name}" mode not present in theme, applying "{new_mode}"'
                )
                mode_name = new_mode

            styles = []
            if theme.style:
                styles.append(theme.style)
            if mode_style := theme.modes[mode_name].style:
                styles.append(mode_style)
            if styles_names:
                for style in styles_names.split(","):
                    if style not in self.styles:
                        return res.error(f'style "{style}" not found')
                    styles.append(self.styles[style])

            if palette_name:
                if palette_name in self.palettes:
                    palette = self.palettes[palette_name]
                else:
                    return res.error(f'palette "{palette_name}" not found')
            else:
                palette = theme.modes[mode_name].palette

            theme_dict = tutils.gen_theme_dict(
                theme=theme,
                base_style=self.base_style,
                mode_name=mode_name,
                styles=styles,
                palette=palette,
            )

            if print_theme_dict:
                pretty = rich.pretty.pretty_repr(theme_dict)
                res.info("generated theme_dict:\r\n" + pretty)

            res.info(f'applying theme "{theme.name}"...')

            modules_res = await self.mm.run(theme_dict, use_modules, exclude_modules)

            res += modules_res

            self.config.theme = theme_name
            self.config.album = album
            self.config.mode = mode_name
            self.save_config()

            # display_color_palette(palette.term)
            if res.errors:
                res.warning(f'theme "{theme_name}" {mode_name} applied with errors')
            else:
                res.success(f'theme "{theme_name}" {mode_name} applied')
        except Exception as e:
            res.exception(e, f'error applying theme "{theme_name}"')
        finally:
            return res

    async def set_random_theme(
        self,
        mode_name: str | None = None,
        styles_names: str | None = None,
        palette_name: str | None = None,
        album: str | None = None,
        theme_name_includes: str | None = None,
        use_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
        print_theme_dict: bool = False,
    ) -> Result:
        res = Result()

        if not album:
            album = "default"
        elif album not in self.albums:
            return res.error(f'album "{album}" not found')

        themes_list = [k for k in self.albums[album].keys()]
        if len(themes_list) < 1:
            return res.error(f'no theme found in album "{album}"')

        if theme_name_includes:
            themes_list = [t for t in themes_list if theme_name_includes in t]
            if len(themes_list) < 1:
                return res.error(
                    f'no theme found with name including "{theme_name_includes}"'
                )

        current = self.config.theme
        if current in themes_list and len(themes_list) > 1:
            themes_list.remove(current)

        theme = random.choice(themes_list)
        apply_res = await self.apply_theme(
            theme,
            album=album,
            mode_name=mode_name,
            styles_names=styles_names,
            palette_name=palette_name,
            use_modules=use_modules,
            exclude_modules=exclude_modules,
            print_theme_dict=print_theme_dict,
        )

        res += apply_res

        return res

    async def toggle_mode(self) -> Result:
        if not self.config.theme:
            return Result().error("no theme set")

        mode_name = "light" if self.config.mode == "dark" else "dark"

        return await self.apply_theme(mode_name=mode_name, album=self.config.album)

    async def set_mode(self, mode_name: str) -> Result:
        if not self.config.theme:
            return Result().error("no theme set")

        return await self.apply_theme(mode_name=mode_name, album=self.config.album)

    async def list_themes(
        self,
        # album: str | None = None,
    ) -> Result:
        res = Result()

        for album_name, themes in self.albums.items():
            res.info(f"{album_name}:")
            for theme_name in themes:
                res.info(f"    {theme_name}")

        return res

    async def list_palettes(
        self,
    ) -> Result:
        res = Result()

        for palette in self.palettes:
            res.info(f"{palette}")

        return res

    async def list_styles(
        self,
    ) -> Result:
        res = Result()

        for style in self.styles:
            res.info(f"{style}")

        return res
