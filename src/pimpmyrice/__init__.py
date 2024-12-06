import os
import pkgutil
from importlib.metadata import version

from pimpmyrice.files import check_config_dirs
from pimpmyrice.logger import set_up_logging

__all__ = [name for _, name, _ in pkgutil.iter_modules([os.path.dirname(__file__)])]
for module in __all__:
    __import__(f"{__name__}.{module}")

__version__ = version("pimpmyrice")

set_up_logging()
