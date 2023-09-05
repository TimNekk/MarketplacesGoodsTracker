from datetime import datetime
from itertools import zip_longest

from gspread.utils import ValueInputOption
from oauth2client.service_account import ServiceAccountCredentials

from src.models import Status, OzonItemPair, OzonUrls
from src.sheets import Sheets
from src.utils import logger


class OzonSheets(Sheets):
    WORKBOOK_NAME = "Трекер Ozon"
    TOP_OFFSET_CELL_VALUE = "FBS"

    def __init__(self, credentials: ServiceAccountCredentials):
        super().__init__(credentials, self.WORKBOOK_NAME, self.TOP_OFFSET_CELL_VALUE)
        self._top_offset += 1

    def get_urls(self, skip_empty: bool = True) -> OzonUrls:
        logger.info("Getting urls...")

        fbs_urls = self._sheet.col_values(1)[(self._top_offset + 1):]
        fbo_urls = self._sheet.col_values(2)[(self._top_offset + 1):]
        urls = zip_longest(fbs_urls, fbo_urls, fillvalue="")

        if skip_empty:
            urls = filter(lambda urls_tuple: urls_tuple[0] != "" or urls_tuple[1] != "", urls)

        return OzonUrls(list(urls))

    def set_items(self, items: list[OzonItemPair]):
        fbs_quantities: list[str | int] = ([""] * (self._top_offset - 1) +
                                           [datetime.now().strftime("%d/%m - %H:%M"), "FBS"])
        fbo_quantities: list[str | int] = [""] * self._top_offset + ["FBO"]
        fbs_prices: list[str | int] = [""] * self._top_offset + ["Цена FBS"]
        fbo_prices: list[str | int] = [""] * self._top_offset + ["Цена FBO"]
        fbs_green_prices = [False] * (self._top_offset + 1)
        fbo_green_prices = [False] * (self._top_offset + 1)

        urls = self.get_urls(skip_empty=False)
        for urls_tuple in urls:
            added = False

            for item in items:
                try:
                    if (item.fbs and item.fbs.url != urls_tuple[0]) or (item.fbo and item.fbo.url != urls_tuple[1]):
                        continue

                    if (item.fbs and item.fbs.status == Status.OUT_OF_STOCK) and (item.fbo and item.fbo.status == Status.OUT_OF_STOCK):
                        fbs_quantities.append(str(item.fbs.status.value))
                        fbo_quantities.append("")
                        fbs_prices.append("")
                        fbo_prices.append("")
                        fbs_green_prices.append(False)
                        fbo_green_prices.append(False)
                        added = True
                        break

                    if item.fbs:
                        if item.fbs.status in (Status.OK, Status.OUT_OF_STOCK):
                            fbs_quantities.append(item.fbs.quantity)
                            if item.fbs.status == Status.OK:
                                fbs_prices.append(str(item.fbs.green_price if item.fbs.green_price else item.fbs.price))
                                fbs_green_prices.append(True if item.fbs.green_price else False)
                            else:
                                fbs_prices.append("")
                                fbs_green_prices.append(False)
                        else:
                            fbs_quantities.append(str(item.fbs.status.value))
                            fbs_prices.append("")
                            fbs_green_prices.append(False)
                    else:
                        fbs_quantities.append("")
                        fbs_prices.append("")
                        fbs_green_prices.append(False)

                    if item.fbo:
                        if item.fbo.status in (Status.OK, Status.OUT_OF_STOCK):
                            fbo_quantities.append(item.fbo.quantity)
                            if item.fbo.status == Status.OK:
                                fbo_prices.append(str(item.fbo.green_price if item.fbo.green_price else item.fbo.price))
                                fbo_green_prices.append(True if item.fbo.green_price else False)
                            else:
                                fbo_prices.append("")
                                fbo_green_prices.append(False)
                        else:
                            fbo_quantities.append(str(item.fbo.status.value))
                            fbo_prices.append("")
                            fbo_green_prices.append(False)
                    else:
                        fbo_quantities.append("")
                        fbo_prices.append("")
                        fbo_green_prices.append(False)

                    added = True
                    break
                except Exception as e:
                    logger.error(f"Error while adding item to sheet: {e}")
                    continue

            if not added:
                fbs_quantities.append("")
                fbo_quantities.append("")
                fbs_prices.append("")
                fbo_prices.append("")
                fbs_green_prices.append(False)
                fbo_green_prices.append(False)

        fbs_quantities = list(map(str, fbs_quantities))
        fbo_quantities = list(map(str, fbo_quantities))
        fbs_prices = list(map(str, fbs_prices))
        fbo_prices = list(map(str, fbo_prices))

        # logger.debug("Removing previous colors...")
        # self._remove_formatting(f"E3:H{len(urls) + self._top_offset + 1}")

        logger.debug("Inserting data...")
        self._sheet.insert_cols([fbs_quantities, fbo_quantities, fbs_prices, fbo_prices],
                                col=5, value_input_option=ValueInputOption.user_entered)

        logger.debug("Adding borders...")
        self._add_border(f"E1:H{len(urls) + self._top_offset + 1}")

        logger.debug("Formatting numbers...")
        self._format_cells(f"E3:H{len(urls) + self._top_offset + 1}")

        # logger.debug("Coloring red cells...")
        # self._color_red_cells(f"G3:G{len(urls) + self._top_offset + 1}", restrictions_col=4, prices_col=7)
        # self._color_red_cells(f"H3:H{len(urls) + self._top_offset + 1}", restrictions_col=4, prices_col=8)

        logger.debug("Coloring green cells...")
        self._color_green_cells(f"G3:G{len(urls) + 1}", fbs_green_prices)
        self._color_green_cells(f"H3:H{len(urls) + 1}", fbo_green_prices)

        logger.debug("Merging cells...")
        self._sheet.merge_cells("E1:H1")
