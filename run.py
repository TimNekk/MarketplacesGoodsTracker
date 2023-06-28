from argparse import ArgumentParser, Namespace
from time import sleep

import schedule

from src.config import CREDENTIAL
from src.utils import logger
from src import App


def parse_args() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument("-u", "--update-after-launch",
                        help="Updates immediately, ignoring schedule",
                        action="store_true")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    app = App(CREDENTIAL)
    logger.debug("App initialized")

    schedule.every().day.at("07:00").do(app.update)

    if args.update_after_launch:
        app.update()

    while True:
        schedule.run_pending()
        sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Stopped by KeyboardInterrupt")
