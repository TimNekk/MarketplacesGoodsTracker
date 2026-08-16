from __future__ import annotations

import re
import threading
import time

from requests import Session
from the_retry import retry

from src.models import Status, WildberriesUrls, WildberriesItem
from src.parsing import ItemParser
from src.parsing.session_parser import SessionData
from src.parsing.wildberries_session_parser import get_session
from src.utils import logger

# If the new session still returns an auth error, wait this long before fetching another session.
DELAY_AFTER_FAILED_SESSION_SEC = 60 * 60  # 60 minutes


class WildberriesParser(ItemParser):
    NO_SALE_AMOUNT = 0
    SALE_AMOUNT = 30
    DESTINATION = -1257786
    HEADERS = {
        'accept': '*/*',
        'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'deviceid': 'site_9aac2961cc744827a5d16b84c6c004e3',
        'priority': 'u=1, i',
        'referer': 'https://www.wildberries.ru/catalog/14922314/detail.aspx',
        'sec-ch-ua': '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'x-requested-with': 'XMLHttpRequest',
        'x-spa-version': '14.19.3',
    }

    # Class-level session management (cookies/headers from Camoufox)
    _session: SessionData | None = None
    _session_lock = threading.Lock()
    _refresh_lock = threading.Lock()
    _success_since_refresh = True

    @classmethod
    def _get_session(cls) -> SessionData:
        """Get current session or create a new one if none exists."""
        with cls._session_lock:
            if cls._session is None:
                cls._session = get_session()
            return cls._session

    @classmethod
    def _refresh_session_on_failure(cls) -> None:
        """Refresh session when the token is rejected. Thread-safe with delay if no success."""
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

            logger.warning("Refreshing Wildberries session due to auth error")

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

    @classmethod
    def get_items(cls, urls: WildberriesUrls) -> list[WildberriesItem]:
        items = []

        for url in urls:
            logger.info(f"Getting item from \"{url}\"...")

            code = re.findall(r"catalog\/(\d+)", url)[0]

            try:
                quantity, price, status = cls._get_item_values(code, cls.SALE_AMOUNT)
            except ValueError as e:
                logger.warning(e)
                continue

            item = WildberriesItem(
                url=url,
                quantity=quantity,
                sale_price=int(price * 0.98),
                no_sale_price=int(price),
                status=status,
            )
            items.append(item)

            logger.info(f"Got item: {item}")

        return items

    @classmethod
    @retry(attempts=3, backoff=5, exponential_backoff=True)
    def _get_item_values(cls, code: str, sale_amount: int) -> tuple[int, int, Status]:
        session_data = cls._get_session()

        card_url = "https://www.wildberries.ru/__internal/u-card/cards/v4/detail"
        params = {
            "nm": code,
            "spp": sale_amount,
            "dest": cls.DESTINATION,
        }
        with Session() as session:
            response = session.get(
                card_url,
                params=params,
                headers={**cls.HEADERS, **session_data.headers},
                cookies=session_data.cookies,
            )

        if response.status_code in (401, 403, 498):
            logger.warning(f"Got {response.status_code} response, refreshing session...")
            cls._refresh_session_on_failure()
            raise Exception(f"Session expired ({response.status_code}), retrying with new session")

        if response.status_code >= 500:
            logger.warning(f"Server error ({response.text}), retrying...")
            raise Exception("Server error")

        try:
            response_json = response.json()
        except Exception:
            logger.warning(f"Failed to parse response: {response.status_code} {response.text}, retrying...")
            raise Exception("Failed to parse response")

        if not response_json.get("products"):
            raise ValueError(f"Item with code \"{code}\" not found")

        cls._mark_success()

        good = response_json.get("products", [])[0]
        price = int(good.get("sizes", [])[0].get("price", {}).get("product", 0) / 100)

        quantity = good.get("totalQuantity")
        status = Status.OK if quantity > 0 else Status.OUT_OF_STOCK

        return quantity, price, status


def test_run():
    print(WildberriesParser.get_items(["https://www.wildberries.ru/catalog/74441434/detail.aspx"]))


if __name__ == '__main__':
    test_run()
