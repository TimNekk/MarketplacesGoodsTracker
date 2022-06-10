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
        quantities, prices = [""] * offset + [datetime.now().strftime("%d/%m")], [""] * (offset + 1)

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
        self.add_border(f"C1:D{len(urls) + 1}")
        self.sheet.merge_cells("C1:D1")

    def add_border(self, cells_range: str) -> None:
        first, second = cells_range.split(":")
        left, top, right, bottom = first[0], first[1:], second[0], second[1:]
        border = {"style": "SOLID"}

        # Edges
        self.sheet.format(f"{left}{top}:{right}{top}", {"borders": {"top": border}})
        self.sheet.format(f"{left}{top}:{left}{bottom}", {"borders": {"left": border}})
        self.sheet.format(f"{left}{bottom}:{right}{bottom}", {"borders": {"bottom": border}})
        self.sheet.format(f"{right}{top}:{right}{bottom}", {"borders": {"right": border}})

        # Corners
        self.sheet.format(left + top, {"borders": {"left": border, "top": border}})
        self.sheet.format(right + top, {"borders": {"right": border, "top": border}})
        self.sheet.format(left + bottom, {"borders": {"left": border, "bottom": border}})
        self.sheet.format(right + bottom, {"borders": {"right": border, "bottom": border}})