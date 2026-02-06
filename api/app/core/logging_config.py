import logging
import sys
from app.config import settings


def setup_logging() -> None:
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | "
        "%(funcName)s:%(lineno)d | %(message)s"
    )
    
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(settings.LOG_LEVEL)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)
    root_logger.addHandler(console_handler)
    
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    if settings.is_development:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)