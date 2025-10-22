from __future__ import annotations

import json
import os
import random
import re
import time

from the_retry import retry
from curl_cffi import requests

from src.models import Status, OzonUrls, OzonItem
from src.parsing import ItemParser
from src.parsing.exceptions import OutOfStockException
from src.utils import logger


class OzonParser(ItemParser):
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 YaBrowser/24.1.0.0 Safari/537.36",
    }
    _COOKIES = {
        "__Secure-ab-group": "16",
        "__Secure-user-id": "0",
        "__Secure-ext_xcid": "75f41c38476494903ece4a7fb84e264b",
        "abt_data": "7.Zmt0ppgkkWL-oyNRYWudH69Z9WOcOu41XdtO2uf5-Iai_lRUCWJNotSP9tGepb51I0aYmrTUAXOibW5USNWRodIe4TuSVBPcOr7ixOWX2Dtv7dbH16TqI1D4BzDGHsAfUKD1nvamBDjWTRThXucFYWXtPbhVO-V1IFpCZoILVLJkLa2xiRmi5FOa1ADUjaFF_7YmfhzHDMAGwZyt8_FkvVj3VajEq7REeXCNeblNOG5b7C_mU7MzPB9AGx57whO7N73tXnz31UHsMHkxigJoZZe0tIQqcjOmQCAzle-4W7tseC4hMcRQH9w8jJQAI5lQDM0QfgZ3O5mpusC0k-ZClWKzDLS7ZR5SWICSxpx2fWr6Ik8Dk-XBeoqO7FgRSU7LPA18FH-_uR0pQOOubjwmGQRBhPj2C7RPsgBqb3UECywEaiPfgcyihg8gBV5Rpiz31bbK27Pmc6_odpaiBesK4dtom98XzW-hwoaMrbDHhYnawYodoseAHctDxTWpMeTKbAEzJyfu8CBOoAkCd3kk1xBqtYkfBd209SdOdVzRhXf2GUDXmlCCOQhpBZPVJfCcfRahzT6rHAuCDi3OyrMKTYTVbfOJr_0-B1GUNc-sp67qwXn1xqetuR8xqzI",
        "__Secure-ETC": "c6c26fbb9de141f371b3e40e14b2d60e",
        "xcid": "2d7192c85af12ed6ceca3073d37a3336",
        "__Secure-access-token": "9.0.D1S3M32LRA2SX6FhHbpvLQ.16.ATHnVxzkq4Mc8esWZXw6SOVi0mDWVjxFgCIJxos8txSHcpPiMxXt8auIATDB2U5CPN0MBdhxMrNMAkXxtSYowKIab9T7E59a1RrdiOoAD0W6..20251021192342.LtYmA1OgEGkY1BJGGgpolgCfiYV-OSTJehiosyBR_xc.17f056fc47e461702",
        "__Secure-refresh-token": "9.0.D1S3M32LRA2SX6FhHbpvLQ.16.ATHnVxzkq4Mc8esWZXw6SOVi0mDWVjxFgCIJxos8txSHcpPiMxXt8auIATDB2U5CPN0MBdhxMrNMAkXxtSYowKIab9T7E59a1RrdiOoAD0W6..20251021192342.T-PPV7WytZgAmRwjnH6r11GkqiuAtjstNLM8urMjjL0.180dbc276488a37d1",
        "rfuid": "LTE5NTAyNjU0NzAsMTI0LjA0MzQ3NTI3NTE2MDc0LDgxMTQ1MjA1NSwtMSwxNjQ5ODY0OTA4LFczc2libUZ0WlNJNklsQkVSaUJXYVdWM1pYSWlMQ0prWlhOamNtbHdkR2x2YmlJNklsQnZjblJoWW14bElFUnZZM1Z0Wlc1MElFWnZjbTFoZENJc0ltMXBiV1ZVZVhCbGN5STZXM3NpZEhsd1pTSTZJbUZ3Y0d4cFkyRjBhVzl1TDNCa1ppSXNJbk4xWm1acGVHVnpJam9pY0dSbUluMHNleUowZVhCbElqb2lkR1Y0ZEM5d1pHWWlMQ0p6ZFdabWFYaGxjeUk2SW5Ca1ppSjlYWDBzZXlKdVlXMWxJam9pUTJoeWIyMWxJRkJFUmlCV2FXVjNaWElpTENKa1pYTmpjbWx3ZEdsdmJpSTZJbEJ2Y25SaFlteGxJRVJ2WTNWdFpXNTBJRVp2Y20xaGRDSXNJbTFwYldWVWVYQmxjeUk2VzNzaWRIbHdaU0k2SW1Gd2NHeHBZMkYwYVc5dUwzQmtaaUlzSW5OMVptWnBlR1Z6SWpvaWNHUm1JbjBzZXlKMGVYQmxJam9pZEdWNGRDOXdaR1lpTENKemRXWm1hWGhsY3lJNkluQmtaaUo5WFgwc2V5SnVZVzFsSWpvaVEyaHliMjFwZFcwZ1VFUkdJRlpwWlhkbGNpSXNJbVJsYzJOeWFYQjBhVzl1SWpvaVVHOXlkR0ZpYkdVZ1JHOWpkVzFsYm5RZ1JtOXliV0YwSWl3aWJXbHRaVlI1Y0dWeklqcGJleUowZVhCbElqb2lZWEJ3YkdsallYUnBiMjR2Y0dSbUlpd2ljM1ZtWm1sNFpYTWlPaUp3WkdZaWZTeDdJblI1Y0dVaU9pSjBaWGgwTDNCa1ppSXNJbk4xWm1acGVHVnpJam9pY0dSbUluMWRmU3g3SW01aGJXVWlPaUpOYVdOeWIzTnZablFnUldSblpTQlFSRVlnVm1sbGQyVnlJaXdpWkdWelkzSnBjSFJwYjI0aU9pSlFiM0owWVdKc1pTQkViMk4xYldWdWRDQkdiM0p0WVhRaUxDSnRhVzFsVkhsd1pYTWlPbHQ3SW5SNWNHVWlPaUpoY0hCc2FXTmhkR2x2Ymk5d1pHWWlMQ0p6ZFdabWFYaGxjeUk2SW5Ca1ppSjlMSHNpZEhsd1pTSTZJblJsZUhRdmNHUm1JaXdpYzNWbVptbDRaWE1pT2lKd1pHWWlmVjE5TEhzaWJtRnRaU0k2SWxkbFlrdHBkQ0JpZFdsc2RDMXBiaUJRUkVZaUxDSmtaWE5qY21sd2RHbHZiaUk2SWxCdmNuUmhZbXhsSUVSdlkzVnRaVzUwSUVadmNtMWhkQ0lzSW0xcGJXVlVlWEJsY3lJNlczc2lkSGx3WlNJNkltRndjR3hwWTJGMGFXOXVMM0JrWmlJc0luTjFabVpwZUdWeklqb2ljR1JtSW4wc2V5SjBlWEJsSWpvaWRHVjRkQzl3WkdZaUxDSnpkV1ptYVhobGN5STZJbkJrWmlKOVhYMWQsV3lKeWRTMVNWU0pkLDAsMSwwLDI0LDIzNzQxNTkzMCw4LDIyNzEyNjUyMCwwLDEsMCwtNDkxMjc1NTIzLFIyOXZaMnhsSUVsdVl5NGdUbVYwYzJOaGNHVWdSMlZqYTI4Z1YybHVNeklnTlM0d0lDaFhhVzVrYjNkeklFNVVJREV3TGpBN0lGZHBialkwT3lCNE5qUXBJRUZ3Y0d4bFYyVmlTMmwwTHpVek55NHpOaUFvUzBoVVRVd3NJR3hwYTJVZ1IyVmphMjhwSUVOb2NtOXRaUzh4TkRFdU1DNHdMakFnVTJGbVlYSnBMelV6Tnk0ek5pQXlNREF6TURFd055Qk5iM3BwYkd4aCxleUpqYUhKdmJXVWlPbnNpWVhCd0lqcDdJbWx6U1c1emRHRnNiR1ZrSWpwbVlXeHpaU3dpU1c1emRHRnNiRk4wWVhSbElqcDdJa1JKVTBGQ1RFVkVJam9pWkdsellXSnNaV1FpTENKSlRsTlVRVXhNUlVRaU9pSnBibk4wWVd4c1pXUWlMQ0pPVDFSZlNVNVRWRUZNVEVWRUlqb2libTkwWDJsdWMzUmhiR3hsWkNKOUxDSlNkVzV1YVc1blUzUmhkR1VpT25zaVEwRk9UazlVWDFKVlRpSTZJbU5oYm01dmRGOXlkVzRpTENKU1JVRkVXVjlVVDE5U1ZVNGlPaUp5WldGa2VWOTBiMTl5ZFc0aUxDSlNWVTVPU1U1SElqb2ljblZ1Ym1sdVp5SjlmWDE5LDY1LC0xMjg1NTUxMywxLDEsLTEsMTY5OTk1NDg4NywxNjk5OTU0ODg3LC0xNDYxNTE4MTIsMTI=",
        "abt_data": "7.r11_QkV4HxZZBwDP2fs_3WZ-Yw51F-2O6FDCRvoe7lzcV3DXx13fZJI_krhb8b1Tww9g_bd6xo2Z-cU671dXISgiLt8LJNXxhhvaAdCEptvYJrZtr9sGTnHcvDTRDQq1QBfK5e2hn0ZhHs1LU_gYAuZatvparzoMftQ5ngZJjbUa6_lcD3xMismiKJuzrIqucan1CKdycwjBkUoCmJD06cJ5NX5j1D2ZNSg13z2OLlP_D4KlVUXIISq8KnoreY4J-EO7Ka7xZhKQR88RwBdxqPRTZcbmA84F4o9xKaWy1nCR_ETvac85wIQ7AZJJXsAIkLSSX2ezwKlVJoFn6qmo9WqQ6xIVwmCazLLP0AiRGcQ_k1BIp24MYsHtc_4S0NZE0ABV06AhjstopoYKWmk7-RSLu4UlTQvJlz4pA_cbsg1rfqV7wADXHX8EzGlMDbVt-kI3gg1RqIPqL-NErdgOWoYAAzCCbkE23ZDhm3TSHaZv0BybikhpPsc9EK9QdGnzmZ835DupzVyY66OjqzkBPGuvkrRQNA_NZ9n0ZraZuCIVd8HMiW8iN1GobpM2nT8juTOotCbCymNlK-GYg9sOUCNK6C0nbP_WAHGlHqECxEoobpptuYt_D1X1rrTQD3bWEw",
        "ADDRESSBOOKBAR_WEB_CLARIFICATION": "1761067444",
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
    def _get_quantity(response: dict, sku: int) -> int:
        for cart_item in response["cart"]["cartItems"]:
            if cart_item["id"] == sku:
                return cart_item["qty"]
        raise Exception("Product not found in cart")

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
        # logger.info(f"Using proxy: {proxy_url}")

        response_price = requests.get(
            url=OzonParser._PRODUCT_URL + url_part,
            headers=OzonParser._HEADERS,
            cookies=OzonParser._COOKIES,
            impersonate="chrome",
            # proxies={"https": proxy_url},
        )

        if response_price.status_code >= 500:
            logger.warning(f"Server error ({response_price.text}), retrying...")
            raise Exception("Server error")

        if response_price.status_code != 200:
            logger.warning(
                f"Got error response from Ozon prices: {response_price.status_code}"
            )
            return OzonItem(url=url, status=Status.PARSING_ERROR)

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
            cookies=OzonParser._COOKIES,
            impersonate="chrome",
            # proxies={"https": proxy_url},
        )

        if response_quantity.status_code >= 500:
            logger.warning(f"Server error ({response_quantity.text}), retrying...")
            raise Exception("Server error")

        if response_quantity.status_code != 200:
            logger.warning(
                f"Got error response from Ozon cart: {response_quantity.status_code}"
            )
            return OzonItem(url=url, status=Status.PARSING_ERROR)

        quantity = OzonParser._get_quantity(response_quantity.json(), redirect_sku)

        item = OzonItem(
            url=url,
            quantity=quantity,
            price=price,
            status=Status.OK,
            green_price=green_price,
        )

        for cart_item in response_quantity.json()["cart"]["cartItems"]:
            logger.debug(f"Remove item from cart: {cart_item}")
            response_quantity = requests.post(
                url=OzonParser._ADD_TO_CART_URL,
                data=json.dumps([{"id": cart_item["id"]}]),
                headers=OzonParser._HEADERS,
                impersonate="chrome116",
                cookies=OzonParser._COOKIES,
                # proxies={"https": proxy_url},
            )

        logger.info(f"Got item: {item}")
        return item


def test_run():
    print(OzonParser._get_item(input("Enter url: ")))


if __name__ == "__main__":
    test_run()
