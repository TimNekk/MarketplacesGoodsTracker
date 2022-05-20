from datetime import datetime
from typing import List

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from errors import Error


class Sheets:
    def __init__(self, credentials: ServiceAccountCredentials, workbook_name="OZON Трекер количества"):
        self.client = gspread.authorize(credentials)
        self.workbook = self.client.open(workbook_name)
        self.sheet = self.workbook.sheet1

    def get_urls(self) -> List[str]:
        return self.sheet.col_values(1)[1:]

    def set_quantities(self, quantities: List):
        for i in range(len(quantities)):
            if quantities[i] == Error.OUT_OF_STOCK:
                quantities[i] = "Нет в наличии"
            elif quantities[i] == Error.PARSING_ERROR:
                quantities[i] = "Ошибка"

        quantities.insert(0, datetime.now().strftime("%d/%m"))
        self.sheet.insert_cols([quantities], col=3)
