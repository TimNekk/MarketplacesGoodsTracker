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
        logger.info(f"Adding to cart: {url}...")

        try:
            logger.debug("Getting page source...")
            self._driver.get(url)
        except InvalidArgumentException:
            raise WrongUrlException(f"Wrong url passed ({url})")

        logger.debug("Checking if item is out of stock...")
        if "ozon.ru/search" in self._driver.current_url:
            raise OutOfStockException("Item is out of stock")

        logger.debug("Clicking add to cart button...")
        try:
            WebDriverWait(self._driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Добавить в корзину']"))).click()
        except TimeoutException:
            WebDriverWait(self._driver, 3).until(EC.element_to_be_clickable((By.XPATH, "(//span[text()='В корзину'])[2]"))).click()

        sleep(1)
        card_count = int(list(filter(lambda element: element.text.isdigit(), self._driver.find_elements(By.CLASS_NAME, "tsCaptionBold")))[-1].text)
        return card_count

    def get_cart(self) -> Collection[Item]:
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

        logger.debug("Getting cart id...")
        cart_id: str = re.findall(r"group_in_cart(.*?):&quot;(.*?)&quot;}", page_source)[0][1]
        return list(self._parse_cart_json(data, cart_id))

    @staticmethod
    def _parse_cart_json(response_json, cart_id: str) -> Iterable[Item]:
        logger.debug("Parsing cart json...")

        try:
            cart_json: str = response_json.get("trackingPayloads").get(cart_id)
        except AttributeError:
            cart_json = response_json.get("state").get("trackingPayloads").get(cart_id)

        items_json = json.loads(cart_json).get("items")

        items: list[Item] = []
        for item_json in items_json:
            item = Item(
                id=str(item_json.get("sku")),
                quantity=item_json.get("maxQuantity"),
                price=item_json.get("finalPrice"),
                status=Status.OK
            )
            items.append(item)

        return items

    @staticmethod
    def get_item_id_from_url(url: str) -> str:
        return re.findall(r"product(.*)-(\d+)\/", url)[0][1]

    @staticmethod
    def get_items(urls: list[str]) -> list[Item]:
        items = []
        total_added = 0
        cart_amount_old = 0
        with OzonParser() as parser:
            for url in urls:
                try:
                    attempts = 3
                    while attempts:
                        cart_amount = parser.add_to_cart(url)

                        if cart_amount != cart_amount_old + 1:
                            attempts -= 1
                            continue

                        cart_amount_old = cart_amount
                        break

                    if attempts == 0:
                        raise OutOfStockException("Item is out of stock")

                    total_added += 1
                    logger.info(f"Added! (Total: {total_added})")
                except WrongUrlException as e:
                    logger.debug(e)
                except OutOfStockException as e:
                    logger.info(e)
                    total_added += 1
                    logger.info(f"Added! (Total: {total_added})")
                    items.append(Item(id=parser.get_item_id_from_url(url), status=Status.OUT_OF_STOCK))

            items += parser.get_cart()

        logger.info("Done parsing!")
        return items


def test_run():
    with OzonParser() as parser:
        parser.add_to_cart(input())
        sleep(1)
        print(parser.get_cart())


if __name__ == "__main__":
    test_run()
