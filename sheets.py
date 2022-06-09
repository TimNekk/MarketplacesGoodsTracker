from datetime import datetime
from typing import List

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from item import Item
from status import Status


class Sheets:
    def __init__(self, credentials: ServiceAccountCredentials, workbook_name="OZON Трекер количества"):
        self.client = gspread.authorize(credentials)
        self.workbook = self.client.open(workbook_name)

        self.sheet = self.workbook.sheet1

    def _get_top_offset(self) -> int:
        return self.sheet.col_values(1).index("Ссылка")

    def get_urls(self) -> List[str]:
        return self.sheet.col_values(1)[(self._get_top_offset() + 1):]

    def set_items(self, items: List[Item]):
        offset = self._get_top_offset()
        quantities, prices = [""] * offset + [datetime.now().strftime("%d/%m")], [""] * offset

        urls = self.get_urls()
        for url in urls:
            added = False

            for item in items:
                if item.id not in url:
                    continue

                if item.status == Status.OK:
                    quantities.append(item.quantity)
                    prices.append(item.price)
                else:
                    quantities.append(item.status.value)
                    prices.append("")
                added = True
                break

            if not added:
                quantities.append("")
                prices.append("")

        self.sheet.insert_cols([quantities, prices], col=3)
        self.sheet.merge_cells("C1:D1")
