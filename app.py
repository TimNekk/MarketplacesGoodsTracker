from time import sleep
from typing import List

import schedule
from oauth2client.service_account import ServiceAccountCredentials

from config import CREDENTIAL
from parsing import Parser
from sheets import Sheets


class App:
    def __init__(self, credentials: ServiceAccountCredentials):
        self.sheets = Sheets(credentials)
        self.parser = Parser(True)

    def get_quantities(self) -> List[int]:
        urls = self.sheets.get_urls()
        quantities = []

        for url in urls:
            quantity = -1
            try:
                quantity = self.parser.get_quantity(url)
            except Exception as e:
                print(e)
            quantities.append(quantity)

        return quantities

    def update(self):
        try:
            quantities = self.get_quantities()
            self.sheets.set_quantities(quantities)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    app = App(CREDENTIAL)
    app.update()

    schedule.every(3).hours.do(app.update)
    while True:
        schedule.run_pending()
        sleep(10)
