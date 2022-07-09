import logging
from logging.handlers import TimedRotatingFileHandler

import coloredlogs


def _check_and_create_logging_directory(path):
    import os
    if not os.path.exists(path):
        os.makedirs(path)


fmt = "%(asctime)s [%(levelname)s] - (%(filename)s).%(funcName)s(%(lineno)d) > %(message)s"
log_directory = "logs/"
log_file = "log"
file_handler_suffix = ".%d-%m-%Y.log"

_check_and_create_logging_directory(log_directory)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
coloredlogs.install(level="INFO", logger=logger, fmt=fmt)

file_handler = TimedRotatingFileHandler(log_directory + log_file, when="midnight", interval=1)
file_handler.setLevel(logging.DEBUG)
file_handler.suffix = file_handler_suffix
file_handler.setFormatter(logging.Formatter(fmt))

logger.addHandler(file_handler)
