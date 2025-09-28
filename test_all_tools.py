#!/usr/bin/env python3
"""
Comprehensive test suite for mcp-browser-use MCP server tools.

This script validates all available MCP tools work correctly with the modern browser-use API.
Run this after making changes to ensure no regressions.

Usage: python test_all_tools.py
"""

import asyncio
import logging
import traceback
from typing import Dict, Any, List

# Import all the MCP tools
from src.mcp_browser_use.server import (
    initialize_browser, close_browser, search_google, go_to_url, go_back, wait,
    click_element, input_text, switch_tab, open_tab, inspect_page, scroll_down,
    scroll_up, send_keys, scroll_to_text, get_dropdown_options,
    select_dropdown_option, validate_page, execute_javascript, done
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ToolTester:
    def __init__(self):
        self.test_results: Dict[str, Dict[str, Any]] = {}
        self.current_test = ""

    def log_test(self, test_name: str, success: bool, result: str = "", error: str = ""):
        """Log test results"""
        self.test_results[test_name] = {
            "success": success,
            "result": result[:200] + "..." if len(result) > 200 else result,
            "error": error
        }
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {result[:100]}{'...' if len(result) > 100 else ''}")
        if error:
            print(f"   Error: {error}")

    async def run_test(self, test_name: str, test_func):
        """Run a single test with error handling"""
        try:
            result = await test_func()
            self.log_test(test_name, True, str(result))
            return True
        except Exception as e:
            self.log_test(test_name, False, "", str(e))
            return False

    async def test_basic_browser_operations(self):
        """Test basic browser initialization and navigation"""
        print("\n🔍 Testing Basic Browser Operations...")

        # Test 1: Initialize browser
        await self.run_test("initialize_browser",
            lambda: initialize_browser(headless=True, task="Comprehensive testing"))

        # Test 2: Go to a test page
        await self.run_test("go_to_url",
            lambda: go_to_url("https://httpbin.org/html"))

        # Test 3: Wait for page load
        await self.run_test("wait",
            lambda: wait(2))

        # Test 4: Go back
        await self.run_test("go_back",
            lambda: go_back())

        # Test 5: Search Google
        await self.run_test("search_google",
            lambda: search_google("browser automation testing"))

    async def test_page_interaction_tools(self):
        """Test page inspection and element interaction"""
        print("\n🔍 Testing Page Interaction Tools...")

        # Navigate to a page with interactive elements
        await go_to_url("https://httpbin.org/forms/post")
        await wait(2)

        # Test 1: Inspect page
        inspect_result = await self.run_test("inspect_page", inspect_page)

        if inspect_result:
            # Test 2: Try to input text (if form elements exist)
            try:
                # Look for the first input field and try to fill it
                await self.run_test("input_text_index_1",
                    lambda: input_text(1, "test input"))
            except:
                self.log_test("input_text_index_1", False, "", "No input element at index 1")

            # Test 3: Try to click an element
            try:
                await self.run_test("click_element_index_1",
                    lambda: click_element(1))
            except:
                self.log_test("click_element_index_1", False, "", "No clickable element at index 1")

    async def test_javascript_and_scrolling(self):
        """Test JavaScript execution and scrolling features"""
        print("\n🔍 Testing JavaScript and Scrolling...")

        # Navigate to a longer page
        await go_to_url("https://httpbin.org/html")
        await wait(2)

        # Test 1: Execute JavaScript
        await self.run_test("execute_javascript",
            lambda: execute_javascript("() => document.title"))

        # Test 2: Scroll down
        await self.run_test("scroll_down", scroll_down)

        # Test 3: Scroll up
        await self.run_test("scroll_up", scroll_up)

        # Test 4: Send keys
        await self.run_test("send_keys",
            lambda: send_keys("Tab"))

        # Test 5: Scroll to text (try to find common text)
        await self.run_test("scroll_to_text",
            lambda: scroll_to_text("html"))

    async def test_tab_management(self):
        """Test tab management features"""
        print("\n🔍 Testing Tab Management...")

        # Test 1: Open new tab
        await self.run_test("open_tab",
            lambda: open_tab("https://httpbin.org/status/200"))

        await wait(1)

        # Test 2: Switch to tab (back to first tab)
        await self.run_test("switch_tab",
            lambda: switch_tab(0))

    async def test_dropdown_and_validation(self):
        """Test dropdown handling and page validation"""
        print("\n🔍 Testing Dropdown and Validation...")

        # Navigate to a page that might have dropdowns
        await go_to_url("https://httpbin.org/forms/post")
        await wait(2)

        # Test 1: Get dropdown options (will likely fail but we'll test the function)
        try:
            await self.run_test("get_dropdown_options",
                lambda: get_dropdown_options(1))
        except:
            self.log_test("get_dropdown_options", False, "", "No dropdown at index 1 (expected)")

        # Test 2: Validate page
        await self.run_test("validate_page",
            lambda: validate_page("form"))

        # Test 3: Validate page with expected text
        await self.run_test("validate_page_with_text",
            lambda: validate_page("Customer name"))

    async def test_completion_tool(self):
        """Test the done tool"""
        print("\n🔍 Testing Completion Tool...")

        # Test done tool
        await self.run_test("done",
            lambda: done(True, "All tests completed successfully"))

    async def test_browser_cleanup(self):
        """Test browser cleanup"""
        print("\n🔍 Testing Browser Cleanup...")

        # Test close browser
        await self.run_test("close_browser", close_browser)

    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Comprehensive MCP Tools Test Suite")
        print("=" * 60)

        try:
            await self.test_basic_browser_operations()
            await self.test_page_interaction_tools()
            await self.test_javascript_and_scrolling()
            await self.test_tab_management()
            await self.test_dropdown_and_validation()
            await self.test_completion_tool()
            await self.test_browser_cleanup()

        except Exception as e:
            print(f"\n❌ Critical error during testing: {e}")
            traceback.print_exc()

            # Try to clean up browser if it's still running
            try:
                await close_browser()
            except:
                pass

        finally:
            self.print_test_summary()

    def print_test_summary(self):
        """Print a summary of all test results"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for result in self.test_results.values() if result["success"])
        total = len(self.test_results)

        print(f"Tests Passed: {passed}/{total}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")

        print("\n📋 DETAILED RESULTS:")
        for test_name, result in self.test_results.items():
            status = "✅" if result["success"] else "❌"
            print(f"{status} {test_name}")
            if result["error"]:
                print(f"    Error: {result['error']}")

        print("\n" + "=" * 60)

        if passed == total:
            print("🎉 ALL TESTS PASSED! The MCP server is fully functional.")
        else:
            failed = total - passed
            print(f"⚠️  {failed} test(s) failed. Review the errors above.")

        return passed == total

async def main():
    """Main test execution"""
    tester = ToolTester()
    success = await tester.run_all_tests()

    # Return appropriate exit code
    exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())