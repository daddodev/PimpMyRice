import logging
from enum import Enum
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

SUCCESS_LEVEL_NUM = 25


class LogLevel(Enum):
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    SUCCESS = SUCCESS_LEVEL_NUM
    INFO = logging.INFO
    DEBUG = logging.DEBUG


class Logger(logging.Logger):
    def success(self, message: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(SUCCESS_LEVEL_NUM):
            self._log(SUCCESS_LEVEL_NUM, message, args, **kwargs)


def set_up_logging() -> None:
    logging.setLoggerClass(Logger)
    logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")
    console = Console(theme=Theme({"logging.level.success": "green"}))
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                tracebacks_show_locals=False,
                console=console,
                show_path=False,
                show_time=False,
                # level=logging.INFO,
            )
        ],
    )


def get_logger(name: str) -> Logger:
    log = logging.getLogger(name)
    return log  # type: ignore


# def to_file(msg: str) -> None:
#     with open(LOG_FILE, "a") as f:
#         f.write(msg + "\n")
#
#
# def format_msg(name: str, msg: str, level: LogLevel) -> str:
#     colors = {
#         LogLevel.ERROR: 1,
#         LogLevel.WARNING: 3,
#         LogLevel.SUCCESS: 2,
#         LogLevel.INFO: 7,
#         LogLevel.DEBUG: 6,
#     }
#
#     virtual_term = False
#     try:
#         term_size = os.get_terminal_size().columns
#     except Exception:
#         virtual_term = True
#         term_size = 80
#
#     msg_lines = [
#         f"{line:<9}" if i > 0 else line for i, line in enumerate(msg.splitlines())
#     ]
#     # origin_length = term_size - len(msg_lines[-1])
#     # if len(msg_lines) == 1:
#     #     origin_length -= 9
#     # if origin_length < len(name) + 1:
#     #     origin_length = 0
#     #     name = ""
#     msg = "\n".join(msg_lines)
#     # formatted = f"{level.name:<9}{msg}{name:>{origin_length}}"
#     formatted = f"{level.name:<9}{msg}"
#     if not virtual_term:
#         formatted = f"\033[3{colors[level]}m{formatted}\033[00m"
#
#     return formatted
