import os
import sys
from enum import Enum
from pathlib import Path


class Os(str, Enum):
    LINUX = "linux"
    WINDOWS = "windows"
    MAC = "mac"

    def __str__(self) -> str:
        return self.value


if os.environ.get("PIMP_TESTING"):
    HOME_DIR = Path("./tests/files/")
else:
    HOME_DIR = Path.home()

match sys.platform:
    case "win32":
        CLIENT_OS = Os.WINDOWS
        CONFIG_DIR = HOME_DIR / "AppData/Roaming"
        PIMP_CONFIG_DIR = HOME_DIR / "pimpmyrice"
    case "linux":
        CLIENT_OS = Os.LINUX
        CONFIG_DIR = HOME_DIR / ".config"
        PIMP_CONFIG_DIR = CONFIG_DIR / "pimpmyrice"
    case "darwin":
        CLIENT_OS = Os.MAC
        CONFIG_DIR = HOME_DIR / "Library/Application Support"
        PIMP_CONFIG_DIR = HOME_DIR / "pimpmyrice"


PIMP_DIR = Path(os.path.abspath(os.path.join(__file__, "../../")))
VENV_DIR = PIMP_CONFIG_DIR / "venv"

if CLIENT_OS == Os.WINDOWS:
    VENV_PIP_PATH = VENV_DIR / "bin" / "pip.exe"
else:
    VENV_PIP_PATH = VENV_DIR / "bin" / "pip"

LOCAL_DIR = HOME_DIR / ".local/share"
CONFIG_FILE = PIMP_CONFIG_DIR / "config.json"
BASE_STYLE_FILE = PIMP_CONFIG_DIR / "base_style.json"
THEMES_DIR = PIMP_CONFIG_DIR / "themes"
STYLES_DIR = PIMP_CONFIG_DIR / "styles"
PALETTES_DIR = PIMP_CONFIG_DIR / "palettes"
MODULES_DIR = PIMP_CONFIG_DIR / "modules"
TEMP_DIR = PIMP_CONFIG_DIR / ".tmp/"
LOCK_FILE = TEMP_DIR / "pimpmyrice.lock"
CORE_PID_FILE = TEMP_DIR / "core.pid"
SERVER_PID_FILE = TEMP_DIR / "server.pid"
LOG_FILE = PIMP_CONFIG_DIR / "pimpmyrice.log"
REPOS_LIST = PIMP_CONFIG_DIR / "remote_repos" / "list.txt"
JSON_SCHEMA_DIR = PIMP_CONFIG_DIR / ".json_schemas"

REPOS_BASE_ADDR = "https://github.com/pimpmyrice-modules"
