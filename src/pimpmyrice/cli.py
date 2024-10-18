"""
Usage:
    rice gen IMAGE... [options] [--apply]
    rice random [options]
    rice refresh [options]
    rice (set|delete) theme THEME [options]
    rice rename theme THEME NEW_NAME [options]
    rice set mode MODE [options]
    rice toggle mode [options]
    rice (clone|delete) module MODULE [options]
    rice run module MODULE COMMAND [COMMAND_ARGS...] [options]
    rice list (themes|styles|palettes|keywords|modules) [options]
    rice edit theme THEME [options]
    rice edit style STYLE [options]
    rice edit palette PALETTE [options]
    rice edit keywords [options]
    rice edit module MODULE [options]
    rice regen [options]
    rice rewrite [options]
    rice server [options]
    rice info [options]

Options:
    --album -a ALBUM
    --mode -m MODE
    --name -n NAME
    --palette -p PALETTE
    --style -s STYLE
    --use_modules -u MODULES
    --exclude_modules -e MODULES
    --print-theme-dict -d
    --backend -b BACKEND
    --verbose -v

See https://pimpmyrice.vercel.app/docs for more info.
"""

import logging

from docopt import DocoptExit, docopt  # type:ignore

from .args import process_args, process_edit_args
from .config import SERVER_PID_FILE
from .files import check_config_dirs
from .logger import get_logger
from .server import run_server, send_to_server
from .theme import ThemeManager
from .utils import is_locked

log = get_logger(__name__)


async def cli() -> None:
    check_config_dirs()

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

    server_running = is_locked(SERVER_PID_FILE)

    if args["server"]:
        if server_running:
            log.error("server already running")
        else:
            await run_server()
        return

    if server_running:
        send_to_server(args)
    else:
        await process_args(ThemeManager(), args)
