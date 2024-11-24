"""
See https://pimpmyrice.vercel.app/docs for more info.

Usage:
    pimp gen IMAGE...       [--apply] [--name=NAME] [--tags=TAGS] [--style=STYLE]
                            [--palette=PALETTE] [options]
    pimp random             [--mode=MODE] [--name=NAME] [--tags=TAGS]
                            [--exclude-tags=TAGS] [--include-modules=MODULES]
                            [--exclude-modules=MODULES] [--style=STYLE]
                            [--palette=PALETTE] [--print-theme-dict]
                            [options]
    pimp refresh            [--mode=MODE] [--include-modules=MODULES]
                            [--exclude-modules=MODULES] [--style=STYLE]
                            [--palette=PALETTE] [--print-theme-dict]
                            [options]
    pimp set theme THEME    [--mode=MODE] [--include-modules=MODULES]
                            [--exclude-modules=MODULES] [--style=STYLE]
                            [--palette=PALETTE] [--print-theme-dict]
                            [options]
    pimp set mode MODE [options]
    pimp delete theme THEME [options]
    pimp rename theme THEME NEW_NAME [options]
    pimp toggle mode [options]
    pimp clone module MODULE_URL [options]
    pimp delete module MODULE [options]
    pimp run module MODULE COMMAND [COMMAND_ARGS...] [options]
    pimp list (themes|tags|styles|palettes|keywords|modules) [options]
    pimp edit theme [THEME] [options]
    pimp edit style STYLE [options]
    pimp edit palette PALETTE [options]
    pimp edit keywords [options]
    pimp edit module MODULE [options]
    pimp regen [--name=NAME] [options]
    pimp rewrite [--name=NAME] [options]
    pimp info [options]
    pimp --help

Options:
    --verbose, -v

"""

import logging

from docopt import DocoptExit, docopt

from pimpmyrice.args import process_args, process_edit_args
from pimpmyrice.config import SERVER_PID_FILE
from pimpmyrice.logger import get_logger
from pimpmyrice.theme import ThemeManager
from pimpmyrice.utils import is_locked

log = get_logger(__name__)


async def cli() -> None:
    try:
        args = docopt(__doc__)
    except DocoptExit:
        print(__doc__)
        return

    if args["--verbose"]:
        logging.getLogger().setLevel(logging.DEBUG)

    if args["edit"]:
        await process_edit_args(args)
        return

    server_running, server_pid = is_locked(SERVER_PID_FILE)

    if server_running:
        from pimpmyrice_server.api import send_to_server

        send_to_server(args)
    else:
        tm = ThemeManager()
        await process_args(tm, args)
