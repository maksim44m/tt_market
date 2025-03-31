import os
import sys

from loguru import logger
from aiogram import Bot

from db import DB


db = DB()
bot = Bot(token=os.getenv("TG_TOKEN"))

CHANNEL_USERNAME = '@test_some_chanel'  # публичное имя канала или группы

logger.remove()
logger.add(
    sys.stdout,
    colorize=True,
    format="<white>{time:HH:mm:ss}</white> | "
           "<level>{level: <8} {file}:{function}:{line}</level> | "
           "<light-cyan>{message}</light-cyan>",
    level="INFO",  # TRACE, DEBUG, INFO, SUCCESS, WARNING, ERROR, CRITICAL
)
