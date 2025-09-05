#!/usr/bin/env python3
"""
This script opens Chrome with Selenium, waits for the user to type 'ok'
after opening all desired tabs, then continuously captures screenshots
of each tab every 10 seconds and saves them into a 'screen_caps' folder.
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException

tradingview_email = "gordonmeng2023@gmail.com"
tradingview_password = "Mm95596862mM...."

def open_browser() -> webdriver.Chrome:
    """Launch Chrome browser with Selenium."""
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-infobars')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(options=options)  # Requires chromedriver in PATH
    return driver

def auto_login(driver: webdriver.Chrome) -> None:
    """Automatically perform login flow on TradingView."""
    wait = WebDriverWait(driver, 10)
    
    try:
        # Step 1: Click "Get started" button
        get_started_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-overflow-tooltip-text="Get started"]'))
        )
        get_started_button.click()
        # time.sleep(2)
        
        # Step 2: Click user menu
        user_menu = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[aria-label="Open user menu"]'))
        )
        user_menu.click()
        # time.sleep(1)
        
        # Step 3: Click sign in option
        sign_in_option = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-name="header-user-menu-sign-in"]'))
        )
        sign_in_option.click()
        # time.sleep(2)
        
        # Step 4: Click Email button
        email_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[name="Email"]'))
        )
        email_button.click()
        # time.sleep(1)
        
        # Step 5: Enter dummy email
        email_input = wait.until(
            EC.presence_of_element_located((By.ID, "id_username"))
        )
        email_input.clear()
        email_input.send_keys(tradingview_email)
        
        # Step 6: Enter dummy password
        password_input = wait.until(
            EC.presence_of_element_located((By.ID, "id_password"))
        )
        password_input.clear()
        password_input.send_keys(tradingview_password)
        
        # Step 7: Click Sign in button
        sign_in_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-overflow-tooltip-text="Sign in"]'))
        )
        sign_in_button.click()
        # time.sleep(3)  # Wait for login attempt to complete
        
    except TimeoutException as e:
        print(f"Timeout during auto login step: {e}. Continuing anyway...")
    except Exception as e:
        print(f"Error during auto login: {e}. Continuing anyway...")

def wait_for_user() -> None:
    """Wait for user confirmation to continue."""
    print(
        "\nBrowser is now open. You may open new tabs and navigate freely.\n"
        "When ready to begin continuous screenshots, type 'ok' here."
    )
    while True:
        user_input = input('Enter "ok" to continue: ').strip().lower()
        if user_input == 'ok':
            break
        else:
            print("Not recognized. Please type 'ok' when ready.")

def capture_screenshots(driver: webdriver.Chrome, output_dir: str, iteration: int) -> None:
    """Capture screenshots for all tabs."""
    os.makedirs(output_dir, exist_ok=True)
    handles = driver.window_handles
    print(f"[Iteration {iteration}] Capturing screenshots for {len(handles)} tab(s)...")
    for idx, handle in enumerate(handles, start=1):
        driver.switch_to.window(handle)
        time.sleep(0.1)  # allow page render
        filename = f"iter{iteration}_tab{idx}.png"
        path = os.path.join(output_dir, filename)
        if driver.save_screenshot(path):
            print(f"Saved {path}")
        else:
            print(f"Failed to save screenshot for tab {idx}")

def main() -> None:
    driver = open_browser()
    try:
        driver.get("https://www.tradingview.com/")
        auto_login(driver)
        wait_for_user()
        iteration = 1
        while True:
            capture_screenshots(driver, "screen_caps", iteration)
            iteration += 1
            print("Waiting 10 seconds before next capture...")
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nStopping screenshot loop.")
    finally:
        driver.quit()
        print("Browser closed. Done.")

if __name__ == "__main__":
    main()