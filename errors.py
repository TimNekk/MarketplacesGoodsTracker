from enum import Enum


class Error(Enum):
    PARSING_ERROR = -1
    OUT_OF_STOCK = -2
    WRONG_URL = -3
