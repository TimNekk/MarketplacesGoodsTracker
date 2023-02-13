from datetime import datetime
from typing import List
import re

import gspread
from gspread.utils import ValueInputOption
from oauth2client.service_account import ServiceAccountCredentials

from src.models import Item, Status
from src.utils import logger


class Sheets:
    def __init__(self, credentials: ServiceAccountCredentials, workbook_name="OZON Трекер количества"):
        self.client = gspread.authorize(credentials)
        self.workbook = self.client.open(workbook_name)

        self.sheet = self.workbook.sheet1
        self.top_offset = self._get_top_offset()

    def _get_top_offset(self) -> int:
        logger.info("Getting top offset...")
        return self.sheet.col_values(1).index("Ссылка")

    def get_urls(self) -> List[str]:
        logger.info("Getting urls...")
        return self.sheet.col_values(1)[(self.top_offset + 1):]

    def set_items(self, items: List[Item]):
        quantities = [""] * self.top_offset + [datetime.now().strftime("%d/%m - %H:%M")]
        prices = [""] * (self.top_offset + 1)

        urls = self.get_urls()
        for url in urls:
            added = False

            for item in items:
                if item.id not in url:
                    continue

                if item.status == Status.OK:
                    quantities.append(str(item.quantity))
                    prices.append(str(item.price))
                else:
                    quantities.append(str(item.status.value))
                    prices.append("")
                added = True
                break

            if not added:
                quantities.append("")
                prices.append("")

        logger.debug("Removing previous colors...")
        self._remove_formatting(f"E2:E{len(urls) + 1}")

        logger.debug("Inserting data...")
        self.sheet.insert_cols([quantities, prices], col=4, value_input_option=ValueInputOption.user_entered)

        logger.debug("Adding borders...")
        self._add_border(f"D1:E{len(urls) + 1}")

        logger.debug("Formatting numbers...")
        self._format_number(f"D2:E{len(urls) + 1}")

        logger.debug("Coloring cells...")
        self._color_cells(f"E2:E{len(urls) + 1}")

        logger.debug("Merging cells...")
        self.sheet.merge_cells("D1:E1")

    def _add_border(self, cells_range: str) -> None:
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

    def _format_number(self, cells_range: str) -> None:
        first, second = cells_range.split(":")
        left, top, right, bottom = first[0], first[1:], second[0], second[1:]

        # Edges
        self.sheet.format(cells_range, {"numberFormat": {"type": "NUMBER", "pattern": "# ###"}})

    @staticmethod
    def _number_literal_to_int(number_literal: str) -> int:
        return int(re.sub(r"\D", "", number_literal))

    def _get_restrictions(self) -> list[int]:
        logger.debug("Getting restrictions...")
        return list(map(
            lambda n: self._number_literal_to_int(n) if n else 0,
            self.sheet.col_values(3)[(self.top_offset + 1):]
        ))

    def _color_cells(self, cells_range: str) -> None:
        restrictions = self._get_restrictions()

        first, second = cells_range.split(":")
        left, top, right, _ = first[0], int(first[1:]), second[0], second[1:]

        prices = self.sheet.col_values(5)[(self.top_offset + 1):]
        for i, price in enumerate(prices):
            if i >= len(restrictions):
                break

            if not price:
                continue

            price = self._number_literal_to_int(price)
            if price < restrictions[i]:
                self.sheet.format(f"{left}{i + top}:{right}{i + top}",
                                  {"textFormat": {"foregroundColor": {"red": 1}}})

    def _remove_formatting(self, cells_range: str) -> None:
        self.sheet.format(cells_range, {"textFormat": {"foregroundColor": {}}})

    def replace_url(self, old_url: str, new_url: str):
        logger.info(f"Replacing {old_url} with {new_url}...")
        cell = self.sheet.find(old_url)
        self.sheet.update_cell(cell.row, cell.col, new_url)

