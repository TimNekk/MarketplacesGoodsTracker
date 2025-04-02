from __future__ import annotations

import json
import os
import re

from the_retry import retry
from curl_cffi import requests

from src.models import Status, OzonUrls, OzonItemPair, OzonItem
from src.parsing import ItemParser
from src.parsing.exceptions import OutOfStockException
from src.utils import logger


class OzonParser(ItemParser):
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 YaBrowser/24.1.0.0 Safari/537.36",
    }
    _BASE_URL = r"https://api.ozon.ru/"
    _PRODUCT_URL = _BASE_URL + r"entrypoint-api.bx/page/json/v2?url=%2Fproduct%2F"
    _ADD_TO_CART_URL = _BASE_URL + r"composer-api.bx/_action/addToCart"

    @staticmethod
    def price_to_number(price: str) -> int:
        return int(re.sub(r"\D", "", price))

    @staticmethod
    def extract_url_parts(url) -> tuple[str | None, int | None]:
        updated_regex = r"(?:\/product\/|%2Fproduct%2F)([\w-]+)"
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
            if key.startswith("webPrice-"):
                price_json = json.loads(value)
                break

        if price_json is None:
            raise OutOfStockException("Item is out of stock")

        price_str = price_json["price"]
        green_price_str = price_json.get("cardPrice")

        return (
            OzonParser.price_to_number(price_str),
            OzonParser.price_to_number(green_price_str) if green_price_str else None,
        )

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
    def return_error_item_on_exception(raise_exception=False):
        def decorator(func):
            def get_item(url: str):
                try:
                    item = func(url)
                except Exception as e:
                    if raise_exception:
                        raise e

                    item = OzonItem(url=url, status=Status.PARSING_ERROR)
                return item

            return get_item

        return decorator

    @staticmethod
    @return_error_item_on_exception()
    @retry(attempts=3, backoff=5, exponential_backoff=True)
    def _get_item(url: str) -> OzonItem | None:
        logger.info(f"Getting item from: {url}...")

        url_part, sku = OzonParser.extract_url_parts(url)

        if url_part is None or sku is None:
            logger.debug(f"Wrong url passed ({url})")
            return None

        proxy_url = os.environ.get("PROXY_URL")

        response_price = requests.get(
            url=OzonParser._PRODUCT_URL + url_part,
            headers=OzonParser._HEADERS,
            impersonate="chrome116",
            proxies={"https": proxy_url},
        )

        if response_price.status_code != 200:
            logger.debug(
                f"Got error response from Ozon prices: {response_price.status_code}"
            )
            return None

        try:
            price, green_price = OzonParser._get_prices(response_price.json())
        except OutOfStockException as e:
            logger.info(e)
            return OzonItem(url=url, status=Status.OUT_OF_STOCK)

        _, redirect_sku = OzonParser.extract_url_parts(response_price.url)

        response_quantity = requests.post(
            url=OzonParser._ADD_TO_CART_URL,
            data=json.dumps([{"id": redirect_sku, "quantity": 2000}]),
            headers=OzonParser._HEADERS,
            impersonate="chrome116",
            cookies={
                "__Secure-refresh-token": "7.0.SYkxK0SbQDmpHVoYJlekhQ.27.AerWva9-O_8-OHJlQRm3IhRExoT2P57SRnrAQ5OzeSN4JU7mVOlUx4eEnV50rLM_DA..20250402222635.j1sYDuPdWbOofvVcWx8P9mh8MwU4sfgSUy--fVLNszc.14bcdb1c048d6dded",
                "abt_data": "7.mnQH91CIDBEENuO5RR0CsCgjWPdOFL0TYfxZCbi-nG-PvBc8Lcy7e7nkYO4CnQfrpjmPopyMaoe3jpFVDGjMXWeQLQ5SdULAQ774fJdLRMy92TeEjzgJNrNwy0I14ba5QvzflpQZaQROoO1Col2e5vDce_Ry_ZZPBvB8OpjE-pMZLGlDRt74QEuxFSXOscVUdj61tQmM4T27gyTKVJ5IgJFrKzHksBQTsNhgIeJtBWMcPkZt58hf2zCf4_wQfCDUn9GebtiLghqUkJfk4o-vDCN8OtBqqOlmcSlcQc7KYQyTnZn15m-A2XyZnICnbCycRif6HVrYmmzz5KQ1XN84mFiI187fSfFLoYmu43dxuaG2zZNu1LT-VUVwa49lIEU1JFh4DkVaU0suwboT3J4EZypUPM1fTQ4mwDlmD0QTXVHvYE0y4DEQdrPJYyfx1sMt4yWhFHQAtx91WYGAIT9qNl5BunWS_VmHphnVjvb60scqJEJKGAhQOPEFK4oK9G2CV36Unylj7431p5O3VTgB3VxMudX0Qx4x2RW5droIPD9fDC780k54fs6TSf69t1C7ab_PJELJ2NQDrNgrWd3P7f9Suh_K_H6P",
            },
            proxies={"https": proxy_url},
        )

        if response_quantity.status_code != 200:
            logger.debug(
                f"Got error response from Ozon cart: {response_quantity.status_code}"
            )
            return None

        quantity = OzonParser._get_quantity(response_quantity.json())

        item = OzonItem(
            url=url,
            quantity=quantity,
            price=price,
            status=Status.OK,
            green_price=green_price,
        )

        response_quantity = requests.post(
            url=OzonParser._ADD_TO_CART_URL,
            data=json.dumps([{"id": redirect_sku}]),
            headers=OzonParser._HEADERS,
            impersonate="chrome116",
            cookies={
                "__Secure-refresh-token": "7.0.SYkxK0SbQDmpHVoYJlekhQ.27.AerWva9-O_8-OHJlQRm3IhRExoT2P57SRnrAQ5OzeSN4JU7mVOlUx4eEnV50rLM_DA..20250402222635.j1sYDuPdWbOofvVcWx8P9mh8MwU4sfgSUy--fVLNszc.14bcdb1c048d6dded",
                "abt_data": "7.mnQH91CIDBEENuO5RR0CsCgjWPdOFL0TYfxZCbi-nG-PvBc8Lcy7e7nkYO4CnQfrpjmPopyMaoe3jpFVDGjMXWeQLQ5SdULAQ774fJdLRMy92TeEjzgJNrNwy0I14ba5QvzflpQZaQROoO1Col2e5vDce_Ry_ZZPBvB8OpjE-pMZLGlDRt74QEuxFSXOscVUdj61tQmM4T27gyTKVJ5IgJFrKzHksBQTsNhgIeJtBWMcPkZt58hf2zCf4_wQfCDUn9GebtiLghqUkJfk4o-vDCN8OtBqqOlmcSlcQc7KYQyTnZn15m-A2XyZnICnbCycRif6HVrYmmzz5KQ1XN84mFiI187fSfFLoYmu43dxuaG2zZNu1LT-VUVwa49lIEU1JFh4DkVaU0suwboT3J4EZypUPM1fTQ4mwDlmD0QTXVHvYE0y4DEQdrPJYyfx1sMt4yWhFHQAtx91WYGAIT9qNl5BunWS_VmHphnVjvb60scqJEJKGAhQOPEFK4oK9G2CV36Unylj7431p5O3VTgB3VxMudX0Qx4x2RW5droIPD9fDC780k54fs6TSf69t1C7ab_PJELJ2NQDrNgrWd3P7f9Suh_K_H6P",
            },
            proxies={"https": proxy_url},
        )

        logger.info(f"Got item: {item}")
        return item


def test_run():
    print(OzonParser._get_item(input("Enter url: ")))


if __name__ == "__main__":
    test_run()
