# ruff: noqa: E402

import asyncio
import logging
import sys
import json
from typing import Dict, Optional, Any, List
from urllib.parse import quote as url_quote

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Keep third-party logging quiet
logging.getLogger("browser_use").setLevel(logging.CRITICAL)
logging.getLogger("playwright").setLevel(logging.CRITICAL)

# Optional dependency; we'll fallback gracefully if missing
try:
    import markdownify  # type: ignore
except Exception:  # pragma: no cover
    markdownify = None  # type: ignore

from browser_use import Browser
from mcp.server.fastmcp import FastMCP

from .utils import check_playwright_installation

# -----------------------------------------------------------------------------
# MCP wiring
# -----------------------------------------------------------------------------
mcp = FastMCP("browser_use")

# -----------------------------------------------------------------------------
# Global state (single-process MCP server, keep this simple)
# -----------------------------------------------------------------------------
browser: Optional[Browser] = None
current_page: Optional[Any] = None  # browser_use Actor Page
# index -> unique CSS selector (we re-query each time to avoid stale handles)
_selector_map: Dict[int, str] = {}
_last_inspected_url: Optional[str] = None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
async def _require_browser() -> Browser:
    global browser
    if browser is None:
        raise RuntimeError("Browser not initialized. Call initialize_browser first.")
    return browser


async def _require_page() -> Any:
    global current_page
    b = await _require_browser()
    if current_page is None:
        current_page = await b.new_page()
    return current_page


def _reset_index_if_navigated(new_url: Optional[str]) -> None:
    global _selector_map, _last_inspected_url
    if new_url and _last_inspected_url and new_url != _last_inspected_url:
        _selector_map.clear()
        _last_inspected_url = new_url


async def _refresh_current_url() -> Optional[str]:
    try:
        page = await _require_page()
        return await page.get_url()
    except Exception:
        return None


def _format_element_line(idx: int, meta: Dict[str, Any]) -> str:
    # show a compact, helpful label
    tag = meta.get("tag", "").lower()
    typ = meta.get("type", "")
    role = meta.get("role", "")
    placeholder = meta.get("placeholder") or ""
    title = meta.get("title") or ""
    aria = meta.get("ariaLabel") or ""
    text = (meta.get("text") or "").strip()
    text = " ".join(text.split())  # collapse whitespace
    preview = text[:120] + ("…" if len(text) > 120 else "")
    bits: List[str] = [f"{idx}: <{tag}{(' type='+typ) if typ else ''}>"]
    if role:
        bits.append(f"[role={role}]")
    if placeholder:
        bits.append(f'placeholder="{placeholder}"')
    if aria:
        bits.append(f'aria-label="{aria}"')
    if title:
        bits.append(f'title="{title}"')
    if preview:
        bits.append(f"text={json.dumps(preview)}")
    return "  ".join(bits)


# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------
@mcp.tool()
async def initialize_browser(headless: bool = False, task: str = "") -> str:
    """
    Initialize a new browser instance (latest browser-use API).
    """
    global browser, current_page, _selector_map, _last_inspected_url

    if browser is not None:
        # Cleanly stop previous session
        try:
            await browser.stop()
        except Exception:
            pass
        browser = None
        current_page = None

    # Try different browser configurations for compatibility
    browser_configs = [
        # Configuration 1: Robust settings for MCP environment
        {
            "headless": headless,
            "disable_security": True,
            "chromium_sandbox": False,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor"
            ]
        },
        # Configuration 2: Basic configuration as fallback
        {
            "headless": headless,
            "args": ["--no-sandbox", "--disable-dev-shm-usage"]
        },
        # Configuration 3: Minimal configuration
        {
            "headless": headless
        }
    ]

    browser = None
    last_error = None

    for i, browser_config in enumerate(browser_configs):
        try:
            logger.info(f"Trying browser configuration {i+1}/3")
            browser = Browser(**browser_config)

            # Start browser with timeout to avoid hanging
            start_task = asyncio.create_task(browser.start())
            await asyncio.wait_for(start_task, timeout=30.0)
            logger.info(f"Browser started successfully with configuration {i+1}")
            break

        except asyncio.TimeoutError as e:
            last_error = f"Configuration {i+1} timed out after 30 seconds"
            logger.warning(last_error)
            if browser:
                try:
                    await browser.stop()
                except:
                    pass
                browser = None

        except Exception as e:
            last_error = f"Configuration {i+1} failed: {str(e)}"
            logger.warning(last_error)
            if browser:
                try:
                    await browser.stop()
                except:
                    pass
                browser = None

    if browser is None:
        raise RuntimeError(f"Browser initialization failed with all configurations. Last error: {last_error}")

    current_page = await browser.new_page("about:blank")
    _selector_map.clear()
    _last_inspected_url = None

    # Simple system guidance string
    actions = (
        "initialize_browser, close_browser, search_google, go_to_url, go_back, wait, "
        "click_element, input_text, switch_tab, open_tab, inspect_page, scroll_down, "
        "scroll_up, send_keys, scroll_to_text, get_dropdown_options, "
        "select_dropdown_option, validate_page, execute_javascript, done"
    )
    return (
        f"You can control a real browser with direct tools. Available actions: {actions}.\n"
        f"Your ultimate task is: {task}\n"
        f"If the task is achieved, call done()."
    )


@mcp.tool()
async def close_browser() -> str:
    """Close the current browser instance."""
    global browser, current_page, _selector_map, _last_inspected_url
    if browser is not None:
        try:
            await browser.stop()
        finally:
            browser = None
            current_page = None
            _selector_map.clear()
            _last_inspected_url = None
    return "Browser closed successfully"


@mcp.tool()
async def search_google(query: str) -> str:
    """Search the query on Google in the current tab."""
    page = await _require_page()
    url = f"https://www.google.com/search?q={url_quote(query)}&udm=14"
    await page.goto(url)
    await asyncio.sleep(0.5)
    _selector_map.clear()
    return f'🔍 Searched for "{query}" in Google'


@mcp.tool()
async def go_to_url(url: str) -> str:
    """Navigate to URL in the current tab."""
    page = await _require_page()
    await page.goto(url)
    await asyncio.sleep(0.5)
    _selector_map.clear()
    return f"🔗 Navigated to {url}"


@mcp.tool()
async def go_back() -> str:
    """Go back to the previous page."""
    page = await _require_page()
    await page.go_back()
    await asyncio.sleep(0.3)
    _selector_map.clear()
    return "🔙 Navigated back"


@mcp.tool()
async def wait(seconds: int = 3) -> str:
    """Wait for a bit."""
    await asyncio.sleep(seconds)
    return f"🕒 Waiting for {seconds} seconds"


@mcp.tool()
async def inspect_page() -> str:
    """
    Lists interactive elements and extracts content from the current page.
    Creates a stable index→selector map for follow-up actions.
    """
    global _selector_map, _last_inspected_url

    page = await _require_page()
    # Collect interactive/meaningful elements (visible only) and compute a unique-ish CSS path
    js = r"""
    () => {
      const isVisible = (el) => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 &&
               style.visibility !== 'hidden' && style.display !== 'none';
      };

      const cssPath = (el) => {
        // generate a fairly unique CSS selector for the element
        if (!(el instanceof Element)) return '';
        const path = [];
        while (el && el.nodeType === Node.ELEMENT_NODE && path.length < 8) {
          let selector = el.nodeName.toLowerCase();
          if (el.id) {
            selector += '#' + CSS.escape(el.id);
            path.unshift(selector);
            break;
          } else {
            let sib = el, nth = 1;
            while (sib = sib.previousElementSibling) {
              if (sib.nodeName.toLowerCase() === selector) nth++;
            }
            selector += `:nth-of-type(${nth})`;
          }
          path.unshift(selector);
          el = el.parentElement;
        }
        return path.join(' > ');
      };

      const nodes = Array.from(document.querySelectorAll(`
        a[href],
        button,
        input:not([type="hidden"]):not([disabled]),
        textarea:not([disabled]),
        select:not([disabled]),
        [role="button"],
        [contenteditable=""], [contenteditable="true"],
        [tabindex]:not([tabindex="-1"])
      `));

      const uniq = new Set();
      const items = [];
      for (const el of nodes) {
        if (!isVisible(el)) continue;
        const selector = cssPath(el);
        if (!selector || uniq.has(selector)) continue;
        uniq.add(selector);
        const text = (el.innerText || el.value || '').trim();
        items.push({
          selector,
          tag: el.tagName.toLowerCase(),
          type: el.getAttribute('type') || '',
          role: el.getAttribute('role') || '',
          placeholder: el.getAttribute('placeholder') || '',
          title: el.getAttribute('title') || '',
          ariaLabel: el.getAttribute('aria-label') || '',
          text,
        });
      }
      return items;
    }
    """
    result = await page.evaluate(js)  # type: ignore
    _selector_map.clear()

    # Handle case where result might be a string (error) or list
    if isinstance(result, str):
        # Try to parse as JSON if it looks like an array
        if result.strip().startswith('[') and result.strip().endswith(']'):
            try:
                import json
                result = json.loads(result)
            except json.JSONDecodeError:
                logger.error(f"JavaScript evaluation returned unparseable string: {result}")
                return "Error extracting elements from page. Page might not be fully loaded."
        else:
            logger.error(f"JavaScript evaluation returned string: {result}")
            return "Error extracting elements from page. Page might not be fully loaded."

    if not isinstance(result, list):
        logger.error(f"JavaScript evaluation returned unexpected type: {type(result)}")
        return "Error extracting elements from page."

    elements: List[Dict[str, Any]] = result
    for i, item in enumerate(elements, start=1):
        if isinstance(item, dict) and "selector" in item:
            _selector_map[i] = item["selector"]
    _last_inspected_url = await page.get_url()

    if not elements:
        return "No interactive elements found on this page."
    lines = ["Interactive elements:"]
    lines += [_format_element_line(i, el) for i, el in enumerate(elements, start=1)]
    return "\n".join(lines)


@mcp.tool()
async def click_element(index: int) -> str:
    """Click the element with the specified index (from inspect_page)."""
    page = await _require_page()
    if index not in _selector_map:
        raise Exception(
            f"Element with index {index} does not exist - call inspect_page() first and retry"
        )

    selector = _selector_map[index]

    # Pre-check: file upload?
    el_list = await page.get_elements_by_css_selector(selector)
    if not el_list:
        _selector_map.pop(index, None)
        return f"Index {index}: element not found anymore (page changed). Re-run inspect_page()."
    el = el_list[0]

    el_type = (await el.get_attribute("type")) or ""
    el_tag = (await el.get_attribute("tagName")) or ""
    if el_tag.lower() == "input" and el_type.lower() == "file":
        return f"Index {index} opens a file picker. Use a dedicated upload tool."

    # Detect new tab opening
    before = await (await _require_browser()).get_pages()
    before_ids = {id(p) for p in before}

    await el.click()
    await asyncio.sleep(0.3)

    after = await (await _require_browser()).get_pages()
    after_ids = {id(p) for p in after}
    new_ids = after_ids - before_ids
    msg = f"🖱️ Clicked element at index {index}"
    if new_ids:
        # Switch to newest page
        for p in after:
            if id(p) in new_ids:
                global current_page
                current_page = p
                break
        _selector_map.clear()
        msg += " - New tab opened and switched to it."
    else:
        # Maybe navigated in place; clear map if URL changed
        _reset_index_if_navigated(await page.get_url())

    return msg


@mcp.tool()
async def input_text(index: int, text: str, has_sensitive_data: bool = False) -> str:
    """
    Input text into an interactive element at the specified index.
    """
    page = await _require_page()
    if index not in _selector_map:
        raise Exception(
            f"Element index {index} does not exist - call inspect_page() first"
        )

    selector = _selector_map[index]
    el_list = await page.get_elements_by_css_selector(selector)
    if not el_list:
        _selector_map.pop(index, None)
        return f"Index {index}: element not found anymore. Re-run inspect_page()."
    el = el_list[0]
    await el.fill(text)
    _reset_index_if_navigated(await page.get_url())

    return (
        f"⌨️ Input sensitive data into index {index}"
        if has_sensitive_data
        else f"⌨️ Input {text} into index {index}"
    )


@mcp.tool()
async def switch_tab(page_id: int) -> str:
    """
    Switch to the tab by index (0-based). Use -1 for the last tab.
    """
    global current_page
    b = await _require_browser()
    pages = await b.get_pages()
    if not pages:
        return "No tabs open."
    if page_id < 0:
        page_id = len(pages) + page_id
    if page_id < 0 or page_id >= len(pages):
        return f"Invalid tab index {page_id}. There are {len(pages)} tabs."
    current_page = pages[page_id]
    url = await current_page.get_url()
    title = await current_page.get_title()
    _selector_map.clear()
    return f"🔄 Switched to tab {page_id} ({title or url})"


@mcp.tool()
async def open_tab(url: str) -> str:
    """Open a URL in a new tab and switch to it."""
    global current_page
    b = await _require_browser()
    current_page = await b.new_page(url)
    await asyncio.sleep(0.3)
    _selector_map.clear()
    return f"🔗 Opened new tab with {url}"


@mcp.tool()
async def scroll_down(amount: Optional[int] = None) -> str:
    """Scroll down by pixels; if None, one viewport."""
    page = await _require_page()
    if amount is None:
        js = "()=> window.scrollBy(0, window.innerHeight)"
        await page.evaluate(js)
        amount = -1  # marker for 'one page'
    else:
        await page.evaluate(f"()=> window.scrollBy(0, {int(amount)})")
    return f"🔍 Scrolled down the page by {'one page' if amount == -1 else f'{amount} pixels'}"


@mcp.tool()
async def scroll_up(amount: Optional[int] = None) -> str:
    """Scroll up by pixels; if None, one viewport."""
    page = await _require_page()
    if amount is None:
        js = "()=> window.scrollBy(0, -window.innerHeight)"
        await page.evaluate(js)
        amount = -1
    else:
        await page.evaluate(f"()=> window.scrollBy(0, -{int(amount)})")
    return f"🔍 Scrolled up the page by {'one page' if amount == -1 else f'{amount} pixels'}"


@mcp.tool()
async def send_keys(keys: str) -> str:
    """Send keyboard keys (e.g., 'Enter', 'Control+A')."""
    page = await _require_page()
    await page.press(keys)
    return f"⌨️ Sent keys: {keys}"


@mcp.tool()
async def scroll_to_text(text: str) -> str:
    """
    Scroll to first element containing the given (case-insensitive) text.
    """
    page = await _require_page()
    js = r"""
    (needle) => {
      const n = String(needle).toLowerCase();
      // Prefer visible text containers
      const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_TEXT,
        {
          acceptNode(node) {
            if (!node.nodeValue) return NodeFilter.FILTER_REJECT;
            if (!node.parentElement) return NodeFilter.FILTER_REJECT;
            const s = node.nodeValue.toLowerCase();
            if (!s.includes(n)) return NodeFilter.FILTER_SKIP;
            const el = node.parentElement;
            const rect = el.getBoundingClientRect();
            const style = getComputedStyle(el);
            if (rect.width <= 0 || rect.height <= 0) return NodeFilter.FILTER_SKIP;
            if (style.visibility === 'hidden' || style.display === 'none') return NodeFilter.FILTER_SKIP;
            return NodeFilter.FILTER_ACCEPT;
          }
        }
      );
      let node;
      while ((node = walker.nextNode())) {
        node.parentElement.scrollIntoView({behavior: 'instant', block: 'center', inline: 'nearest'});
        return true;
      }
      return false;
    }
    """
    found = await page.evaluate(js, text)  # type: ignore
    return f"🔍 Scrolled to text: {text}" if found else f"Text '{text}' not found or not visible on page"


@mcp.tool()
async def get_dropdown_options(index: int) -> str:
    """
    List visible option labels for a <select> element by index from inspect_page().
    """
    page = await _require_page()
    if index not in _selector_map:
        return "No such element index. Run inspect_page() first."
    selector = _selector_map[index]
    js = r"""
    (sel) => {
      const el = document.querySelector(sel);
      if (!el || el.tagName.toLowerCase() !== 'select') return null;
      return Array.from(el.options).map((opt, i) => ({
        idx: i,
        text: opt.text,
        value: opt.value
      }));
    }
    """
    opts = await page.evaluate(js, selector)  # type: ignore
    if not opts:
        return f"No options found (or element {index} is not a <select>)."
    lines = [f"{o['idx']}: text={json.dumps(o['text'])}  value={json.dumps(o['value'])}" for o in opts]
    lines.append("Use select_dropdown_option(index, text=<visible text>)")
    return "\n".join(lines)


@mcp.tool()
async def select_dropdown_option(index: int, text: str) -> str:
    """
    Select an option from a dropdown by its *visible text*.
    """
    page = await _require_page()
    if index not in _selector_map:
        return "No such element index. Run inspect_page() first."
    selector = _selector_map[index]

    # Resolve visible text -> value in-page, then call Element.select_option(values=value)
    js_value_for_text = r"""
    (sel, want) => {
      const el = document.querySelector(sel);
      if (!el || el.tagName.toLowerCase() !== 'select') return null;
      const match = Array.from(el.options).find(o => (o.text || '').trim() === want.trim());
      return match ? match.value : null;
    }
    """
    value = await page.evaluate(js_value_for_text, selector, text)  # type: ignore
    if value is None:
        return f"Could not find option with visible text {json.dumps(text)}."

    elements = await page.get_elements_by_css_selector(selector)
    if not elements:
        return f"Select element disappeared; re-run inspect_page()."
    await elements[0].select_option(value)
    return f"Selected option {json.dumps(text)} with value {json.dumps(value)}"


@mcp.tool()
async def validate_page(expected_text: str = "") -> str:
    """
    Extract page content; optionally assert that expected_text appears.
    """
    page = await _require_page()
    html = await page.evaluate("()=> document.documentElement.outerHTML")
    text_md = None
    if markdownify:
        try:
            text_md = markdownify.markdownify(html)  # type: ignore
        except Exception:
            pass

    content_preview = (text_md or html)[:800]
    if expected_text:
        found = (text_md or html).lower().find(expected_text.lower()) != -1
        if found:
            return f"✅ Validation successful: Expected text '{expected_text}' found on page."
        return f"⚠ Validation warning: Expected text '{expected_text}' not found.\nExtracted snippet: {content_preview}..."
    return f"Page content extracted:\n{content_preview}..."


@mcp.tool()
async def execute_javascript(script: str) -> str:
    """
    Execute JavaScript on the current page.
    IMPORTANT: pass an arrow function as a string, e.g. '() => document.title'
    or '(x, y) => x + y'.
    """
    page = await _require_page()
    try:
        result = await page.evaluate(script)
        if isinstance(result, (dict, list)):
            try:
                return "📝 JavaScript executed successfully:\n" + json.dumps(result, indent=2)
            except Exception:
                return f"📝 JavaScript executed successfully. Result (non-serializable): {str(result)}"
        else:
            return f"📝 JavaScript executed successfully. Result: {result}"
    except Exception as e:
        return f"❌ Error executing JavaScript: {str(e)}"


@mcp.tool()
async def done(success: bool = True, text: str = "") -> dict:
    """Signal completion to the client."""
    return {"is_done": True, "success": success, "extracted_content": text}


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
def main():
    """Run the MCP server"""
    if not check_playwright_installation():
        logger.error("Playwright is not properly installed. Exiting.")
        sys.exit(1)

    logger.info("Starting MCP server for browser-use (modern API)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

