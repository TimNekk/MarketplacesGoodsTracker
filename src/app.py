from time import sleep

from oauth2client.service_account import ServiceAccountCredentials

from src.models import Item, Marketplace
from src.utils import logger


class App:
    def __init__(
        self,
        credentials: ServiceAccountCredentials,
        marketplace: Marketplace,
    ) -> None:
        self.marketplace = marketplace
        self.sheets = self.marketplace.sheets(credentials)

    def update(self):
        logger.info("Getting items...")

        while True:
            try:
                items = self._get_items()
                logger.debug("\n".join(map(str, items)))
                break
            except Exception as e:
                logger.exception(e)

        logger.info("Exporting...")

        while True:
            try:
                self.sheets.set_items(items)
                break
            except Exception as e:
                logger.exception(e)
                sleep(60)

        logger.info("Done exporting!")

    def _get_items(self) -> list[Item]:
        urls = self.sheets.get_urls()
        logger.debug(f"Got urls: {urls}")
        return self.marketplace.parser.get_items(urls)
