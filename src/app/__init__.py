import logging

logger = logging.getLogger(__name__)


def configure_logger(level_name: str = "INFO") -> None:
    numeric_level = getattr(logging, level_name.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(numeric_level)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.propagate = False
