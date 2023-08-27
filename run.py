from argparse import ArgumentParser, Namespace
from time import sleep

import schedule

from src.config import CREDENTIAL
from src.parsing.ozon import test_run
from src.utils import logger
from src import App


def parse_args() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument("-u", "--update-after-launch",
                        help="Updates immediately, ignoring schedule",
                        action="store_true")
    parser.add_argument("-b", "--binary",
                        help="Path to chrome binary",
                        type=str,
                        default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    parser.add_argument("-t", "--start-time",
                        help="Time to start updating",
                        type=str,
                        default="05:00")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    app = App(CREDENTIAL, args.binary)
    logger.debug("App initialized")

    schedule.every().day.at(args.start_time).do(app.update)

    if args.update_after_launch:
        app.update()

    while True:
        schedule.run_pending()
        sleep(1)


if __name__ == "__main__":
    try:
        # test_run()
        main()
    except KeyboardInterrupt:
        logger.info("Stopped by KeyboardInterrupt")
