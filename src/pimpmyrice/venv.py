import venv

from pimpmyrice.config import VENV_DIR, VENV_PIP_PATH
from pimpmyrice.logger import get_logger
from pimpmyrice.module_utils import run_shell_command

log = get_logger(__name__)


def create_venv() -> None:
    log.info("creating venv")
    venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    log.success("venv created")


async def install_in_venv(packages: list[str]) -> None:
    cmd = f'{VENV_PIP_PATH} install {",".join(packages)}'
    res, err = await run_shell_command(cmd)
    print(res)
    print(err)
