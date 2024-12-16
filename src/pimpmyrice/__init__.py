import os
import pkgutil
from importlib.metadata import version

from pimpmyrice.files import check_config_dirs
from pimpmyrice.logger import set_up_logging

__version__ = version("pimpmyrice")

set_up_logging()
