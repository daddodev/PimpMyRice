"""
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
    pimp list (themes|styles|palettes|keywords|modules) [options]
    pimp edit theme THEME [options]
    pimp edit style STYLE [options]
    pimp edit palette PALETTE [options]
    pimp edit keywords [options]
    pimp edit module MODULE [options]
    pimp regen [options]
    pimp rewrite [options]
    pimp (start|stop|reload) server [options]
    pimp info [options]

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
import os
import signal

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

    server_running, server_pid = is_locked(SERVER_PID_FILE)

    if args["server"]:
        if args["start"]:
            if server_running:
                log.error("server already running")
            else:
                await run_server()
            return
        elif args["stop"]:
            if server_running:
                os.kill(server_pid, signal.SIGTERM)
                log.info("server stopped")
            else:
                log.error("server not running")
            return
        elif args["reload"]:
            if not server_running:
                log.error("server not running")
                return

    if server_running:
        send_to_server(args)
    else:
        await process_args(ThemeManager(), args)
