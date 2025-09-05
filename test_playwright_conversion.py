#!/usr/bin/env python3
"""
Test script to verify the Playwright conversion works correctly.
This script tests the basic functionality without running the full automation.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

def test_browser_launch():
    """Test that we can launch a browser with Playwright."""
    print("Testing Playwright browser launch...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            # Test basic navigation
            page.goto("https://www.google.com")
            title = page.title()
            print(f"✓ Successfully navigated to Google. Title: {title}")
            
            browser.close()
            print("✓ Browser closed successfully")
            return True
    except Exception as e:
        print(f"✗ Browser launch failed: {e}")
        return False

def test_imports():
    """Test that all required imports work."""
    print("Testing imports...")
    try:
        from scrape import open_browser, auto_login, wait_for_user, capture_screenshots
        print("✓ scrape.py imports successful")
        
        from main import (
            configure_logging, wait_for_user_ready, get_tab_metadata,
            extract_symbol_from_image, crop_screenshot, refresh_single_tab,
            capture_single_tab, refresh_all_tabs_parallel, capture_all_tabs_sequential
        )
        print("✓ main.py imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality without full automation."""
    print("Testing basic functionality...")
    try:
        # Test logging setup
        from main import configure_logging
        logger = configure_logging("test.log")
        logger.info("Test log message")
        print("✓ Logging setup successful")
        
        # Test browser opening (but don't keep it open)
        from scrape import open_browser
        browser, context, page = open_browser()
        print("✓ Browser opened successfully")
        
        # Test basic navigation
        page.goto("https://www.tradingview.com/")
        print("✓ Navigation to TradingView successful")
        
        browser.close()
        print("✓ Browser closed successfully")
        return True
    except Exception as e:
        print(f"✗ Basic functionality test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("PLAYWRIGHT CONVERSION TEST")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("Browser Launch Test", test_browser_launch),
        ("Basic Functionality Test", test_basic_functionality),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 30)
        if test_func():
            passed += 1
            print(f"✓ {test_name} PASSED")
        else:
            print(f"✗ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("=" * 50)
    
    if passed == total:
        print("🎉 All tests passed! Playwright conversion is working correctly.")
        return True
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
