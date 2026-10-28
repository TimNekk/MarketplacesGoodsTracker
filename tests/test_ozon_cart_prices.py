import json
import unittest
from unittest.mock import MagicMock, patch

from src.models import Status
from src.parsing.ozon_parser import FetchResult, OzonParser


def cart_response(sku=224587638, quantity=2, price='16\u2009200 ₽', card_price='14\u2009580 ₽'):
    columns = []
    for kind, text in [('price', price), ('ozon-card-price', card_price)]:
        if text is not None:
            columns.append({'type': 'prices', 'prices': {'elements': [{
                'testInfo': {'automatizationId': f'cart-split-item-{kind}'},
                'price': [{'text': text}],
            }]}})
    return {'widgetStates': {'cartSplit-1': json.dumps({'cartItems': [{
        'product': {'id': str(sku), 'priceColumn': columns},
        'controls': {'quantity': {'current': quantity}},
    }]})}}


class OzonCartPricesTests(unittest.TestCase):
    def test_cart_totals_become_unit_prices(self):
        self.assertEqual(OzonParser._get_cart_prices(cart_response(), 224587638), (8100, 7290))

    def test_card_price_is_optional(self):
        self.assertEqual(OzonParser._get_cart_prices(cart_response(card_price=None), 224587638), (8100, None))

    def test_missing_product_and_fractional_price_are_rejected(self):
        for response, sku in [(cart_response(), 123), (cart_response(price='16 201 ₽'), 224587638)]:
            with self.subTest(sku=sku), self.assertRaises(ValueError):
                OzonParser._get_cart_prices(response, sku)

    def test_anonymous_session_reads_cart_and_removes_only_requested_product(self):
        url = 'https://www.ozon.ru/product/example-224587638/'
        session = MagicMock(is_authenticated=False)
        session.fetch.side_effect = [
            FetchResult(200, url, {'widgetStates': {'webPrice-1': json.dumps({'price': '6075 ₽', 'cardPrice': '5468 ₽'})}}),
            FetchResult(200, '', {'cart': {'cartItems': [{'id': 224587638, 'qty': 2}, {'id': 123, 'qty': 1}]}}),
            FetchResult(200, '', cart_response()),
            FetchResult(200, '', {}),
        ]
        with patch.object(OzonParser, '_get_session', return_value=session):
            item = OzonParser._get_item(url)
        self.assertEqual((item.status, item.price, item.green_price, item.quantity), (Status.OK, 8100, 7290, 2))
        self.assertEqual(session.fetch.call_args_list[2].args, (OzonParser._CART_URL,))
        self.assertEqual(json.loads(session.fetch.call_args_list[3].kwargs['body']), [{'id': 224587638}])

    def test_cart_failure_still_removes_product_and_never_returns_card_page_price(self):
        url = 'https://www.ozon.ru/product/example-224587638/'
        session = MagicMock(is_authenticated=False)
        session.fetch.side_effect = [
            FetchResult(200, url, {'widgetStates': {'webPrice-1': json.dumps({'price': '6075 ₽'})}}),
            FetchResult(200, '', {'cart': {'cartItems': [{'id': 224587638, 'qty': 2}]}}),
            FetchResult(400, '', None),
            FetchResult(200, '', {}),
        ]
        with patch.object(OzonParser, '_get_session', return_value=session):
            item = OzonParser._get_item(url)
        self.assertEqual(item.status, Status.PARSING_ERROR)
        self.assertEqual(json.loads(session.fetch.call_args_list[-1].kwargs['body']), [{'id': 224587638}])

    def test_card_page_price_is_not_required(self):
        url = 'https://www.ozon.ru/product/example-224587638/'
        for widget in ({}, {'price': '', 'cardPrice': ''}):
            with self.subTest(widget=widget):
                session = MagicMock(is_authenticated=False)
                session.fetch.side_effect = [
                    FetchResult(200, url, {'widgetStates': {'webPrice-1': json.dumps(widget)}}),
                    FetchResult(200, '', {'cart': {'cartItems': [{'id': 224587638, 'qty': 2}]}}),
                    FetchResult(200, '', cart_response()),
                    FetchResult(200, '', {}),
                ]
                with patch.object(OzonParser, '_get_session', return_value=session):
                    item = OzonParser._get_item(url)
                self.assertEqual((item.status, item.price, item.green_price), (Status.OK, 8100, 7290))

    def test_missing_price_widget_still_means_out_of_stock(self):
        session = MagicMock()
        session.fetch.return_value = FetchResult(200, '', {'widgetStates': {}})
        with patch.object(OzonParser, '_get_session', return_value=session):
            item = OzonParser._get_item('https://www.ozon.ru/product/example-224587638/')
        self.assertEqual(item.status, Status.OUT_OF_STOCK)
        self.assertEqual(session.fetch.call_count, 1)

    def test_cart_403_refreshes_even_when_cleanup_raises(self):
        url = 'https://www.ozon.ru/product/example-224587638/'
        product = FetchResult(200, url, {'widgetStates': {'webPrice-1': '{}'}})
        quantity = FetchResult(200, '', {'cart': {'cartItems': [{'id': 224587638, 'qty': 2}]}})
        old_session, new_session = MagicMock(), MagicMock()
        old_session.fetch.side_effect = [
            product, quantity, FetchResult(403, '', None), RuntimeError('Network error during cleanup'),
        ]
        new_session.fetch.side_effect = [
            product, quantity, FetchResult(200, '', cart_response()), FetchResult(200, '', {}),
        ]
        with (
            patch.object(OzonParser, '_get_session', side_effect=[old_session, new_session]),
            patch.object(OzonParser, '_refresh_session_on_403') as refresh,
            patch('the_retry.retry.time.sleep'),
        ):
            item = OzonParser._get_item(url)
        refresh.assert_called_once_with()
        self.assertEqual((item.status, item.price, item.green_price), (Status.OK, 8100, 7290))
        self.assertEqual(old_session.fetch.call_count, 4)
        self.assertEqual(new_session.fetch.call_count, 4)


if __name__ == '__main__':
    unittest.main()
