import json
import re
from collections.abc import Iterable
from time import sleep

from selenium.common.exceptions import InvalidArgumentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from src.models import Status, OzonUrls, OzonItem, OzonItemPair
from src.parsing.exceptions import WrongUrlException, OutOfStockException
from src.parsing.item_parser import ItemParser
from src.parsing.selenium_parser import SeleniumParser
from src.utils import logger, QuotEncoder


class OzonParser(ItemParser, SeleniumParser):
    def __init__(self) -> None:
        self._cart = "https://www.ozon.ru/cart"

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
            WebDriverWait(self._driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Добавить в корзину']"))).click()
        except TimeoutException:
            WebDriverWait(self._driver, 3).until(EC.element_to_be_clickable((By.XPATH, "(//span[text()='В корзину'])[2]"))).click()

    def get_first_cart_item(self) -> OzonItem:
        logger.debug("Getting cart...")

        json_string = None
        while True:
            self._driver.get(self._cart)

            page_source = self._driver.page_source
            page_source = page_source.replace("&nbsp;", " ")
            page_source = page_source.replace("&quot;", "\"")

            logger.debug("Parsing page source...")
            try:
                json_string = str(re.findall(r"'({.*?trackingPayloads.*?})'", page_source)[0])
                green_price_parts = re.findall(r"ozCtrlPositive.*?((\d+\s*)+).*?₽", page_source)
            except IndexError:
                sleep(5)
                continue
            break

        json_string = json_string.replace("\\\\", "\\")
        json_string = re.sub(r"\\n", "", json_string)

        logger.debug("Parsing json...")
        data = json.loads(json_string, cls=QuotEncoder)

        first_item = list(self._parse_cart_json(data))[0]

        if green_price_parts:
            green_price = int(green_price_parts[0][0].replace(" ", ""))
            first_item.green_price = green_price

        return first_item

    @staticmethod
    def _parse_cart_json(response_json) -> Iterable[OzonItem]:
        logger.debug("Parsing cart json...")
        tracking_payloads: dict[str, str] = response_json.get("trackingPayloads")

        json_payload = None
        for payload in tracking_payloads.values():
            json_payload = json.loads(payload)
            if "products" in json_payload:
                break

        items: list[OzonItem] = []
        for item_json in json_payload.get("products"):
            item = OzonItem(
                quantity=item_json.get("availability"),
                price=item_json.get("finalPrice"),
                status=Status.OK
            )
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
                        return OzonItem(url=url, status=Status.OUT_OF_STOCK)

                    sleep(1)
                    item = parser.get_first_cart_item()
                    item.url = url
                    logger.info(f"Got item: {item}")
                    return item
            except Exception as e:
                logger.error(e)
                attempts += 1


def test_run():
    SeleniumParser.BINARY_LOCATION = r"C:\Users\herew\Downloads\chrome\win64-114.0.5735.133\chrome-win64\chrome.exe"
    with OzonParser() as parser:
        parser.add_to_cart(input())
        sleep(1)
        print(parser.get_first_cart_item())


if __name__ == "__main__":
    test_run()
