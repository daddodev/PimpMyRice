"""
See https://pimpmyrice.vercel.app/docs for more info.

Usage:
    pimp gen IMAGE... [options] [--apply]
    pimp random [options]
    pimp refresh [options]
    pimp (set|delete) theme THEME [options]
    pimp rename theme THEME NEW_NAME [options]
    pimp set mode MODE [options]
    pimp toggle mode [options]
    pimp (clone|delete) module MODULE [options]
    pimp run module MODULE COMMAND [COMMAND_ARGS...] [options]
    pimp list (themes|tags|styles|palettes|keywords|modules) [options]
    pimp edit theme THEME [options]
    pimp edit style STYLE [options]
    pimp edit palette PALETTE [options]
    pimp edit keywords [options]
    pimp edit module MODULE [options]
    pimp regen [options]
    pimp rewrite [options]
    pimp info [options]

Options:
    --tags -t TAGS
    --exclude-tags TAGS
    --mode -m MODE
    --name -n NAME
    --palette -p PALETTE
    --style -s STYLE
    --include-modules MODULES
    --exclude-modules MODULES
    --print-theme-dict
    --verbose -v
"""

import logging

from docopt import DocoptExit, docopt  # type:ignore

from .args import process_args, process_edit_args
from .config import SERVER_PID_FILE
from .logger import get_logger
from .theme import ThemeManager
from .utils import is_locked

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
        await process_args(ThemeManager(), args)
