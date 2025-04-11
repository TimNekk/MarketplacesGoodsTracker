from datetime import datetime

from gspread.utils import ValueInputOption
from oauth2client.service_account import ServiceAccountCredentials

from src.models import Status, OzonItem, OzonUrls
from src.sheets import Sheets
from src.utils import logger


class OzonSheets(Sheets):
    WORKBOOK_NAME = "Трекер Ozon"
    TOP_OFFSET_CELL_VALUE = "Продавец"

    def __init__(self, credentials: ServiceAccountCredentials) -> None:
        super().__init__(credentials, self.WORKBOOK_NAME, self.TOP_OFFSET_CELL_VALUE)
        self._top_offset += 1

    def get_urls(self, skip_empty: bool = True) -> OzonUrls:
        logger.info("Getting urls...")

        urls = self._sheet.col_values(2)[(self._top_offset + 1) :]

        if skip_empty:
            urls = filter(lambda url: url != "", urls)

        return OzonUrls(list(urls))

    def set_items(self, items: list[OzonItem]) -> None:
        quantities: list[str | int] = [""] * (self._top_offset - 1) + [
            datetime.now().strftime("%d/%m - %H:%M"),
            "Количество",
        ]
        prices: list[str | int] = [""] * self._top_offset + ["Цена"]
        green_prices = [False] * (self._top_offset + 1)

        urls = self.get_urls(skip_empty=False)

        for url in urls:
            for item in items:
                if item and item.url != url:
                    continue

                if item.status == Status.OK:
                    quantities.append(str(item.quantity))
                    prices.append(
                        str(item.green_price) if item.green_price else str(item.price)
                    )
                    green_prices.append(True if item.green_price else False)
                else:
                    quantities.append(str(item.status.value))
                    prices.append("")
                    green_prices.append(False)

                break

        quantities = list(map(str, quantities))
        prices = list(map(str, prices))

        logger.debug("Inserting data...")
        self._sheet.insert_cols(
            [quantities, prices],
            col=8,
            value_input_option=ValueInputOption.user_entered,
        )

        logger.debug("Adding borders...")
        self._add_border(f"H1:I{len(urls) + self._top_offset + 1}")

        logger.debug("Formatting numbers...")
        self._format_cells(f"H3:I{len(urls) + self._top_offset + 1}")

        logger.debug("Coloring green cells...")
        self._color_green_cells(f"I3:I{len(urls) + 1}", green_prices)

        logger.debug("Merging cells...")
        self._sheet.merge_cells("H1:I1")
