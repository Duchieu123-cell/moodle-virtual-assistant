import logging
import sys
from src.core.config import settings


def setup_logging() -> None:
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Giảm nhiễu từ thư viện bên thứ ba
    for name in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)