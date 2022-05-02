from typing import List

import gspread
from oauth2client.service_account import ServiceAccountCredentials


class Sheets:
    def __init__(self, credentials: ServiceAccountCredentials, workbook_name="OZON Трекер количества"):
        self.client = gspread.authorize(credentials)
        self.workbook = self.client.open(workbook_name)
        self.sheet = self.workbook.sheet1

    def get_urls(self) -> List[str]:
        return self.sheet.col_values(2)

    def set_quantities(self, quantities: List[int]):
        cells = tuple(map(lambda x: [x], quantities))
        self.sheet.update("A1", cells)
