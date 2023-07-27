from datetime import datetime
from time import sleep
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
        green_prices = [False] * (self.top_offset + 1)

        urls = self.get_urls()
        for url in urls:
            added = False

            for item in items:
                if item.url != url:
                    continue

                if item.status == Status.OK:
                    quantities.append(str(item.quantity))
                    if item.green_price:
                        prices.append(str(item.green_price))
                        green_prices.append(True)
                    else:
                        prices.append(str(item.price))
                        green_prices.append(False)
                else:
                    quantities.append(str(item.status.value))
                    prices.append("")
                    green_prices.append(False)
                added = True
                break

            if not added:
                quantities.append("")
                prices.append("")
                green_prices.append(False)

        logger.debug("Removing previous colors...")
        self._remove_formatting(f"E2:E{len(urls) + 1}")

        logger.debug("Inserting data...")
        self.sheet.insert_cols([quantities, prices], col=4, value_input_option=ValueInputOption.user_entered)

        logger.debug("Adding borders...")
        self._add_border(f"D1:E{len(urls) + 1}")

        logger.debug("Formatting numbers...")
        self._format_number(f"D2:E{len(urls) + 1}")

        logger.debug("Coloring red cells...")
        self._color_red_cells(f"E2:E{len(urls) + 1}")

        logger.debug("Coloring green cells...")
        self._color_green_cells(f"E2:E{len(urls) + 1}", green_prices)

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
        sleep(1)

        # Corners
        self.sheet.format(left + top, {"borders": {"left": border, "top": border}})
        self.sheet.format(right + top, {"borders": {"right": border, "top": border}})
        self.sheet.format(left + bottom, {"borders": {"left": border, "bottom": border}})
        self.sheet.format(right + bottom, {"borders": {"right": border, "bottom": border}})
        sleep(1)

    def _format_number(self, cells_range: str) -> None:
        # Edges
        self.sheet.format(cells_range, {"numberFormat": {"type": "NUMBER", "pattern": "# ###"}})
        sleep(1)

    @staticmethod
    def _number_literal_to_int(number_literal: str) -> int:
        return int(re.sub(r"\D", "", number_literal))

    def _get_restrictions(self) -> list[int]:
        logger.debug("Getting restrictions...")
        return list(map(
            lambda n: self._number_literal_to_int(n) if n else 0,
            self.sheet.col_values(3)[(self.top_offset + 1):]
        ))

    def _color_red_cells(self, cells_range: str) -> None:
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
                                  {
                                      "textFormat":
                                          {
                                              "foregroundColor":
                                                  {
                                                      "red": 0.8
                                                  },
                                              "bold": True
                                          },
                                  })
                sleep(1)

    def _color_green_cells(self, cells_range: str, green_prices: list[bool]) -> None:
        first, second = cells_range.split(":")
        left, top, right, _ = first[0], int(first[1:]) - 1, second[0], second[1:]

        for i, green_price in enumerate(green_prices):
            if not green_price:
                continue

            self.sheet.format(f"{left}{i + top}:{right}{i + top}",
                              {
                                  "backgroundColor":
                                      {
                                          "red": 0.85,
                                          "green": 0.91,
                                          "blue": 0.82
                                      }
                              })
            sleep(1)

    def _remove_formatting(self, cells_range: str) -> None:
        self.sheet.format(cells_range,
                          {
                              "textFormat":
                                  {
                                      "foregroundColor": {},
                                      "bold": False
                                  },
                              "backgroundColor": {
                                  "red": 1,
                                  "green": 1,
                                  "blue": 1
                              }
                          })
        sleep(1)

    def replace_url(self, old_url: str, new_url: str):
        logger.info(f"Replacing {old_url} with {new_url}...")
        cell = self.sheet.find(old_url)
        self.sheet.update_cell(cell.row, cell.col, new_url)
