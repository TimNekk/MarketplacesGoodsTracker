import sys
from time import sleep
from typing import List

import schedule
from oauth2client.service_account import ServiceAccountCredentials

from config import CREDENTIAL
from item import Item
from logger import logger
from status import Status
from parsing import Parser, OutOfStockException, WrongUrlException
from sheets import Sheets


class App:
    def __init__(self, credentials: ServiceAccountCredentials):
        self.sheets = Sheets(credentials)

    def get_items(self) -> List[Item]:
        urls = self.sheets.get_urls() + [""]
        items = []
        total_added = 0

        while True:
            with Parser() as parser:
                for url in urls:
                    try:
                        parser.add_to_cart(url)
                        total_added += 1
                        logger.info(f"Added! (Total: {total_added})")
                    except WrongUrlException as e:
                        logger.exception(e)
                    except OutOfStockException as e:
                        logger.exception(e)
                        items.append(Item(id=parser.get_item_id_from_url(url), status=Status.OUT_OF_STOCK))

                cart = parser.get_cart()
                if len(cart) == total_added:
                    items += cart
                    break

        logger.info("Done parsing!")
        return items

    def update(self):
        try:
            logger.info("Getting items...")
            while True:
                try:
                    items = self.get_items()
                    logger.debug("\n".join(map(str, items)))
                    break
                except Exception as e:
                    logger.exception(e)

            logger.info("Exporting...\n")
            while True:
                try:
                    self.sheets.set_items(items)
                    break
                except Exception as e:
                    logger.exception(e)
                    sleep(60)

            logger.info("Done exporting!")
        except Exception as e:
            logger.exception(e)


if __name__ == "__main__":
    args = sys.argv[1:]
    logger.debug(f"App started with args: {args}")

    app = App(CREDENTIAL)
    logger.debug("App initialized")

    if len(args) < 1 or args[0] != "0":
        app.update()

    schedule.every().day.at("07:00").do(app.update)
    while True:
        schedule.run_pending()
        sleep(1)
