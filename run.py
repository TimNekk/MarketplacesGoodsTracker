from argparse import ArgumentParser, Namespace
from time import sleep

import schedule

from src import App
from src.config import CREDENTIAL
from src.models import OZON, WILDBERRIES
from src.utils import logger
from src.utils.logger import initialize_file_logger


def parse_args() -> Namespace:
    parser = ArgumentParser()

    parser.add_argument("-oz", "--ozon",
                        help="Parse Ozon",
                        action="store_true")
    parser.add_argument("-wb", "--wildberries",
                        help="Parse Wildberries",
                        action="store_true")
    parser.add_argument("-u", "--update-immediately",
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

    if args.ozon:
        marketplace = OZON
    elif args.wildberries:
        marketplace = WILDBERRIES
    else:
        logger.warning("No marketplace specified. Use -h for help")
        return
    initialize_file_logger(marketplace.name)

    app = App(CREDENTIAL, marketplace, args.binary)
    logger.debug("App initialized")

    schedule.every().day.at(args.start_time).do(app.update)

    if args.update_immediately:
        app.update()

    while True:
        schedule.run_pending()
        sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Stopped by KeyboardInterrupt")
