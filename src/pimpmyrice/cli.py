import logging

from docopt import DocoptExit, docopt

from pimpmyrice.args import process_args, process_edit_args
from pimpmyrice.config import SERVER_PID_FILE
from pimpmyrice.doc import __doc__ as cli_doc
from pimpmyrice.logger import get_logger
from pimpmyrice.theme import ThemeManager
from pimpmyrice.utils import is_locked

log = get_logger(__name__)


async def cli() -> None:
    try:
        args = docopt(cli_doc)
    except DocoptExit:
        print(cli_doc)
        return

    if args["--verbose"]:
        logging.getLogger().setLevel(logging.DEBUG)

    if args["edit"]:
        await process_edit_args(args)
        return

    server_running, server_pid = is_locked(SERVER_PID_FILE)

    if server_running:
        try:
            from pimpmyrice_server.api import send_to_server
        except ImportError:
            log.error("PimpMyRice server is not installed")
            log.error("https://github.com/daddodev/pimpmyrice_server#install")
            return

        send_to_server(args)
    else:
        tm = ThemeManager()
        await process_args(tm, args)
