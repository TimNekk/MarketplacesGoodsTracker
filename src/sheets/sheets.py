import re
from abc import ABC, abstractmethod
from time import sleep

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from src.models import Item, Urls
from src.utils import logger


class Sheets(ABC):
    def __init__(self,
                 credentials: ServiceAccountCredentials,
                 workbook_name: str,
                 top_offset_cell_value: str
                 ) -> None:
        self._client = gspread.authorize(credentials)
        self._workbook = self._client.open(workbook_name)
        self._top_offset_cell_value = top_offset_cell_value

        self._sheet = self._workbook.sheet1
        self._top_offset = self._get_top_offset()

    def _get_top_offset(self) -> int:
        logger.info("Getting top offset...")
        return self._sheet.col_values(1).index(self._top_offset_cell_value)

    @abstractmethod
    def get_urls(self) -> Urls:
        pass

    @abstractmethod
    def set_items(self, items: list[Item]):
        pass

    def _add_border(self, cells_range: str) -> None:
        first, second = cells_range.split(":")
        left, top, right, bottom = first[0], first[1:], second[0], second[1:]
        border = {"style": "SOLID"}

        # Edges
        self._sheet.format(f"{left}{top}:{right}{top}", {"borders": {"top": border}})
        self._sheet.format(f"{left}{top}:{left}{bottom}", {"borders": {"left": border}})
        self._sheet.format(f"{left}{bottom}:{right}{bottom}", {"borders": {"bottom": border}})
        self._sheet.format(f"{right}{top}:{right}{bottom}", {"borders": {"right": border}})
        sleep(1)

        # Corners
        self._sheet.format(left + top, {"borders": {"left": border, "top": border}})
        self._sheet.format(right + top, {"borders": {"right": border, "top": border}})
        self._sheet.format(left + bottom, {"borders": {"left": border, "bottom": border}})
        self._sheet.format(right + bottom, {"borders": {"right": border, "bottom": border}})
        sleep(1)

    def _format_number(self, cells_range: str) -> None:
        # Edges
        self._sheet.format(cells_range, {"numberFormat": {"type": "NUMBER", "pattern": "#,##0;#,##0;0"}})
        sleep(1)

    @staticmethod
    def _number_literal_to_int(number_literal: str) -> int:
        return int(re.sub(r"\D", "", number_literal))

    def _get_restrictions(self, restrictions_col: int) -> list[int]:
        logger.debug("Getting restrictions...")
        return list(map(
            lambda n: self._number_literal_to_int(n) if n else 0,
            self._sheet.col_values(restrictions_col)[(self._top_offset + 1):]
        ))

    def _color_red_cells(self, cells_range: str, restrictions_col: int, prices_col: int) -> None:
        restrictions = self._get_restrictions(restrictions_col)

        first, second = cells_range.split(":")
        left, top, right, _ = first[0], int(first[1:]), second[0], second[1:]

        prices = self._sheet.col_values(prices_col)[(self._top_offset + 1):]
        for i, price in enumerate(prices):
            if i >= len(restrictions):
                break

            if not price:
                continue

            price = self._number_literal_to_int(price)
            if price < restrictions[i]:
                self._sheet.format(f"{left}{i + top}:{right}{i + top}",
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
        left, top, right, _ = first[0], int(first[1:]) - self._top_offset - 1, second[0], second[1:]

        for i, green_price in enumerate(green_prices):
            if not green_price:
                continue

            self._sheet.format(f"{left}{i + top}:{right}{i + top}",
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
        self._sheet.format(cells_range,
                           {
                               "textFormat":
                                   {
                                       "foregroundColor": {},
                                       "bold": False
                                   },
                               # "backgroundColor": {
                               #     "red": 1,
                               #     "green": 1,
                               #     "blue": 1
                               # }
                           })
        sleep(1)
