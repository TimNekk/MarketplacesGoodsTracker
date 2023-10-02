class ParsingException(Exception):
    pass


class OutOfStockException(ParsingException):
    pass


class WrongUrlException(ParsingException):
    pass
