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
    Check if playwright browsers are installed and install if needed.
    Returns:
        bool: True if browsers are available, False otherwise
    """
    try:
        # First check if browser-use is available
        import browser_use
        logger.info("browser-use is available")

        # Check if playwright browsers are installed
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                # Try to launch a browser to verify installation
                browser = p.chromium.launch(headless=True)
                browser.close()
                logger.info("Playwright browsers are properly installed")
            return True
        except Exception as e:
            if "Executable doesn't exist" in str(e) or "Browser executable" in str(e):
                logger.warning("Playwright browsers are not installed. Installing now...")
                try:
                    # Install playwright browsers
                    subprocess.run(
                        [sys.executable, "-m", "playwright", "install", "chromium"],
                        check=True,
                        capture_output=True
                    )
                    logger.info("Playwright browsers installed successfully.")

                    # Verify installation worked
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        browser.close()
                    return True
                except subprocess.CalledProcessError as install_error:
                    logger.error(f"Failed to install Playwright browsers: {install_error}")
                    return False
                except Exception as verify_error:
                    logger.error(f"Browser installation verification failed: {verify_error}")
                    return False
            else:
                logger.error(f"Error checking Playwright installation: {e}")
                return False
    except ImportError as e:
        logger.error(f"browser-use or playwright is not installed: {e}")
        return False
