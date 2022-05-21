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
    def __init__(self, credentials: ServiceAccountCredentials, hide_driver=True, max_parsing_attempts=3):
        self.sheets = Sheets(credentials)
        self.parser = Parser(hide_driver)
        self.max_parsing_attempts = max_parsing_attempts

    def get_items(self) -> List[Item]:
        urls = self.sheets.get_urls()
        items = []

        for url in urls:
            print(f"\nParsing {url}...")

            item = Item()
            attempt = 0

            while attempt != self.max_parsing_attempts:
                print(f"Attempt #{attempt + 1}")

                try:
                    quantity, price = self.parser.get_quantity_and_price(url)
                    item = Item(quantity, price, Status.OK)
                    print(item)
                    break
                except WrongUrlException as e:
                    print(e)
                    item.status = Status.WRONG_URL
                    break
                except OutOfStockException as e:
                    print(e)
                    item.status = Status.OUT_OF_STOCK
                    break
                except Exception as e:
                    print(e)
                    item.status = Status.PARSING_ERROR

                attempt += 1

            items.append(item)

        print("\nDone parsing\n")
        return items

    def update(self):
        try:
            items = self.get_items()
            self.sheets.set_items(items)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    app = App(CREDENTIAL, False)

    app.update()

    schedule.every().day.do(app.update)
    while True:
        schedule.run_pending()
        sleep(1)
