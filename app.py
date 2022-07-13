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
        urls = self.fix_redirects_and_query(self.sheets.get_urls() + [""])
        logger.debug(f'Got urls: {urls}')

        items = []
        total_added = 0
        cart_amount_old = 0
        with Parser() as parser:
            for url in urls:
                try:
                    attempts = 3
                    while attempts:
                        cart_amount = parser.add_to_cart(url)

                        if cart_amount != cart_amount_old + 1:
                            attempts -= 1
                            continue

                        cart_amount_old = cart_amount
                        break

                    if cart_amount != cart_amount_old + 1:
                        raise OutOfStockException("Item is out of stock")

                    total_added += 1
                    logger.info(f"Added! (Total: {total_added})")
                except WrongUrlException as e:
                    logger.debug(e)
                except OutOfStockException as e:
                    logger.info(e)
                    total_added += 1
                    logger.info(f"Added! (Total: {total_added})")
                    items.append(Item(id=parser.get_item_id_from_url(url), status=Status.OUT_OF_STOCK))

            items += parser.get_cart()

        logger.info("Done parsing!")
        return items

    def fix_redirects_and_query(self, urls: List[str]) -> List[str]:
        logger.info("Fixing redirects...")
        with Parser() as parser:
            for index, old_url in enumerate(urls):
                if not old_url:
                    continue

                logger.debug(f"Checking \"{old_url}\"...")
                urls[index] = parser.remove_query_from_url(urls[index])
                redirect = parser.get_redirect(urls[index])

                if redirect != urls[index]:
                    urls[index] = parser.remove_query_from_url(redirect)

                if old_url != urls[index]:
                    self.sheets.replace_url(old_url, urls[index])

        return urls

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
