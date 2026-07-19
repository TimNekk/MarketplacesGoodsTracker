import os
import sys

from loguru import logger

logger.remove()

logger.add(
    sys.stdout,
    level=os.getenv("LOG_LEVEL", "DEBUG"),
    serialize=os.getenv("LOG_JSON", "true").lower() == "true",
    backtrace=False,
    diagnose=False,
    enqueue=True,
)
