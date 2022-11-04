from argparse import ArgumentParser, BooleanOptionalAction
from time import sleep

import schedule

from app.config import CREDENTIAL
from app.utils import logger
from app import App


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-u", "--update-after-launch",
                        help="Updates immediately, ignoring schedule",
                        action="store_true")
    parser.add_argument('--fix-redirects',
                        help='Enables redirects fixing',
                        action=BooleanOptionalAction,
                        default=True)
    args = parser.parse_args()

    app = App(CREDENTIAL)
    logger.debug("App initialized")

    schedule.every().day.at("07:00").do(app.update, args.fix_redirects)

    if args.update_after_launch:
        app.update(args.fix_redirects)

    while True:
        schedule.run_pending()
        sleep(1)
