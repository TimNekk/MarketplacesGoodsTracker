from datetime import datetime
from typing import List

from gspread.utils import ValueInputOption
from oauth2client.service_account import ServiceAccountCredentials

from src.models import Status, WildberriesItem, WildberriesUrls
from src.sheets import Sheets, CellFormat
from src.utils import logger


class WildberriesSheets(Sheets):
    WORKBOOK_NAME = "Трекер Wildberries"
    TOP_OFFSET_CELL_VALUE = "Ссылка"

    def __init__(self, credentials: ServiceAccountCredentials):
        super().__init__(credentials, self.WORKBOOK_NAME, self.TOP_OFFSET_CELL_VALUE)

    def get_urls(self) -> WildberriesUrls:
        logger.info("Getting urls...")
        urls = list(filter(lambda url: url != "", self._sheet.col_values(1)[(self._top_offset + 1):]))
        return WildberriesUrls(urls)

    def set_items(self, items: List[WildberriesItem]):
        quantities = [""] * self._top_offset + [datetime.now().strftime("%d/%m - %H:%M")]
        prices = [""] * (self._top_offset + 1)
        sales = [""] * (self._top_offset + 1)

        urls = self.get_urls()
        for url in urls:
            added = False

            for item in items:
                if item.url != url:
                    continue

                if item.status == Status.OK:
                    quantities.append(str(item.quantity))
                    prices.append(str(item.sale_price))
                    sales.append(item.sale_formula)
                else:
                    quantities.append(str(item.status.value))
                    prices.append("")
                    sales.append("")
                added = True
                break

            if not added:
                quantities.append("")
                prices.append("")
                sales.append("")

        logger.debug("Removing previous colors...")
        self._remove_formatting(f"E2:E{len(urls) + 1}")

        logger.debug("Inserting data...")
        self._sheet.insert_cols([quantities, prices, sales], col=4, value_input_option=ValueInputOption.user_entered)

        logger.debug("Adding borders...")
        self._add_border(f"D1:F{len(urls) + 1}")

        logger.debug("Formatting numbers...")
        self._format_cells(f"D2:E{len(urls) + 1}")
        self._format_cells(f"F2:F{len(urls) + 1}", CellFormat.NUMBER_PERCENT)

        logger.debug("Coloring red cells...")
        self._color_red_cells(f"E2:E{len(urls) + 1}", restrictions_col=3, prices_col=5)

        logger.debug("Merging cells...")
        self._sheet.merge_cells("D1:F1")
