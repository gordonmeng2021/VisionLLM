import os
import sys
import time
import math
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

#### make sure the stock is within the same stock exchange e.g. NASDAQ, NYSE, etc.
stock_list = ["TSLA", "NVDA", "AAPL"]

try:
    import cv2
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    cv2 = None
    pytesseract = None
    OCR_AVAILABLE = False

try:
    from selenium.common.exceptions import WebDriverException
    SELENIUM_AVAILABLE = True
except ImportError:
    WebDriverException = Exception
    SELENIUM_AVAILABLE = False

# Reuse existing Selenium helpers and login flow
try:
    from scrape import open_browser, auto_login
except Exception as import_error:
    open_browser = None
    auto_login = None

try:
    from strategy import CandleStrategyAnalyzer
except Exception as strategy_import_error:
    CandleStrategyAnalyzer = None

# Note: We implement cropping directly in crop_screenshot() function


def configure_logging(log_path: str) -> logging.Logger:
    logger = logging.getLogger("main_orchestrator")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

        file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3)
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler.setFormatter(file_formatter)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        console_handler.setFormatter(console_formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def wait_for_user_ready(logger: logging.Logger) -> None:
    logger.info("Browser is now open. Open all desired tabs and sign in if needed.")
    logger.info("Type 'ok' here to start the scheduled refresh/capture loop.")
    print("Browser is now open. Open all desired tabs and sign in if needed.")
    print("Type 'ok' here to start the scheduled refresh/capture loop.")
    while True:
        try:
            user_input = input('Enter "ok" to continue: ').strip().lower()
        except EOFError:
            time.sleep(1)
            continue
        if user_input == "ok":
            logger.info("User confirmed start. Beginning scheduled operations.")
            print("Starting scheduled operations...")
            return
        logger.info("Input not recognized. Please type 'ok' when ready.")
        print("Input not recognized. Please type 'ok' when ready.")


def get_tab_metadata(driver) -> list:
    tab_infos = []
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        time.sleep(0.2)
        current_url = driver.current_url or "about:blank"
        title = driver.title or ""
        host = urlparse(current_url).hostname or "unknown"
        safe_host = host.replace(":", "_")
        tab_infos.append({
            "handle": handle,
            "url": current_url,
            "title": title,
            "host": safe_host,
        })
    return tab_infos


def extract_symbol_from_image(image_path: str, logger: logging.Logger) -> str:
    """Extract symbol text from top_left_corner.png using OCR."""
    if not OCR_AVAILABLE:
        logger.warning("OCR not available (cv2/pytesseract not installed). Returning UNKNOWN.")
        return "UNKNOWN"
    
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Could not load image for OCR: {image_path}")
            return "UNKNOWN"
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray, lang="eng").strip()
        
        # Clean up the text - take first line and remove common noise
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            symbol = lines[0]
            # Remove common OCR noise characters
            symbol = ''.join(c for c in symbol if c.isalnum() or c in '.-_/')
            logger.info(f"Extracted symbol: '{symbol}' from {image_path}")
            return symbol
        else:
            logger.warning(f"No text found in {image_path}")
            return "UNKNOWN"
            
    except Exception as e:
        logger.error(f"OCR failed for {image_path}: {e}")
        return "UNKNOWN"


def crop_screenshot(image_path: str, output_dir: str, logger: logging.Logger) -> tuple:
    """Crop screenshot and return paths to cropped images."""
    try:
        try:
            from PIL import Image
        except ImportError:
            logger.error("PIL (Pillow) not available. Cannot crop images.")
            return None, None
        
        # Create a temporary directory for this specific image's crops
        # Structure: image_name_temp_crops/
        image_basename = os.path.splitext(os.path.basename(image_path))[0]
        temp_crop_dir = os.path.join(output_dir, f"{image_basename}_temp_crops")
        os.makedirs(temp_crop_dir, exist_ok=True)
        
        # Load the image
        try:
            img = Image.open(image_path)
            logger.info(f"Original image size: {img.size} (width x height)")
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return None, None
        
        # CROP 1: Small top left corner (same coordinates as image_cropper.py)
        top_left_x = 160
        top_left_y = 0
        top_left_width = 140
        top_left_height = 60
        
        # CROP 2: Vertical long rectangle in the middle-right area
        vertical_x = 2500
        vertical_y = 80
        vertical_width = 250
        vertical_height = 1430
        
        # Check if image is large enough for the crops
        img_width, img_height = img.size
        if img_width < vertical_x + vertical_width:
            logger.warning(f"Image width {img_width} is smaller than required {vertical_x + vertical_width}. Adjusting vertical crop.")
            vertical_x = max(0, img_width - vertical_width - 100)  # Move left if needed
            vertical_width = min(vertical_width, img_width - vertical_x)
        
        if img_height < vertical_y + vertical_height:
            logger.warning(f"Image height {img_height} is smaller than required {vertical_y + vertical_height}. Adjusting vertical crop.")
            vertical_height = min(vertical_height, img_height - vertical_y)
        
        logger.info(f"Using crop coordinates - Top left: ({top_left_x}, {top_left_y}, {top_left_width}, {top_left_height})")
        logger.info(f"Using crop coordinates - Vertical: ({vertical_x}, {vertical_y}, {vertical_width}, {vertical_height})")
        
        # Perform the crops
        crops = []
        
        # Crop 1: Top left corner
        try:
            top_left_crop = img.crop((
                top_left_x, 
                top_left_y, 
                top_left_x + top_left_width, 
                top_left_y + top_left_height
            ))
            
            top_left_path = os.path.join(temp_crop_dir, "top_left_corner.png")
            top_left_crop.save(top_left_path)
            crops.append(("Top Left Corner", top_left_path, top_left_crop.size))
            logger.info(f"✓ Top left corner saved: {top_left_path}")
            
        except Exception as e:
            logger.error(f"Error cropping top left: {e}")
            return None, None
        
        # Crop 2: Vertical rectangle
        try:
            vertical_crop = img.crop((
                vertical_x, 
                vertical_y, 
                vertical_x + vertical_width, 
                vertical_y + vertical_height
            ))
            
            vertical_path = os.path.join(temp_crop_dir, "vertical_rectangle.png")
            vertical_crop.save(vertical_path)
            crops.append(("Vertical Rectangle", vertical_path, vertical_crop.size))
            logger.info(f"✓ Vertical rectangle saved: {vertical_path}")
            
        except Exception as e:
            logger.error(f"Error cropping vertical rectangle: {e}")
            return None, None
        
        # Verify files exist
        if not os.path.exists(top_left_path):
            logger.error(f"Top left crop file not found: {top_left_path}")
            return None, None
        if not os.path.exists(vertical_path):
            logger.error(f"Vertical crop file not found: {vertical_path}")
            return None, None
        
        logger.info(f"Successfully cropped {image_path}")
        logger.info(f"Top left: {top_left_path}")
        logger.info(f"Vertical: {vertical_path}")
        return top_left_path, vertical_path
            
    except Exception as e:
        logger.error(f"Cropping failed for {image_path}: {e}")
        return None, None


def refresh_single_tab(driver, tab_info: dict, index: int, logger: logging.Logger) -> bool:
    """Refresh a single tab and return success status."""
    try:
        driver.switch_to.window(tab_info["handle"])
        driver.refresh()
        logger.info(f"Refreshed tab {index}: {tab_info['url']}")
        return True
    except WebDriverException as e:
        logger.error(f"Failed to refresh tab {index}: {e}")
        return False


def capture_single_tab(driver, tab_info: dict, index: int, output_dir: str, timestamp_for_filename: str, logger: logging.Logger) -> str:
    """Capture a single tab and return the saved path."""
    try:
        driver.switch_to.window(tab_info["handle"])
        time.sleep(0.8)
        filename = f"{timestamp_for_filename}_tab{index}_{tab_info['host']}.png"
        path = os.path.join(output_dir, filename)
        
        ok = driver.save_screenshot(path)
        if ok:
            logger.info(f"Saved screenshot: {path}")
            return path
        else:
            logger.error(f"Failed to save screenshot for tab {index}")
            return None
    except WebDriverException as e:
        logger.error(f"Failed to capture tab {index}: {e}")
        return None


def refresh_all_tabs_parallel(driver, logger: logging.Logger, max_workers: int = 4) -> None:
    """Refresh all tabs in parallel."""
    try:
        tabs = get_tab_metadata(driver)
        logger.info(f"Refreshing {len(tabs)} tab(s) in parallel...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for index, tab in enumerate(tabs, start=1):
                future = executor.submit(refresh_single_tab, driver, tab, index, logger)
                futures.append(future)
            
            # Wait for all refreshes to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Refresh future failed: {e}")
                    
    except Exception as e:
        logger.exception(f"Unexpected error during parallel refresh: {e}")


def ensure_capture_dir(base_dir: str, capture_time: datetime) -> str:
    date_dir = capture_time.strftime("%Y%m%d")
    time_dir = capture_time.strftime("%H%M")
    full_path = os.path.join(base_dir, date_dir, time_dir)
    os.makedirs(full_path, exist_ok=True)
    return full_path


def capture_all_tabs_sequential(driver, logger: logging.Logger, output_base: str, capture_time: datetime) -> list:
    """Capture all tabs sequentially (one at a time)."""
    tabs = get_tab_metadata(driver)
    output_dir = ensure_capture_dir(output_base, capture_time)
    timestamp_for_filename = capture_time.strftime("%Y%m%d_%H%M%S")

    logger.info(f"Capturing screenshots for {len(tabs)} tab(s) sequentially → {output_dir}")
    
    saved_paths = []
    for index, tab in enumerate(tabs, start=1):
        try:
            result = capture_single_tab(driver, tab, index, output_dir, timestamp_for_filename, logger)
            if result:
                saved_paths.append(result)
        except Exception as e:
            logger.error(f"Capture failed for tab {index}: {e}")
    
    return saved_paths


def process_single_image(image_path: str, output_dir: str, logger: logging.Logger) -> tuple:
    """Process a single image: crop, extract symbol, analyze vertical rectangle."""
    try:
        # Step 1: Crop the image - use the time directory (output_dir) for temp_crops
        top_left_path, vertical_path = crop_screenshot(image_path, output_dir, logger)
        if not top_left_path or not vertical_path:
            return (image_path, {"error": "Cropping failed"})
        
        # Step 2: Extract symbol from top left corner
        symbol = extract_symbol_from_image(top_left_path, logger)
        
        # Step 3: Analyze vertical rectangle for strategy signals
        if CandleStrategyAnalyzer is None:
            return (image_path, {"error": "CandleStrategyAnalyzer not available", "symbol": symbol})
        
        analyzer = CandleStrategyAnalyzer(vertical_path)
        results = analyzer.run_analysis()
        
        # Add symbol to results
        if "error" not in results:
            results["symbol"] = symbol
        
        return (image_path, results)
        
    except Exception as e:
        logger.error(f"Processing failed for {image_path}: {e}")
        return (image_path, {"error": str(e)})


def run_strategy_concurrently(image_paths: list, output_dir: str, logger: logging.Logger, max_workers: int = 4) -> None:
    """Process all images concurrently: crop, extract symbol, analyze strategy."""
    if not image_paths:
        logger.info("No images to analyze.")
        return

    logger.info(f"Processing {len(image_paths)} image(s) with up to {max_workers} worker(s)...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_single_image, path, output_dir, logger): path for path in image_paths}
        for future in as_completed(futures):
            path = futures[future]
            try:
                img_path, result = future.result()
                if "error" in result:
                    logger.error(f"Processing failed for {img_path}: {result['error']}")
                    # Clean terminal output for errors
                    print(f"JSON Output: {{\"Symbol\":\"ERROR\",\"STM\":\"error\",\"TD\":\"error\"}}")
                else:
                    symbol = result.get("symbol", "UNKNOWN")
                    stm = result.get("STM", "none")
                    td = result.get("TD", "none")
                    logger.info(f"Analysis: {img_path} → Symbol={symbol}, STM={stm}, TD={td}")
                    # Clean terminal output - only JSON
                    print(f"JSON Output: {{\"Symbol\":\"{symbol}\",\"STM\":\"{stm}\",\"TD\":\"{td}\"}}")
            except Exception as e:
                logger.exception(f"Exception in processing for {path}: {e}")
                # Clean terminal output for exceptions
                print(f"JSON Output: {{\"Symbol\":\"ERROR\",\"STM\":\"error\",\"TD\":\"error\"}}")


def ceil_to_next_5min_mark(now: datetime) -> datetime:
    minute = (now.minute // 5) * 5
    if now.minute % 5 == 0 and now.second == 0:
        next_mark = now
    else:
        next_minute = minute + 5
        carry_hours = next_minute // 60
        next_minute = next_minute % 60
        next_hour = (now.hour + carry_hours) % 24
        next_day = now + timedelta(days=1) if (now.hour + carry_hours) >= 24 else now
        next_mark = next_day.replace(hour=next_hour, minute=next_minute, second=0, microsecond=0)
    return next_mark


def main():
    logger = configure_logging("main.log")

    if open_browser is None or auto_login is None:
        logger.error("Failed to import browser helpers from scrape.py. Exiting.")
        print("ERROR: scrape.py helpers not available. Cannot continue.")
        return

    try:
        driver = open_browser()
    except Exception as e:
        logger.exception(f"Unable to open browser: {e}")
        return

    try:
        driver.get("https://www.tradingview.com/")
        try:
            auto_login(driver)
        except Exception as e:
            logger.warning(f"Login flow encountered an issue: {e}. Continuing anyway.")

        wait_for_user_ready(logger)
        # get the first tab's url
        first_tab_url = driver.current_url
        if "%3A" in first_tab_url:
            base, _ = first_tab_url.split("%3A", 1)  # split once, discard the old stock part
            for stock in stock_list:
                new_url = f"{base}%3A{stock}"
                # Open new tab with the URL
                driver.execute_script(f"window.open('{new_url}', '_blank');")
        else:
            pass

        base_output_dir = "screen_caps"
        logger.info("Entering scheduled loop: refresh at -30s, capture at 5-minute marks.")
        print("Scheduled operations started. Monitoring every 5 minutes...")

        while True:
            now = datetime.now()
            capture_time = ceil_to_next_5min_mark(now)
            refresh_time = capture_time - timedelta(seconds=30)

            if now >= refresh_time:
                refresh_delay = 0
            else:
                refresh_delay = (refresh_time - now).total_seconds()

            logger.info(f"Next capture at {capture_time.strftime('%H:%M:%S')}; refreshing at {refresh_time.strftime('%H:%M:%S')} (in {max(0, int(refresh_delay))}s)")
            if refresh_delay > 0:
                time.sleep(refresh_delay)

            logger.info("Refreshing all tabs...")
            refresh_all_tabs_parallel(driver, logger, max_workers=min(8, max(2, os.cpu_count() or 4)))

            now = datetime.now()
            if now >= capture_time:
                capture_delay = 0
            else:
                capture_delay = (capture_time - now).total_seconds()

            if capture_delay > 0:
                time.sleep(capture_delay)

            logger.info(f"Capturing screenshots at {capture_time.strftime('%H:%M:%S')}...")
            images = capture_all_tabs_sequential(driver, logger, base_output_dir, capture_time)

            # Get the specific time directory for temp_crops
            time_output_dir = ensure_capture_dir(base_output_dir, capture_time)
            
            try:
                logger.info("Processing images and analyzing strategies...")
                run_strategy_concurrently(images, time_output_dir, logger, max_workers=min(8, max(2, os.cpu_count() or 4)))
            except Exception as e:
                logger.exception(f"Error running strategy analysis: {e}")

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Shutting down.")
        print("\nShutting down...")
    except Exception as e:
        logger.exception(f"Fatal error in main loop: {e}")
        print(f"ERROR: {e}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        logger.info("Browser closed. Done.")
        print("Done.")


if __name__ == "__main__":
    main()


