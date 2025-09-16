import time
import sys
import pytz
import asyncio
import threading
from datetime import datetime

try:
    from main_with_ib_trading import IBTradingManager, configure_logging, IB_AVAILABLE
except Exception as e:
    print(f"Failed to import trading modules: {e}")
    sys.exit(1)


def _trade_in_thread(symbol: str, logger) -> bool:
    # Create and set an asyncio event loop for ib_async within this worker thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    manager = IBTradingManager(symbols=[symbol], special_symbols=[], init_capital=10000, logger=logger)

    try:
        if not manager.connect():
            logger.error("Unable to connect to IB API in worker thread.")
            return False

        logger.info("Connected in worker thread. Waiting 10 seconds before requesting market data...")
        time.sleep(10)

        price = manager.get_current_price(symbol)
        if price is None:
            logger.error(f"No price received for {symbol}. Aborting.")
            return False

        logger.info(f"Current {symbol} price: ${price:.2f}")

        # Force the position size calculation to return exactly 1 share for this test
        manager.current_capital = price * 15.0

        signal_data = {"STM": "buy", "TD": "buy", "Zigzag": "buy"}
        logger.info(f"Placing BUY order for 1 share of {symbol}...")
        placed = manager.place_order(symbol, "buy", price, signal_data)
        time.sleep(5)
        return placed
    finally:
        try:
            manager.disconnect()
        except Exception:
            pass


def main() -> None:
    logger = configure_logging("test_ib.log")

    if not IB_AVAILABLE:
        logger.error("IB API not available. Install ib_async and ensure TWS/Gateway running.")
        print("IB API not available. Exiting.")
        return

    symbol = "AAPL"

    result_holder = {"ok": False}

    def worker():
        result_holder["ok"] = _trade_in_thread(symbol, logger)

    t = threading.Thread(target=worker, name="IB-Trade-Thread", daemon=False)
    t.start()
    t.join()

    if result_holder["ok"]:
        logger.info(f"Order placement success for {symbol} (submission sent to IB).")
    else:
        logger.error(f"Order placement failed for {symbol}.")

    logger.info("Test script finished.")


if __name__ == "__main__":
    main()


