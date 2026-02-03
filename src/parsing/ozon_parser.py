from __future__ import annotations

import json
import random
import re
import threading
import time
from typing import Any

from the_retry import retry
from tls_client import Session

from src.models import Status, OzonUrls, OzonItem
from src.parsing import ItemParser
from src.parsing.exceptions import OutOfStockException
from src.parsing.session_parser import SessionData, get_session
from src.utils import logger

# If the new session still returns 403, wait this long before fetching another session.
DELAY_AFTER_FAILED_SESSION_SEC = 60 * 60  # 60 minutes

# List of TLS client identifiers to rotate through for fingerprint diversity
# Type ignored because tls_client type stubs don't include newer Chrome versions
TLS_CLIENT_IDENTIFIERS: list[Any] = [
    "chrome_120",
    "chrome_119",
    "chrome_118",
    "chrome_117",
    "chrome_116",
]


class OzonParser(ItemParser):
    _BASE_URL = r"https://www.ozon.ru/api/composer-api.bx/"
    _PRODUCT_URL = _BASE_URL + r"page/json/v2?url=%2Fproduct%2F"
    _ADD_TO_CART_URL = _BASE_URL + r"_action/addToCart"

    # TLS client session for requests - now managed dynamically
    _tls_session: Session | None = None
    _tls_client_index = 0

    # Class-level session management (cookies/headers from Selenium)
    _session: SessionData | None = None
    _session_lock = threading.Lock()
    _success_since_refresh = True

    @classmethod
    def _create_tls_session(cls) -> Session:
        """Create a fresh TLS session with rotating client identifier."""
        client_id = TLS_CLIENT_IDENTIFIERS[cls._tls_client_index % len(TLS_CLIENT_IDENTIFIERS)]
        cls._tls_client_index += 1
        logger.debug(f"Creating new TLS session with client identifier: {client_id}")
        return Session(
            client_identifier=client_id,
            random_tls_extension_order=True,
        )

    @classmethod
    def _get_tls_session(cls) -> Session:
        """Get or create TLS session."""
        if cls._tls_session is None:
            cls._tls_session = cls._create_tls_session()
        return cls._tls_session

    @classmethod
    def _get_session(cls) -> SessionData:
        """Get current session or create a new one if none exists."""
        with cls._session_lock:
            if cls._session is None:
                cls._session = get_session()
            return cls._session

    @classmethod
    def _refresh_session_on_403(cls) -> None:
        """Refresh session when 403 is encountered. Thread-safe with delay if no success."""
        with cls._session_lock:
            need_delay = not cls._success_since_refresh

        if need_delay:
            logger.warning(
                f"Previous session had no success, waiting {DELAY_AFTER_FAILED_SESSION_SEC // 60} minutes before refresh"
            )
            time.sleep(DELAY_AFTER_FAILED_SESSION_SEC)

        logger.warning("Refreshing Ozon session due to 403 error")
        
        # Recreate TLS session to clear stale connection state
        logger.info("Recreating TLS client session...")
        cls._tls_session = cls._create_tls_session()
        
        new_session = get_session()

        with cls._session_lock:
            cls._session = new_session
            cls._success_since_refresh = False

        logger.info("Session refreshed successfully")

    @classmethod
    def _mark_success(cls) -> None:
        """Mark that a successful request was made with the current session."""
        with cls._session_lock:
            cls._success_since_refresh = True

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
            def get_item(cls_or_url, url: str = None):
                # Support both static methods (url only) and classmethods (cls, url)
                if url is None:
                    actual_url = cls_or_url
                    args = (actual_url,)
                else:
                    actual_url = url
                    args = (cls_or_url, url)

                try:
                    item = func(*args)
                except Exception as e:
                    if raise_exception:
                        raise e

                    item = OzonItem(url=actual_url, status=Status.PARSING_ERROR)
                return item

            return get_item

        return decorator

    @classmethod
    @return_error_item_on_exception()
    @retry(attempts=3, backoff=5, exponential_backoff=True)
    def _get_item(cls, url: str) -> OzonItem | None:
        logger.info(f"Getting item from: {url}...")

        url_part, sku = cls.extract_url_parts(url)

        if url_part is None or sku is None:
            logger.debug(f"Wrong url passed ({url})")
            return None

        proxy_url = None
        # proxy_url = os.environ.get("PROXY_URL")
        session = cls._get_session()
        tls_session = cls._get_tls_session()

        response_price = tls_session.get(
            url=cls._PRODUCT_URL + url_part,
            headers=session.headers,
            cookies=session.cookies,
            proxy=proxy_url,
        )

        if response_price.status_code == 403:
            logger.warning("Got 403 response, refreshing session...")
            cls._refresh_session_on_403()
            raise Exception("Session expired (403), retrying with new session")

        if response_price.status_code >= 500:
            logger.warning(f"Server error ({response_price.text}), retrying...")
            raise Exception("Server error")

        if response_price.status_code == 302:
            logger.info("Item out of stock")
            return OzonItem(url=url, status=Status.OUT_OF_STOCK)

        if response_price.status_code != 200:
            logger.warning(
                f"Got error response from Ozon prices: {response_price.status_code}"
            )
            return OzonItem(url=url, status=Status.PARSING_ERROR)

        cls._mark_success()

        try:
            price, green_price = cls._get_prices(response_price.json())
        except OutOfStockException as e:
            logger.info(e)
            return OzonItem(url=url, status=Status.OUT_OF_STOCK)

        _, redirect_sku = cls.extract_url_parts(response_price.url)

        response_quantity = tls_session.post(
            url=cls._ADD_TO_CART_URL,
            data=json.dumps([{"id": redirect_sku, "quantity": 2000}]),
            headers=session.headers,
            cookies=session.cookies,
            proxy=proxy_url,
        )

        if response_quantity.status_code == 403:
            logger.warning("Got 403 response on cart request, refreshing session...")
            cls._refresh_session_on_403()
            raise Exception("Session expired (403), retrying with new session")

        if response_quantity.status_code >= 500:
            logger.warning(f"Server error ({response_quantity.text}), retrying...")
            raise Exception("Server error")

        if response_quantity.status_code != 200:
            logger.warning(
                f"Got error response from Ozon cart: {response_quantity.status_code}"
            )
            return OzonItem(url=url, status=Status.PARSING_ERROR)

        quantity = cls._get_quantity(response_quantity.json(), redirect_sku)

        item = OzonItem(
            url=url,
            quantity=quantity,
            price=price,
            status=Status.OK,
            green_price=green_price,
        )

        for cart_item in response_quantity.json()["cart"]["cartItems"]:
            logger.debug(f"Remove item from cart: {cart_item}")
            tls_session.post(
                url=cls._ADD_TO_CART_URL,
                data=json.dumps([{"id": cart_item["id"]}]),
                headers=session.headers,
                cookies=session.cookies,
                proxy=proxy_url,
            )

        logger.info(f"Got item: {item}")
        return item


def test_run():
    print(OzonParser._get_item(input("Enter url: ")))


if __name__ == "__main__":
    test_run()
