import undetected_chromedriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.chromium.options import ChromiumOptions

from abc import ABC


class SeleniumParser(ABC):
    BINARY_LOCATION = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

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
        options.add_argument("--disable-extensions")
        options.add_argument("--dns-prefetch-disable")
        options.add_argument("--disable-gpu")
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-browser-side-navigation')
        options.add_argument('--blink-settings=imagesEnabled=false')
        options.page_load_strategy = 'normal'
        options.binary_location = SeleniumParser.BINARY_LOCATION
        return undetected_chromedriver.Chrome(options=options, suppress_welcome=True)
