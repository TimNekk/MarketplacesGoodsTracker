from urllib.parse import urlsplit

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait

from src.parsing.selenium_parser import SeleniumParser
from src.utils import logger


class RedirectParser(SeleniumParser):
    def get_redirect(self, url: str) -> str:
        while True:
            try:
                self._driver.get(url)
                break
            except Exception as e:
                logger.warning(f"Error while getting redirect: {e}")

        try:
            WebDriverWait(self._driver, 3).until(lambda driver: url in driver.current_url)
        except TimeoutException:
            pass
        return self._driver.current_url

    @staticmethod
    def remove_query_from_url(url: str) -> str:
        return urlsplit(url)._replace(query=None).geturl()
