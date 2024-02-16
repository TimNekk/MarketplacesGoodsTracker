from enum import Enum


class Status(Enum):
    DEFAULT = "DEFAULT"
    OK = "Ок"
    PARSING_ERROR = "Ошибка"
    OUT_OF_STOCK = "Нет в наличии"
    WRONG_URL = ""
    OUTDATED_URL = "Обновите ссылку"
