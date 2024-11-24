import asyncio

from pimpmyrice.cli import cli
from pimpmyrice.logger import get_logger

log = get_logger(__name__)


def main() -> None:
    try:
        asyncio.run(cli())
    except KeyboardInterrupt:
        log.info("stopped")


if __name__ == "__main__":
    main()
    # import yappi
    #
    # with yappi.run():
    #     main()
    #
    # stats = yappi.get_func_stats()
    # stats.print_all()
    # stats.save("cr.prof", type="callgrind")

    # import cProfile
    #
    # cProfile.run("main()", sort="cumtime")

    # print("profiled")
