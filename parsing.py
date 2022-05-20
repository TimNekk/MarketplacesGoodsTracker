import logging
import re
from time import sleep

from selenium import webdriver
from selenium.common.exceptions import InvalidArgumentException, StaleElementReferenceException
from selenium.webdriver import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


class Parser:
    def __init__(self, headless=False) -> None:
        self.headless = headless

        self.cart = "https://www.ozon.ru/cart"

    def _get_driver(self) -> WebDriver:
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        return webdriver.Chrome(service=Service(ChromeDriverManager(log_level=logging.NOTSET).install()), options=chrome_options)

    def get_quantity(self, url: str) -> int:
        input_index = 4
        driver = self._get_driver()

        try:
            driver.get(url)
        except InvalidArgumentException:
            raise WrongUrlException(f"Wrong url passed ({url})")

        # Checks if item is out of stock
        for el in driver.find_elements(By.TAG_NAME, "div"):
            try:
                if el.get_attribute("data-widget") == "webPrice" and "Товар закончился" in el.text:
                    raise OutOfStockException("Item is out of stock")
            except StaleElementReferenceException:
                pass

        # Adding to cart
        try:
            # If only one "Add to cart" button
            add_to_card_button = list(filter(lambda button: button.text == "Добавить в корзину", driver.find_elements(By.TAG_NAME, "button")))[0]
        except IndexError:
            # If two "Add to cart" buttons
            input_index = 5
            add_to_card_button = list(filter(lambda button: button.text == "В корзину", driver.find_elements(By.TAG_NAME, "button")))[1]
        add_to_card_button.click()
        sleep(0.8)

        # Go to cart
        driver.get(self.cart)

        # Hide pop-up window
        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()

        # Click on quantity input
        inputs = driver.find_elements(By.TAG_NAME, "input")
        inputs[input_index].click()

        # Go to bottom of quantity list
        sleep(0.3)
        for _ in range(0, 10):
            webdriver.ActionChains(driver).send_keys(Keys.ARROW_DOWN).perform()
        webdriver.ActionChains(driver).send_keys(Keys.ENTER).perform()

        # Type max number to quantity input
        inputs = driver.find_elements(By.TAG_NAME, "input")
        inputs[input_index].send_keys("9999999999999")

        # Get available quantity
        sleep(3)
        left = int(re.findall(r"Товары \(([\d&nbsp;]+)\)", driver.page_source)[0].replace("&nbsp;", ""))

        driver.close()

        return left


class OutOfStockException(Exception):
    pass


class WrongUrlException(Exception):
    pass


if __name__ == "__main__":
    parser = Parser()
    print(parser.get_quantity(input()))
