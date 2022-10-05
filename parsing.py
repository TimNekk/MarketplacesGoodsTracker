import json
import re
from collections.abc import Iterable, Collection
from time import sleep
from urllib.parse import urlsplit

import undetected_chromedriver
from selenium.common.exceptions import InvalidArgumentException, TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.chromium.options import ChromiumOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from encoder import QuotEncoder
from item import Item
from logger import logger
from status import Status


class Parser:
    def __init__(self) -> None:
        self._cart = "https://www.ozon.ru/cart"

    def __enter__(self):
        self._driver = self._get_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._driver.quit()

    @staticmethod
    def _get_driver() -> WebDriver:
        options = ChromiumOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-automation")
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-browser-side-navigation')
        options.add_argument('--blink-settings=imagesEnabled=false')
        options.binary_location = "C:\Program Files\Google\Chrome Beta\Application\chrome.exe"
        return undetected_chromedriver.Chrome(options=options, suppress_welcome=False)

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
            cart_json: str = response_json.get("state").get("trackingPayloads").get(cart_id)

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

    def get_redirect(self, url: str) -> str:
        while True:
            try:
                self._driver.get(url)
                break
            except:
                pass

        try:
            WebDriverWait(self._driver, 3).until(lambda driver: url in driver.current_url)
        except TimeoutException:
            pass
        return self._driver.current_url

    @staticmethod
    def remove_query_from_url(url: str) -> str:
        return urlsplit(url)._replace(query=None).geturl()


class OutOfStockException(Exception):
    pass


class WrongUrlException(Exception):
    pass


if __name__ == "__main__":
    with Parser() as parser:
        parser.add_to_cart(input())
        sleep(1)
        print(parser.get_cart())
