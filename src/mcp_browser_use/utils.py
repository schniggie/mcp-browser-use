# ruff: noqa: E402

import logging
import os
import subprocess
import sys

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

logging.getLogger("browser_use").setLevel(logging.CRITICAL)
logging.getLogger("playwright").setLevel(logging.CRITICAL)


def check_playwright_installation():
    """
    Check if browser-use dependencies are available.
    Returns:
        bool: True if dependencies are available, False otherwise
    """
    try:
        # browser-use handles browser management internally
        import browser_use
        logger.info("browser-use is available")
        return True
    except ImportError as e:
        logger.error(f"browser-use is not installed: {e}")
        return False
