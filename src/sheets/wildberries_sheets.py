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

    def get_urls(self, skip_empty: bool = True) -> WildberriesUrls:
        logger.info("Getting urls...")
        urls = self._sheet.col_values(1)[(self._top_offset + 1):]
        if skip_empty:
            urls = list(filter(lambda url: url != "", urls))
        return WildberriesUrls(urls)

    def set_items(self, items: List[WildberriesItem]):
        quantities = [""] * self._top_offset + [datetime.now().strftime("%d/%m - %H:%M")]
        prices = [""] * (self._top_offset + 1)
        sales = [""] * (self._top_offset + 1)

        urls = self.get_urls(skip_empty=False)
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
        self._remove_formatting(f"H2:H{len(urls) + 1}")

        logger.debug("Inserting data...")
        self._sheet.insert_cols([quantities, prices, sales], col=7, value_input_option=ValueInputOption.user_entered)

        logger.debug("Adding borders...")
        self._add_border(f"G1:I{len(urls) + 1}")

        logger.debug("Formatting numbers...")
        self._format_cells(f"G2:H{len(urls) + 1}", CellFormat.NUMBER_WITH_SPACE)
        self._format_cells(f"I2:I{len(urls) + 1}", CellFormat.NUMBER_PERCENT)

        logger.debug("Coloring red cells...")
        self._color_red_cells(f"H2:H{len(urls) + 1}", restrictions_col=3, prices_col=5)

        logger.debug("Merging cells...")
        self._sheet.merge_cells("G1:I1")
