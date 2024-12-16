import json
import logging
from pathlib import Path
from typing import Any

from docopt import DocoptExit, docopt

from pimpmyrice.config import SERVER_PID_FILE
from pimpmyrice.doc import __doc__ as cli_doc
from pimpmyrice.edit_args import process_edit_args
from pimpmyrice.logger import LogLevel, get_logger
from pimpmyrice.utils import is_locked

log = get_logger(__name__)


def send_to_server(
    args: dict[str, Any], address: str = "http://127.0.0.1:5000"
) -> None:
    import requests

    if "IMAGE" in args and args["IMAGE"]:
        args["IMAGE"] = [
            (
                img
                if img.startswith(("http://", "https://"))
                else str(Path(img).absolute())
            )
            for img in args["IMAGE"]
        ]

    if args["OUT_DIR"]:
        args["OUT_DIR"] = str(Path(args["OUT_DIR"]).absolute())

    log.debug(f"connecting to {address}")

    try:
        with requests.post(
            f"{address}/v1/cli_command", json=args, stream=True
        ) as response:
            if response.status_code == 200:
                for chunk in response.iter_lines():
                    parsed = json.loads(chunk)["data"]
                    try:
                        log.log(LogLevel[parsed["level"]].value, parsed["msg"])
                    except Exception as e:
                        log.exception(e)

        # res_json = json.loads(response.json())
        #
        # for record in res_json["result"]["records"]:
        #     log.log(LogLevel[record["level"]].value, record["msg"])

    except Exception as e:
        log.exception(e)
    finally:
        log.debug("closing connection")


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
        send_to_server(args)
    else:
        from pimpmyrice.args import process_args
        from pimpmyrice.theme import ThemeManager

        tm = ThemeManager()
        await process_args(tm, args)
