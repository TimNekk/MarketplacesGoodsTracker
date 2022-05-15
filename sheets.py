from datetime import datetime
from typing import List

import gspread
from oauth2client.service_account import ServiceAccountCredentials


class Sheets:
    def __init__(self, credentials: ServiceAccountCredentials, workbook_name="OZON Трекер количества"):
        self.client = gspread.authorize(credentials)
        self.workbook = self.client.open(workbook_name)
        self.sheet = self.workbook.sheet1

    def get_urls(self) -> List[str]:
        return self.sheet.col_values(1)[1:]

    def set_quantities(self, quantities: List[int]):
        cells = list(map(lambda x: "Нет в наличии" if x == -1 else x, quantities))
        cells.insert(0, datetime.now().strftime("%d/%m"))
        print(cells)
        self.sheet.insert_cols([cells], col=3)
