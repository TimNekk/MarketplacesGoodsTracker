import json
import re
from collections.abc import Iterable, Collection
from time import sleep

from selenium.common.exceptions import InvalidArgumentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.models import Item, Status
from src.parsing.exceptions import WrongUrlException, OutOfStockException
from src.parsing.item_parser import ItemParser
from src.parsing.selenium_parser import SeleniumParser
from src.utils import logger, QuotEncoder


class OzonParser(ItemParser, SeleniumParser):
    def __init__(self) -> None:
        self._cart = "https://www.ozon.ru/cart"

    def add_to_cart(self, url: str) -> int:
        logger.debug(f"Adding to cart...")

        try:
            logger.debug("Getting page source...")
            self._driver.get(url)
        except InvalidArgumentException:
            raise WrongUrlException(f"Wrong url passed ({url})")

        logger.debug("Checking if item is out of stock...")
        if "ozon.ru/search" in self._driver.current_url or "ozon.ru/category" in self._driver.current_url:
            raise OutOfStockException("Item is out of stock")

        logger.debug("Clicking add to cart button...")
        try:
            WebDriverWait(self._driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Добавить в корзину']"))).click()
        except TimeoutException:
            WebDriverWait(self._driver, 3).until(EC.element_to_be_clickable((By.XPATH, "(//span[text()='В корзину'])[2]"))).click()

    def get_cart(self) -> list[Item]:
        logger.debug("Getting cart...")

        json_string = None
        while True:
            self._driver.get(self._cart)

            page_source = self._driver.page_source

            logger.debug("Parsing page source...")
            try:
                json_string = str(re.findall(r"'({.*?trackingPayloads.*?})'", page_source)[0])
            except IndexError:
                sleep(5)
                continue
            break

        json_string = json_string.replace("\\\\", "\\")
        json_string = re.sub(r"\\n", "", json_string)

        logger.debug("Parsing json...")
        data = json.loads(json_string, cls=QuotEncoder)

        return list(self._parse_cart_json(data))

    @staticmethod
    def _parse_cart_json(response_json) -> Iterable[Item]:
        logger.debug("Parsing cart json...")
        items_json = response_json.get("shared").get("itemsTrackingInfo")

        items: list[Item] = []
        for item_json in items_json:
            item = Item(
                quantity=item_json.get("stockMaxQty"),
                price=item_json.get("finalPrice"),
                status=Status.OK
            )
            items.append(item)

        return items

    @staticmethod
    def get_items(urls: list[str]) -> list[Item]:
        items = []
        for url in urls:
            logger.info(f"Getting item from: {url}...")

            attempts = 0
            max_attempts = 3
            while attempts < max_attempts:
                try:
                    with OzonParser() as parser:
                        try:
                            parser.add_to_cart(url)
                        except WrongUrlException as e:
                            logger.debug(e)
                            break
                        except OutOfStockException as e:
                            logger.info(e)
                            items.append(Item(url=url, status=Status.OUT_OF_STOCK))
                            break

                        sleep(1)
                        item = parser.get_cart()[0]
                        item.url = url
                        items.append(item)

                        logger.info(f"Got item: {item}")
                        break
                except Exception as e:
                    logger.error(e)
                    attempts += 1

        return items


def test_run():
    with OzonParser() as parser:
        parser.add_to_cart(input())
        sleep(1)
        print(parser.get_cart())


if __name__ == "__main__":
    test_run()
