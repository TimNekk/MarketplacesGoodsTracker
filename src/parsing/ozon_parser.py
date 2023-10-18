import json
import re
from collections.abc import Iterable
from time import sleep

from selenium.common.exceptions import InvalidArgumentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from src.models import Status, OzonUrls, OzonItem, OzonItemPair
from src.parsing.exceptions import WrongUrlException, OutOfStockException, ParsingException
from src.parsing.item_parser import ItemParser
from src.parsing.selenium_parser import SeleniumParser
from src.utils import logger, QuotEncoder


class OzonParser(ItemParser, SeleniumParser):
    _CART = "https://www.ozon.ru/cart"
    _MAX_ITEM_PARSE_ATTEMPTS = 3

    def add_to_cart(self, url: str) -> None:
        logger.debug("Adding to cart...")

        url = url.replace("oos_search=false", "")

        logger.debug("Getting page source...")
        try:
            self._driver.get(url)
        except InvalidArgumentException:
            raise WrongUrlException(f"Wrong url passed ({url})")

        logger.debug("Checking if item is out of stock...")
        if "ozon.ru/search" in self._driver.current_url or "ozon.ru/category" in self._driver.current_url:
            raise OutOfStockException("Item is out of stock")

        logger.debug("Clicking add to cart button...")
        try:
            WebDriverWait(self._driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Добавить в корзину']"))).click()
        except TimeoutException:
            WebDriverWait(self._driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "(//span[text()='В корзину'])[2]"))).click()

    def get_first_cart_item(self) -> OzonItem:
        logger.debug("Getting cart...")

        json_string = None
        tries = 0
        while tries < 2:
            tries += 1

            self._driver.get(OzonParser._CART)

            page_source = self._driver.page_source
            page_source = page_source.replace("&nbsp;", " ")
            page_source = page_source.replace("&quot;", "\"")

            logger.debug("Parsing page source...")
            try:
                json_string = str(re.findall(r"split.*,\"items\":(\[.*])", page_source)[0])
            except IndexError:
                sleep(5)
                continue
            break

        if not json_string:
            raise ParsingException("Couldn't parse cart")

        json_string = json_string.replace("\\\\", "\\")
        json_string = re.sub(r"\\n", "", json_string)

        logger.debug("Converting parsed string to items JSON...")
        items = json.loads(json_string, cls=QuotEncoder)

        first_item = list(self._parse_cart_json(items))[0]
        return first_item

    @staticmethod
    def _parse_cart_json(parsed_items) -> Iterable[OzonItem]:
        logger.debug("Parsing items JSON...")

        items: list[OzonItem] = []
        for parsed_item in parsed_items:
            quantity = parsed_item.get("quantity").get("maxQuantity")

            price_column = parsed_item.get("products")[0].get("priceColumn")
            price = int(''.join(filter(str.isdigit,
                                       list(filter(lambda column_item: column_item.get("type") == "price",
                                                   price_column))[0]
                                       .get("price")
                                       .get("price")
                                       )))

            item = OzonItem(
                quantity=quantity,
                price=price,
                status=Status.OK
            )

            green_price_column_items = list(
                filter(lambda column_item: column_item.get("type") == "priceWithTitle", price_column))
            if green_price_column_items:
                green_price = int(
                    ''.join(filter(str.isdigit, green_price_column_items[0].get("priceWithTitle").get("price"))))
                item.green_price = green_price

            items.append(item)

        return items

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
    def _get_item(url: str) -> OzonItem:
        logger.info(f"Getting item from: {url}...")

        attempts, max_attempts = 0, OzonParser._MAX_ITEM_PARSE_ATTEMPTS
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
                        return OzonItem(url=url, status=Status.OUT_OF_STOCK)

                    sleep(1)
                    item = parser.get_first_cart_item()
                    item.url = url
                    logger.info(f"Got item: {item}")
                    return item
            except Exception as e:
                logger.exception(e)
                sleep(5)
                attempts += 1


def test_run():
    SeleniumParser.BINARY_LOCATION = r"C:\Users\herew\Downloads\chrome\win64-114.0.5735.133\chrome-win64\chrome.exe"
    with OzonParser() as parser:
        parser.add_to_cart(input())
        sleep(1)
        print(parser.get_first_cart_item())


if __name__ == "__main__":
    test_run()
