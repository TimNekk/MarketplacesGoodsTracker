import unittest
from unittest.mock import MagicMock, patch

from src.models import OzonItem, Status
from src.sheets import OzonSheets, WildberriesSheets


class SheetOffsetTests(unittest.TestCase):
    def make_tracker(self, tracker_type, columns):
        sheet = MagicMock()
        sheet.col_values.side_effect = columns.__getitem__
        with patch('src.sheets.sheets.gspread.authorize') as authorize:
            authorize.return_value.open.return_value.sheet1 = sheet
            tracker = tracker_type(MagicMock())
        return tracker, sheet

    def test_ozon_ignores_headers_and_preserves_product_alignment(self):
        url = 'https://www.ozon.ru/product/example-123/'
        for headers in (['Ссылка', ''], ['Renamed', 'anything'], ['', '']):
            with self.subTest(headers=headers):
                tracker, sheet = self.make_tracker(OzonSheets, {2: headers + [url, '', url]})
                self.assertEqual(tracker._top_offset, 1)
                self.assertEqual(list(tracker.get_urls()), [url, url])
                for method in ('_add_border', '_format_cells', '_color_green_cells'):
                    setattr(tracker, method, MagicMock())
                tracker.set_items([OzonItem(url=url, quantity=7, price=100, status=Status.OK)])
                columns = sheet.insert_cols.call_args.args[0]
                self.assertEqual(columns[0][2:], ['7', '', '7'])
                self.assertEqual(columns[1][2:], ['100', '', '100'])

    def test_ozon_rejects_missing_product_urls(self):
        for values in ([], ['Ссылка', ''], ['https://ozon.ru.example.com/product/123/']):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, 'column B'):
                self.make_tracker(OzonSheets, {2: values})

    def test_ozon_requires_room_for_output_headers(self):
        with self.assertRaisesRegex(ValueError, 'two header rows'):
            self.make_tracker(OzonSheets, {2: ['https://ozon.ru/product/123/']})

    def test_wildberries_keeps_existing_offset(self):
        tracker, _ = self.make_tracker(WildberriesSheets, {1: ['Ссылка', 'url']})
        self.assertEqual(tracker._top_offset, 0)
        self.assertEqual(list(tracker.get_urls()), ['url'])


if __name__ == '__main__':
    unittest.main()
