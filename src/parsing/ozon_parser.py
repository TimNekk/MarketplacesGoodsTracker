from __future__ import annotations

import json
import random
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

from the_retry import retry
from playwright.sync_api import BrowserContext, Page

from src.models import Status, OzonUrls, OzonItem
from src.parsing import ItemParser
from src.parsing.ozon_session_parser import (
    ENTRYPOINT_REQUEST,
    OZON_URL,
    REQUEST_TIMEOUT_MS,
    SessionData,
    headless_mode,
    open_profile,
)
from src.utils import logger

# If the new session still returns 403, wait this long before fetching another session.
DELAY_AFTER_FAILED_SESSION_SEC = 60 * 60  # 60 minutes

# Runs inside the authenticated page via page.evaluate, so requests carry the
# real Firefox TLS/HTTP2 stack and headers instead of a separately spoofed
# client - Ozon's antibot blocks the latter outright even with valid cookies.
_FETCH_JS = """
async ({url, method, body}) => {
    const res = await fetch(url, {
        method,
        credentials: 'include',
        headers: body !== null ? {'Content-Type': 'application/json'} : {},
        body: body !== null ? body : undefined,
    });
    let json = null;
    try { json = await res.json(); } catch (e) {}
    return {status: res.status, url: res.url, json};
}
"""


@dataclass
class FetchResult:
    status: int
    url: str
    json: Any


class OzonBrowserSession:
    """Authenticated Camoufox page kept open for the process lifetime."""

    def __init__(self) -> None:
        self._context_cm = open_profile(headless_mode(True))
        self.context: BrowserContext = self._context_cm.__enter__()
        try:
            self.page: Page = (
                self.context.pages[0] if self.context.pages else self.context.new_page()
            )

            with self.page.expect_request(ENTRYPOINT_REQUEST, timeout=REQUEST_TIMEOUT_MS):
                self.page.goto(OZON_URL)
        except BaseException:
            self._context_cm.__exit__(None, None, None)
            raise

        if self.is_authenticated:
            logger.info(f"Got authenticated session (user id {self._user_id()})")
        else:
            logger.info("Got anonymous session; prices will be read from the cart")

    def _user_id(self) -> str:
        cookies = {c["name"]: c["value"] for c in self.context.cookies()}
        return cookies.get("__Secure-user-id", "0")

    @property
    def is_authenticated(self) -> bool:
        cookies = {c["name"]: c["value"] for c in self.context.cookies()}
        return SessionData(cookies=cookies, headers={}).is_authenticated

    def fetch(self, url: str, method: str = "GET", body: str | None = None) -> FetchResult:
        result = self.page.evaluate(_FETCH_JS, {"url": url, "method": method, "body": body})
        return FetchResult(status=result["status"], url=result["url"], json=result["json"])

    def close(self) -> None:
        self._context_cm.__exit__(None, None, None)


class OzonParser(ItemParser):
    _BASE_URL = r"https://www.ozon.ru/api/composer-api.bx/"
    _PRODUCT_URL = _BASE_URL + r"page/json/v2?url=%2Fproduct%2F"
    _CART_URL = _BASE_URL + r"page/json/v2?url=%2Fcart"
    _ADD_TO_CART_URL = _BASE_URL + r"_action/addToCart"

    _session: OzonBrowserSession | None = None
    _session_lock = threading.Lock()
    _refresh_lock = threading.Lock()
    _success_since_refresh = True

    @classmethod
    def _get_session(cls) -> OzonBrowserSession:
        """Reuse an open session or recreate it after the browser closes."""
        with cls._session_lock:
            if cls._session is not None and cls._session.page.is_closed():
                logger.warning("Ozon browser page closed, recreating session")
                old_session = cls._session
                cls._session = None
                old_session.close()
            if cls._session is None:
                cls._session = OzonBrowserSession()
            return cls._session

    @classmethod
    def _refresh_session_on_403(cls) -> None:
        """Refresh session when 403 is encountered. Thread-safe with delay if no success."""
        with cls._session_lock:
            need_delay = not cls._success_since_refresh
            old_session = cls._session

        if need_delay:
            logger.warning(
                f"Previous session had no success, waiting {DELAY_AFTER_FAILED_SESSION_SEC // 60} minutes before refresh"
            )
            time.sleep(DELAY_AFTER_FAILED_SESSION_SEC)

        with cls._refresh_lock:
            # Another thread may have already refreshed while we waited
            with cls._session_lock:
                if cls._session is not old_session:
                    logger.info("Session already refreshed by another thread, skipping")
                    return
                # A failed close or launch must not leave a closed session cached.
                cls._session = None

            logger.warning("Refreshing Ozon session due to 403 error")

            if old_session is not None:
                old_session.close()

            new_session = OzonBrowserSession()

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
    def _get_cart_prices(response: dict, sku: int) -> tuple[int, int | None]:
        for key, value in response["widgetStates"].items():
            if not key.startswith("cartSplit-"):
                continue
            for item in json.loads(value)["cartItems"]:
                if item["product"]["id"] != str(sku):
                    continue
                quantity = item["controls"]["quantity"]["current"]
                prices = {}
                for column in item["product"]["priceColumn"]:
                    if column["type"] != "prices":
                        continue
                    for element in column["prices"]["elements"]:
                        kind = element.get("testInfo", {}).get("automatizationId")
                        if kind not in ("cart-split-item-price", "cart-split-item-ozon-card-price"):
                            continue
                        total = OzonParser.price_to_number(element["price"][0]["text"])
                        # Cart prices are line totals, including every requested unit.
                        price, remainder = divmod(total, quantity)
                        if remainder or price <= 0:
                            raise ValueError("Invalid cart unit price")
                        prices[kind] = price
                return prices["cart-split-item-price"], prices.get("cart-split-item-ozon-card-price")
        raise ValueError("Product price not found in cart")

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

        session = cls._get_session()

        response_price = session.fetch(cls._PRODUCT_URL + url_part)

        if response_price.status == 403:
            logger.warning("Got 403 response, refreshing session...")
            cls._refresh_session_on_403()
            raise Exception("Session expired (403), retrying with new session")

        if response_price.status >= 500:
            logger.warning(f"Server error ({response_price.status}), retrying...")
            raise Exception("Server error")

        if response_price.status != 200:
            logger.warning(f"Got error response from Ozon prices: {response_price.status}")
            return OzonItem(url=url, status=Status.PARSING_ERROR)

        # A 200 whose body isn't the product JSON (redirected to a plain page
        # instead) means the listing itself is gone/unavailable.
        if response_price.json is None:
            logger.info("Item out of stock")
            return OzonItem(url=url, status=Status.OUT_OF_STOCK)

        cls._mark_success()

        if not any(key.startswith("webPrice-") for key in response_price.json["widgetStates"]):
            logger.info("Item out of stock")
            return OzonItem(url=url, status=Status.OUT_OF_STOCK)

        _, redirect_sku = cls.extract_url_parts(response_price.url)
        redirect_sku = redirect_sku or sku

        response_quantity = session.fetch(
            cls._ADD_TO_CART_URL,
            method="POST",
            body=json.dumps([{"id": redirect_sku, "quantity": 2000}]),
        )

        if response_quantity.status == 403:
            logger.warning("Got 403 response on cart request, refreshing session...")
            cls._refresh_session_on_403()
            raise Exception("Session expired (403), retrying with new session")

        if response_quantity.status >= 500:
            logger.warning(f"Server error ({response_quantity.status}), retrying...")
            raise Exception("Server error")

        if response_quantity.status != 200 or response_quantity.json is None:
            logger.warning(f"Got error response from Ozon cart: {response_quantity.status}")
            return OzonItem(url=url, status=Status.PARSING_ERROR)

        cleanup_error = None
        try:
            quantity = cls._get_quantity(response_quantity.json, redirect_sku)
            response_cart = session.fetch(cls._CART_URL)
        finally:
            try:
                session.fetch(
                    cls._ADD_TO_CART_URL,
                    method="POST",
                    body=json.dumps([{"id": redirect_sku}]),
                )
            except Exception as e:
                logger.warning(f"Failed to remove item from cart: {e}")
                cleanup_error = e

        if response_cart.status == 403:
            cls._refresh_session_on_403()
            raise Exception("Session expired (403), retrying with new session")
        if cleanup_error is not None:
            raise cleanup_error
        if response_cart.status >= 500:
            raise Exception("Server error fetching cart prices")
        if response_cart.status != 200 or response_cart.json is None:
            return OzonItem(url=url, status=Status.PARSING_ERROR)

        price, green_price = cls._get_cart_prices(response_cart.json, redirect_sku)

        item = OzonItem(
            url=url,
            quantity=quantity,
            price=price,
            status=Status.OK,
            green_price=green_price,
        )

        logger.info(f"Got item: {item}")
        return item


def test_run():
    print(OzonParser._get_item(input("Enter url: ")))


if __name__ == "__main__":
    test_run()
