import json
import re

from requests import Session

from src.models import Status, OzonUrls, OzonItemPair, OzonItem
from src.parsing import ItemParser
from src.parsing.exceptions import OutOfStockException
from src.utils import logger


class OzonParser(ItemParser):
    _HEADERS = {
        "accept": "*/*",
        "user-agent": "ozonapp_android/16.23.1+2381",
        "X-O3-App-Name": "ozonapp_android",
        "X-O3-App-Version": "16.23.1(2381)",
        "X-O3-Device-Type": "mobile",
        "Mobile-Lat": "0"
    }
    _BASE_URL = r"https://api.ozon.ru/composer-api.bx"
    _PRODUCT_URL = _BASE_URL + r"/page/json/v2?url=%2Fproduct%2F"
    _ADD_TO_CART_URL = _BASE_URL + r"/_action/addToCart"

    @staticmethod
    def price_to_number(price: str) -> int:
        return int(re.sub(r'\D', '', price))

    @staticmethod
    def extract_url_parts(url) -> tuple[str | None, int | None]:
        updated_regex = r"/product/([^/]+)"
        match = re.search(updated_regex, url)

        if not match:
            return None, None

        if match:
            full_string = match.group(1)
            last_number_match = re.findall(r"\d+", full_string)
            if last_number_match:
                last_number = int(last_number_match[-1])
                return full_string, last_number
            else:
                return full_string, None
        else:
            return None, None

    @staticmethod
    def _get_prices(response: dict) -> tuple[int, int | None]:
        widget_states = response["widgetStates"]

        price_json = None
        for key, value in widget_states.items():
            if key.startswith("price-"):
                price_json = json.loads(value)
                break

        if price_json is None:
            raise OutOfStockException("Item is out of stock")

        if price_json.get("ordinaryPrice"):
            price_str = price_json["ordinaryPrice"]["price"]["price"]["text"]
            return OzonParser.price_to_number(price_str), None

        price_str = price_json["ozonCardPrice"]["price"]["price"]["price"]["text"]
        green_price_str = price_json["ozonCardPrice"]["accentPrice"]["price"]["price"]["price"]["text"]

        return OzonParser.price_to_number(price_str), OzonParser.price_to_number(green_price_str)

    @staticmethod
    def _get_quantity(response: dict) -> int:
        return response["cart"]["cartItems"][0]["qty"]

    @staticmethod
    def get_items(urls: OzonUrls) -> list[OzonItemPair]:
        items = []

        for urls_tuple in urls:
            fbs, fbo = None, None
            if urls_tuple[0] != "":
                fbs = OzonParser._get_item(urls_tuple[0])
            if urls_tuple[1] != "":
                fbo = OzonParser._get_item(urls_tuple[1])

            if fbo or fbs:
                items.append(OzonItemPair(fbs=fbs, fbo=fbo))

        return items

    @staticmethod
    def _get_item(url: str) -> OzonItem | None:
        logger.info(f"Getting item from: {url}...")

        url_part, sku = OzonParser.extract_url_parts(url)

        if url_part is None or sku is None:
            logger.debug(f"Wrong url passed ({url})")
            return None

        with Session() as session:
            session.headers.update(OzonParser._HEADERS)

            response_price = session.get(
                url=OzonParser._PRODUCT_URL + url_part
            )
            response_quantity = session.post(
                url=OzonParser._ADD_TO_CART_URL,
                data=json.dumps([{"id": sku, "quantity": 2000}])
            )

        if response_price.status_code != 200:
            logger.debug(f"Wrong url passed ({url})")
            return None

        try:
            price, green_price = OzonParser._get_prices(response_price.json())
        except OutOfStockException as e:
            logger.info(e)
            return OzonItem(url=url, status=Status.OUT_OF_STOCK)
        quantity = OzonParser._get_quantity(response_quantity.json())

        item = OzonItem(
            url=url,
            quantity=quantity,
            price=price,
            status=Status.OK,
            green_price=green_price
        )

        logger.info(f"Got item: {item}")
        return item


def test_run():
    print(OzonParser._get_item(input("Enter url: ")))


if __name__ == '__main__':
    test_run()
