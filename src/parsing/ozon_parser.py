from __future__ import annotations

import json
import os
import random
import re
import time

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
    def get_items(urls: OzonUrls) -> list[OzonItem]:
        items = []

        for url in urls:
            item = None
            if url != "":
                item = OzonParser._get_item(url)

            if item:
                items.append(item)

            time.sleep(random.randint(4, 6) + random.random() * 2)

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
                "abt_data": "7.xvuoRpz3AF0qOZLW3RpN3FEgCP08Hp_XOZfonfd8ewg3gspc45RSo5Fw24IoC5SdIEKGh7LDwsjqIGn79QBU9GJaLkJJo1MMo7gSlQMGg2h3sLhC4Kwx4rkXEIeufGEcf4a40v5-wcegNqrF7U9Nj1jxGJd1GZpo1BZtnSSnRwUGxPpSLIA-xNeSoc8mCJxvbVNFtT2zqEOiZj9peNQHm_kEJxtJUvPuSpZ6-RiVzxzYQDW2duuTJknC5MwLxzRXrgGdZ2s55n4vhVj2n_U6sO_yrDaLc8G8d11NCCodx5HJYXA0eH9iAkPbC9lFQqdgaSI_k3DaMBlsbowyxguvJKNqTEmhUXmjd2xVGkaNxo9Qj5UFu2kUiVn5QcgSPJ2i15iMjZiiRNsVjs_MRQf6yoX7vnxMpbkfWmkxPpjAzvDa5NWPuoyQwoMn_8rRKgNYDwv2oep72clKuSY7Z6tRcoGAYu9-vG0lq9YpeXu13mY3YA9_ga2UgKC-5jpC3YoxOoC4RR8kdo9t6ZHT9ZhG21g",
                "__Secure-refresh-token": "7.76618151.X93AXBEcS3G-_i_dwjpy0Q.22.AUNCdCn3Pp7xcLbbOUKM49HDlvbiHDPILWwV7lu3-6FE1emejS_nOFgVp3o3KhIozlqJQn3L_YAvzw78SAEySTU.20210922142247.20250409150825.nzLKfzDjAaYMXsNoloQXJjlq027_SB0vAVeHbG9xPJw.1b3b93e55e6ba8a9e",
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
                "abt_data": "7.xvuoRpz3AF0qOZLW3RpN3FEgCP08Hp_XOZfonfd8ewg3gspc45RSo5Fw24IoC5SdIEKGh7LDwsjqIGn79QBU9GJaLkJJo1MMo7gSlQMGg2h3sLhC4Kwx4rkXEIeufGEcf4a40v5-wcegNqrF7U9Nj1jxGJd1GZpo1BZtnSSnRwUGxPpSLIA-xNeSoc8mCJxvbVNFtT2zqEOiZj9peNQHm_kEJxtJUvPuSpZ6-RiVzxzYQDW2duuTJknC5MwLxzRXrgGdZ2s55n4vhVj2n_U6sO_yrDaLc8G8d11NCCodx5HJYXA0eH9iAkPbC9lFQqdgaSI_k3DaMBlsbowyxguvJKNqTEmhUXmjd2xVGkaNxo9Qj5UFu2kUiVn5QcgSPJ2i15iMjZiiRNsVjs_MRQf6yoX7vnxMpbkfWmkxPpjAzvDa5NWPuoyQwoMn_8rRKgNYDwv2oep72clKuSY7Z6tRcoGAYu9-vG0lq9YpeXu13mY3YA9_ga2UgKC-5jpC3YoxOoC4RR8kdo9t6ZHT9ZhG21g",
                "__Secure-refresh-token": "7.76618151.X93AXBEcS3G-_i_dwjpy0Q.22.AUNCdCn3Pp7xcLbbOUKM49HDlvbiHDPILWwV7lu3-6FE1emejS_nOFgVp3o3KhIozlqJQn3L_YAvzw78SAEySTU.20210922142247.20250409150825.nzLKfzDjAaYMXsNoloQXJjlq027_SB0vAVeHbG9xPJw.1b3b93e55e6ba8a9e",
            },
            proxies={"https": proxy_url},
        )

        logger.info(f"Got item: {item}")
        return item


def test_run():
    print(OzonParser._get_item(input("Enter url: ")))


if __name__ == "__main__":
    test_run()
