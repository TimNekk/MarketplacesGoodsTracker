from time import sleep
from typing import List

import schedule
from oauth2client.service_account import ServiceAccountCredentials

from config import CREDENTIAL
from errors import Error
from parsing import Parser, OutOfStockException, WrongUrlException
from sheets import Sheets


class App:
    def __init__(self, credentials: ServiceAccountCredentials, hide_driver=True, max_parsing_attempts=3):
        self.sheets = Sheets(credentials)
        self.parser = Parser(hide_driver)
        self.max_parsing_attempts = max_parsing_attempts

    def get_quantities(self) -> List[int]:
        urls = self.sheets.get_urls()
        quantities = []

        for url in urls:
            print(f"\nParsing {url}...")

            quantity = 0
            attempt = 0

            while attempt != self.max_parsing_attempts:
                print(f"Attempt #{attempt + 1}")

                try:
                    quantity = self.parser.get_quantity(url)
                    print(f"Quantity: {quantity}")
                    break
                except WrongUrlException as e:
                    print(e)
                    quantity = Error.WRONG_URL
                    break
                except OutOfStockException as e:
                    print(e)
                    quantity = Error.OUT_OF_STOCK
                    break
                except Exception as e:
                    print(e)
                    quantity = Error.PARSING_ERROR

                attempt += 1

            quantities.append(quantity)

        print("\nDone parsing\n")
        return quantities

    def update(self):
        try:
            quantities = self.get_quantities()
            self.sheets.set_quantities(quantities)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    app = App(CREDENTIAL, False)
    app.update()

    schedule.every().day.do(app.update)
    while True:
        schedule.run_pending()
        sleep(1)
