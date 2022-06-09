from time import sleep
from typing import List

import schedule
from oauth2client.service_account import ServiceAccountCredentials

from config import CREDENTIAL
from item import Item
from status import Status
from parsing import Parser, OutOfStockException, WrongUrlException
from sheets import Sheets


class App:
    def __init__(self, credentials: ServiceAccountCredentials):
        self.sheets = Sheets(credentials)

    def get_items(self) -> List[Item]:
        urls = self.sheets.get_urls() + [""]
        items = []

        with Parser() as parser:
            for url in urls:
                print(f"\nAdding to cart: {url}...")

                try:
                    parser.add_to_cart(url)
                    print("Added!")
                except WrongUrlException as e:
                    print(e)
                except OutOfStockException as e:
                    print(e)
                    items.append(Item(id=parser.get_item_id_from_url(url), status=Status.OUT_OF_STOCK))

            cart = parser.get_cart()
            items += cart

        print("\nDone parsing!\n")
        return items

    def update(self):
        try:
            items = self.get_items()
            print(items)

            while True:
                try:
                    self.sheets.set_items(items)
                    break
                except Exception:
                    sleep(60)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    app = App(CREDENTIAL)

    app.update()

    schedule.every().day.do(app.update)
    while True:
        schedule.run_pending()
        sleep(1)
