import os
import sys
import time
import math
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import platform
import pytz
import json
import random
import numpy as np
import pandas as pd
import csv
import threading
import asyncio

#### make sure the stock is within the same stock exchange e.g. NASDAQ, NYSE, etc.
stock_list = ["NVDA","TSLA","NFLX","OPEN","AMD","AVGO","META","WMT","IBM","UBER","OKLO"]
# stock_list = []
# Special symbols that should always be included
special_symbols = ["QQQ"]

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

# Global, thread-safe market price cache updated by ibapi callbacks
GLOBAL_PRICE_CACHE = {}
# GLOBAL_PRICE_LOCK = threading.Lock()

# IB Trading imports (ibapi replacement for ib_async)
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.order import Order
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("Warning: ibapi not available. Trading functionality disabled.")

# Lightweight ibapi threaded app wrapper (reference: test.py)
class IBApiApp(EWrapper, EClient):
    def __init__(self, logger: logging.Logger):
        EClient.__init__(self, self)
        self.logger = logger or logging.getLogger(__name__)
        self._thread = None
        self._connected_event = threading.Event()
        self._next_id_event = threading.Event()
        self.next_order_id = None
        self._req_id = 1000
        self._lock = threading.Lock()
        self.reqId_to_symbol = {}
        self.symbol_to_price = {}
        self._active_market_data_req_ids = set()
        # Historical data buffers and events keyed by reqId
        self._hist_data = {}
        self._hist_events = {}
        
        # Order execution tracking
        self.order_status = {}  # {order_id: order_status_info}
        self.executions = {}    # {order_id: [execution_details]}
        self.filled_orders = {} # {order_id: filled_price_info}
        self.order_events = {}  # {order_id: threading.Event} for waiting on fills

    # Connection helpers
    def connect_and_start(self, host: str, port: int, client_id: int, wait_timeout: float = 5.0):
        self.connect(host, port, client_id)
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        # Wait for nextValidId which signals readiness
        if not self._next_id_event.wait(timeout=wait_timeout):
            raise RuntimeError("Timed out waiting for nextValidId from TWS/Gateway")

    def disconnect(self):
        try:
            super().disconnect()
        except Exception:
            pass

    # EWrapper callbacks
    def nextValidId(self, orderId: int):
        self.next_order_id = orderId
        self._next_id_event.set()

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        try:
            self.logger.error(f"IB Error reqId={reqId}, code={errorCode}, msg={errorString}")
        except Exception:
            pass

    def tickPrice(self, reqId, tickType, price, attrib):
        # 4 = LAST price, 9 = CLOSE
        if price is None or price <= 0:
            return
        symbol = self.reqId_to_symbol.get(reqId)
        if not symbol:
            return
        # Only accept LAST (4) or CLOSE (9). Prefer LAST over CLOSE.
        if tickType == 4:
            # store last under the symbol key
            self.symbol_to_price[symbol] = price
        elif tickType == 9:
            # store close separately as fallback
            self.symbol_to_price[f"{symbol}_close"] = price
        # Publish preferred price (LAST then CLOSE) into global cache atomically
        preferred_value = self.symbol_to_price.get(symbol)
        if not preferred_value:
            preferred_value = self.symbol_to_price.get(f"{symbol}_close")
        if preferred_value and preferred_value > 0:
            try:
                # with GLOBAL_PRICE_LOCK:
                GLOBAL_PRICE_CACHE[symbol] = float(preferred_value)
                # print("Updated global price cache for", symbol, preferred_value)
                # print(GLOBAL_PRICE_CACHE)
                    # self.logger.info("Updated global price cache for", symbol, preferred_value)
            except Exception:
                pass

    # Historical data callbacks
    def historicalData(self, reqId, bar):
        try:
            if reqId not in self._hist_data:
                self._hist_data[reqId] = []
            # Store minimal fields to keep memory small
            self._hist_data[reqId].append({
                'date': getattr(bar, 'date', None),
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': float(bar.volume) if hasattr(bar, 'volume') else None,
            })
        except Exception:
            pass

    def historicalDataEnd(self, reqId, start, end):
        try:
            ev = self._hist_events.get(reqId)
            if ev:
                ev.set()
        except Exception:
            pass

    # Order execution callbacks
    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        """Called when order status changes"""
        try:
            self.logger.info(f"Order {orderId} status: {status}, filled: {filled}, remaining: {remaining}, avgFillPrice: {avgFillPrice}")
            
            # Store order status
            self.order_status[orderId] = {
                'status': status,
                'filled': filled,
                'remaining': remaining,
                'avgFillPrice': avgFillPrice,
                'lastFillPrice': lastFillPrice,
                'timestamp': datetime.now()
            }
            
            # Check if order is filled
            if status == "Filled" and filled > 0:
                self.filled_orders[orderId] = {
                    'filled_quantity': filled,
                    'avg_fill_price': avgFillPrice,
                    'last_fill_price': lastFillPrice,
                    'fill_time': datetime.now(),
                    'status': status
                }
                self.logger.info(f"🎉 ORDER FILLED! Order {orderId}: {filled} shares at avg price ${avgFillPrice:.2f}")
                
                # Signal waiting threads
                if orderId in self.order_events:
                    self.order_events[orderId].set()
        except Exception as e:
            self.logger.error(f"Error in orderStatus callback: {e}")

    def execDetails(self, reqId, contract, execution):
        """Called when execution details are received"""
        try:
            self.logger.info(f"Execution details - Order {execution.orderId}: {execution.shares} shares at ${execution.avgPrice:.2f}")
            
            # Store execution details
            if execution.orderId not in self.executions:
                self.executions[execution.orderId] = []
            
            self.executions[execution.orderId].append({
                'execId': execution.execId,
                'time': execution.time,
                'account': execution.acctNumber,
                'exchange': execution.exchange,
                'side': execution.side,
                'shares': execution.shares,
                'price': execution.price,
                'avgPrice': execution.avgPrice,
                'orderId': execution.orderId,
                'cumQty': execution.cumQty,
                'permId': execution.permId
            })
        except Exception as e:
            self.logger.error(f"Error in execDetails callback: {e}")

    def openOrder(self, orderId, contract, order, orderState):
        """Called when order details are received"""
        try:
            self.logger.info(f"Open order {orderId}: {order.action} {order.totalQuantity} {contract.symbol} @ {order.lmtPrice if hasattr(order, 'lmtPrice') else 'Market'}")
        except Exception as e:
            self.logger.error(f"Error in openOrder callback: {e}")

    def openOrderEnd(self):
        """Called when all open orders have been sent"""
        self.logger.info("Open orders end")

    def request_historical_5m(self, symbol: str, durationStr: str = "1 D", barSizeSetting: str = "5 mins", useRTH: int = 0, timeout: float = 5.0):
        """Request recent historical bars and return list of bar dicts."""
        with self._lock:
            self._req_id += 1
            req_id = self._req_id
        # Prepare buffers
        self._hist_data[req_id] = []
        ev = threading.Event()
        self._hist_events[req_id] = ev

        # Build contract
        contract = Contract()
        contract.symbol = symbol
        contract.secType = 'STK'
        contract.exchange = 'SMART'
        contract.currency = 'USD'

        end_time = datetime.now().strftime("%Y%m%d %H:%M:%S")
        try:
            self.reqHistoricalData(
                req_id,
                contract,
                end_time,
                durationStr,
                barSizeSetting,
                "TRADES",
                useRTH,
                1,
                False,
                []
            )
        except Exception as e:
            try:
                self.logger.error(f"reqHistoricalData failed for {symbol}: {e}")
            except Exception:
                pass
            return []

        # Wait until end or timeout
        ev.wait(timeout=max(0.5, timeout))
        data = self._hist_data.get(req_id, [])
        # Cleanup
        try:
            del self._hist_data[req_id]
            del self._hist_events[req_id]
        except Exception:
            pass
        return data

    # Convenience APIs
    def request_market_price(self, symbol: str, timeout: float = 2.0) -> float:
        with self._lock:
            self._req_id += 1
            req_id = self._req_id
        # Build contract
        contract = Contract()
        contract.symbol = symbol
        contract.secType = 'STK'
        contract.exchange = 'SMART'
        contract.currency = 'USD'
        self.reqId_to_symbol[req_id] = symbol
        try:
            self.reqMktData(req_id, contract, '', False, False, [])
        except Exception as e:
            self.logger.error(f"reqMktData failed for {symbol}: {e}")
            return None
        # Poll for price up to timeout
        deadline = time.time() + timeout
        price = None
        while time.time() < deadline:
            price = self.symbol_to_price.get(symbol)
            if price and price > 0:
                break
            time.sleep(0.05)
        try:
            self.cancelMktData(req_id)
        except Exception:
            pass
        return price if price and price > 0 else None

    # Continuous market data subscription helpers
    def _build_stock_contract(self, symbol: str) -> Contract:
        c = Contract()
        c.symbol = symbol
        c.secType = 'STK'
        c.exchange = 'SMART'
        c.currency = 'USD'
        return c

    def subscribe_market_data_stream(self, symbols: list):
        for symbol in symbols:
            try:
                with self._lock:
                    self._req_id += 1
                    req_id = self._req_id
                self.reqId_to_symbol[req_id] = symbol
                contract = self._build_stock_contract(symbol)
                self.reqMktData(req_id, contract, '', False, False, [])
                self._active_market_data_req_ids.add(req_id)
                # Initialize cache entry to avoid KeyErrors on early reads
                # with GLOBAL_PRICE_LOCK:
                GLOBAL_PRICE_CACHE.setdefault(symbol, None)
            except Exception as e:
                try:
                    self.logger.error(f"Failed subscribing market data for {symbol}: {e}")
                except Exception:
                    pass

    def cancel_all_market_data(self):
        for req_id in list(self._active_market_data_req_ids):
            try:
                self.cancelMktData(req_id)
            except Exception:
                pass
            finally:
                self._active_market_data_req_ids.discard(req_id)

    def place_order(self, contract: Contract, order: Order):
        # Ensure we have a valid next order id
        start = time.time()
        while self.next_order_id is None and (time.time() - start) < 5.0:
            time.sleep(0.05)
        if self.next_order_id is None:
            raise RuntimeError("No next order id available from IB")
        with self._lock:
            order_id = self.next_order_id
            self.next_order_id += 1
        try:
            super().placeOrder(order_id, contract, order)
        except Exception as e:
            self.logger.error(f"placeOrder failed for {contract.symbol}: {e}")
            raise
        return order_id

    def wait_for_fill(self, order_id: int, timeout: float = 30.0) -> dict:
        """Wait for order to be filled and return fill details"""
        # Create event for this order if it doesn't exist
        if order_id not in self.order_events:
            self.order_events[order_id] = threading.Event()
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if order_id in self.filled_orders:
                return self.filled_orders[order_id]
            
            # Check if order is cancelled or rejected
            if order_id in self.order_status:
                status = self.order_status[order_id]['status']
                if status in ['Cancelled', 'Rejected']:
                    self.logger.error(f"Order {order_id} was {status}")
                    return None
            
            # Wait for event with short timeout
            if self.order_events[order_id].wait(0.01):
                if order_id in self.filled_orders:
                    return self.filled_orders[order_id]
        
        self.logger.warning(f"Timeout waiting for order {order_id} to fill")
        return None

    def get_order_status(self, order_id: int) -> dict:
        """Get current status of an order"""
        return self.order_status.get(order_id, {})

    def get_executions(self, order_id: int) -> list:
        """Get execution details for an order"""
        return self.executions.get(order_id, [])

    def get_filled_price(self, order_id: int) -> float:
        """Get the average fill price for a filled order"""
        if order_id in self.filled_orders:
            return self.filled_orders[order_id]['avg_fill_price']
        return None

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


class IBTradingManager:
    """
    Interactive Brokers trading manager that handles connections, data, and orders.
    """
    
    def __init__(self, 
                 symbols: list,
                 special_symbols: list = None,
                 ib_connection: IBApiApp = None,  # Accept external connection
                 ib_host: str = '127.0.0.1', 
                 ib_port: int = 4002, 
                 ib_client_id: int = None,
                 init_capital: float = 10000,
                 logger: logging.Logger = None):
        
        self.symbols = symbols
        self.special_symbols = special_symbols or []
        # Combine regular symbols with special symbols for complete list
        self.all_symbols = list(set(symbols + self.special_symbols))
        
        # Use external connection if provided, otherwise store connection parameters
        self.ib = ib_connection  # Use external connection
        self._is_external_connection = ib_connection is not None  # Flag to track if connection is external
        self.ib_host = ib_host
        self.ib_port = ib_port
        self.ib_client_id = ib_client_id or self._generate_client_id()
        self.init_capital = init_capital
        self.current_capital = init_capital
        self.logger = logger or logging.getLogger(__name__)
        
        # Contracts dictionary
        self.contracts = {}
        
        # Trading state - track positions per symbol
        self.current_positions = {}  # {symbol: position_info}
        self.last_signal_times = {}  # {symbol: datetime}
        
        # Initialize position tracking for all symbols (regular + special)
        for symbol in self.all_symbols:
            self.current_positions[symbol] = None
            self.last_signal_times[symbol] = None
        
        # Log which symbols we're tracking
        self.logger.info(f"Regular symbols: {self.symbols}")
        self.logger.info(f"Special symbols: {self.special_symbols}")
        self.logger.info(f"All tracked symbols: {self.all_symbols}")
        
        # Trading record files
        self.trades_log_file = "ib_trading_log.txt"  # Keep for backup logging
        self.trades_csv_file = "trading_records.csv"
        self._initialize_log_files()
        self._initialize_csv_file()
        
        # Thread-local IB connections for use under ThreadPoolExecutor
        self._thread_local = threading.local()
        self._thread_ib_conns = []  # keep references for cleanup
    
    def _generate_client_id(self):
        """Generate a unique client ID."""
        today = datetime.now(pytz.timezone('US/Eastern'))
        weekday = today.weekday()
        random_number = random.randint(1, 60)
        return random_number + weekday
    
    def _initialize_log_files(self):
        """Initialize log files if they don't exist."""
        if not os.path.exists(self.trades_log_file):
            with open(self.trades_log_file, "w") as f:
                f.write("==== IB Trading Log Start ====\n")
    
    def _initialize_csv_file(self):
        """Initialize CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.trades_csv_file):
            headers = [
                'Trade_ID',
                'Entry_Time',
                'Exit_Time', 
                'Symbol',
                'Signal_Type',
                'Action',  # ENTRY or EXIT
                'Shares',
                'Entry_Price',
                'Exit_Price',
                'Take_Profit',
                'Stop_Loss',
                'PnL_Dollar',
                'PnL_Percent',
                'Exit_Reason',
                'Duration_Minutes',
                'STM_Signal',
                'TD_Signal', 
                'Zigzag_Signal',
                'Market_Hours',
                'Order_Type',
                'Notes'
            ]
            
            with open(self.trades_csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            
            self.logger.info(f"Created new trading CSV file: {self.trades_csv_file}")
        else:
            self.logger.info(f"Using existing trading CSV file: {self.trades_csv_file}")
    
    def _generate_trade_id(self) -> str:
        """Generate a unique trade ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = random.randint(100, 999)
        return f"TRADE_{timestamp}_{random_suffix}"
    
    def connect(self):
        """Connect to Interactive Brokers API using ibapi or use existing connection."""
        if not IB_AVAILABLE:
            self.logger.error("IB API not available. Cannot connect.")
            return False

        # If external connection provided, use it
        if self.ib is not None:
            self.logger.info("Using provided external IB connection")
            # Create stock contracts for each symbol (regular + special)
            for symbol in self.all_symbols:
                c = Contract()
                c.symbol = symbol
                c.secType = 'STK'
                c.exchange = 'SMART'
                c.currency = 'USD'
                self.contracts[symbol] = c
                self.logger.info(f"Created stock contract for {symbol}")

            # Start continuous market data stream for all symbols
            try:
                self.ib.subscribe_market_data_stream(self.all_symbols)
                self.logger.info(f"Subscribed to market data stream for {len(self.all_symbols)} symbols")
            except Exception as e:
                self.logger.error(f"Failed to subscribe market data streams: {e}")

            return True

        # Otherwise, create new connection
        try:
            self.ib = IBApiApp(self.logger)
            self.logger.info(f"Connecting to IB at {self.ib_host}:{self.ib_port} with client ID {self.ib_client_id}...")
            self.ib.connect_and_start(self.ib_host, self.ib_port, self.ib_client_id)
            self.logger.info("Connected to IB!")

            # Create stock contracts for each symbol (regular + special)
            for symbol in self.all_symbols:
                c = Contract()
                c.symbol = symbol
                c.secType = 'STK'
                c.exchange = 'SMART'
                c.currency = 'USD'
                self.contracts[symbol] = c
                self.logger.info(f"Created stock contract for {symbol}")

            # Start continuous market data stream for all symbols
            try:
                self.ib.subscribe_market_data_stream(self.all_symbols)
                self.logger.info(f"Subscribed to market data stream for {len(self.all_symbols)} symbols")
            except Exception as e:
                self.logger.error(f"Failed to subscribe market data streams: {e}")

            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to IB: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from Interactive Brokers API."""
        if self.ib:
            try:
                try:
                    self.ib.cancel_all_market_data()
                except Exception:
                    pass
                # Only disconnect if we created the connection ourselves
                # Don't disconnect external connections
                if hasattr(self, '_is_external_connection') and self._is_external_connection:
                    self.logger.info("Keeping external IB connection alive")
                else:
                    self.ib.disconnect()
                    self.logger.info("Disconnected from IB")
            except Exception:
                pass
        # Disconnect any thread-local IB connections
        try:
            for tib in list(self._thread_ib_conns):
                try:
                    if tib and tib.isConnected():
                        tib.disconnect()
                except Exception:
                    pass
            self._thread_ib_conns.clear()
        except Exception:
            pass
    
    def get_current_price(self, symbol: str) -> float:
        """Atomically read the latest price from the global cache."""
        try:
            # with GLOBAL_PRICE_LOCK:
            price = GLOBAL_PRICE_CACHE.get(symbol)
            if price is None or (isinstance(price, (int, float)) and price <= 0):
                return None
            return float(price)
        except Exception as e:
            self.logger.error(f"Error reading cached price for {symbol}: {e}")
            return None
    
    def calculate_fibonacci_levels(self, symbol: str, entry_price: float, signal_type: str, confidence: float):
        """
        Calculate fibonacci-based take profit and stop loss levels.
        
        Args:
            symbol: Stock symbol
            entry_price: Entry price for the position
            signal_type: 'buy' or 'sell'
        
        Returns:
            tuple: (take_profit, stop_loss)
        """
        try:
            ib = self.ib
            if ib is None:
                # Fallback: simple 1% TP/0.5% SL
                if signal_type == 'buy':
                    self.logger.info(f"Symbol: {symbol}, **Not using Fibo SL AND TP, Entry Price: {entry_price:.2f}, Take Profit: {entry_price * 1.01:.2f}, Stop Loss: {entry_price * 0.995:.2f}, reason: no connection")
                    return entry_price * 1.01, entry_price * 0.995
                else:
                    self.logger.info(f"Symbol: {symbol}, **Not using Fibo SL AND TP, Entry Price: {entry_price:.2f}, Take Profit: {entry_price * 0.99:.2f}, Stop Loss: {entry_price * 1.005:.2f}, reason: no connection")
                    return entry_price * 0.99, entry_price * 1.005
                
            # Fetch recent 5m bars (1 day) including extended hours
            bars = ib.request_historical_5m(symbol, durationStr="1 D", barSizeSetting="5 mins", useRTH=0, timeout=6.0)
            if not bars:
                # Fallback if no data
                if signal_type == 'buy':
                    self.logger.info(f"Symbol: {symbol}, **Not using Fibo SL AND TP, Entry Price: {entry_price:.2f}, Take Profit: {entry_price * 1.01:.2f}, Stop Loss: {entry_price * 0.995:.2f}, reason: no bars")
                    return entry_price * 1.01, entry_price * 0.995
                else:
                    self.logger.info(f"Symbol: {symbol}, **Not using Fibo SL AND TP, Entry Price: {entry_price:.2f}, Take Profit: {entry_price * 0.99:.2f}, Stop Loss: {entry_price * 1.005:.2f}, reason: no bars")
                    return entry_price * 0.99, entry_price * 1.005
            
            # Use last 33 bars
            last = bars[-33:] if len(bars) >= 33 else list(bars)
            highs = [float(b['high']) for b in last]
            lows = [float(b['low']) for b in last]
            recent_low = min(lows)
            recent_high = max(highs)

            if confidence is None:
                confidence = 0.5

            if signal_type.lower() == 'buy':
                risk_long = entry_price - recent_low
                if risk_long <= 0:
                    # Entry below recent_low (or equal) → use range-based fallback to avoid negative risk
                    range_span = max(recent_high - recent_low, entry_price * 0.005)
                    risk_long = range_span
                fib_sl = 0.382 + (1 - confidence) * (0.618 - 0.382)
                fib_tp = 1.382 + confidence * (1.618 - 1.382)
                stop_loss = entry_price - risk_long * fib_sl * 2
                take_profit = entry_price + risk_long * fib_tp
                # Enforce directional sanity for BUY
                if take_profit <= entry_price or stop_loss >= entry_price:
                    try:
                        self.logger.warning(
                            f"BUY TP/SL adjusted: entry={entry_price:.2f}, tp={take_profit:.2f}, sl={stop_loss:.2f}, "
                            f"recent_low={recent_low:.2f}, recent_high={recent_high:.2f}"
                        )
                    except Exception:
                        pass
                    stop_loss = min(recent_low, entry_price * 0.995)
                    adjusted_risk = max(entry_price - stop_loss, max(recent_high - recent_low, entry_price * 0.005))
                    take_profit = entry_price + adjusted_risk * fib_tp
                self.logger.info(f"Symbol: {symbol}, **Fibo SL: {fib_sl:.2f}, Fibo TP: {fib_tp:.2f}, Stop Loss: {stop_loss:.2f}, Take Profit: {take_profit:.2f}")
            else:
                risk_short = recent_high - entry_price
                if risk_short <= 0:
                    # Entry above recent_high (or equal) → use range-based fallback to avoid negative risk
                    range_span = max(recent_high - recent_low, entry_price * 0.005)
                    risk_short = range_span
                fib_sl = 0.382 + (1 - confidence) * (0.618 - 0.382)
                fib_tp = 1.382 + confidence * (1.618 - 1.382)
                stop_loss = entry_price + risk_short * fib_sl * 2
                take_profit = entry_price - risk_short * fib_tp
                # Enforce directional sanity for SELL
                if take_profit >= entry_price or stop_loss <= entry_price:
                    try:
                        self.logger.warning(
                            f"SELL TP/SL adjusted: entry={entry_price:.2f}, tp={take_profit:.2f}, sl={stop_loss:.2f}, "
                            f"recent_low={recent_low:.2f}, recent_high={recent_high:.2f}"
                        )
                    except Exception:
                        pass
                    stop_loss = max(recent_high, entry_price * 1.005)
                    adjusted_risk = max(stop_loss - entry_price, max(recent_high - recent_low, entry_price * 0.005))
                    take_profit = entry_price - adjusted_risk * fib_tp
                self.logger.info(f"Symbol: {symbol}, **Fibo SL: {fib_sl:.2f}, Fibo TP: {fib_tp:.2f}, Stop Loss: {stop_loss:.2f}, Take Profit: {take_profit:.2f}")

            return float(take_profit), float(stop_loss)
        except Exception as e:
            try:
                self.logger.error(f"calculate_fibonacci_levels failed for {symbol}: {e}")
            except Exception:
                pass
            
            self.logger.error(f"calculate_fibonacci_levels failed for {symbol}: {e}")
            # Final fallback
            if signal_type == 'buy':
                return entry_price * 1.01, entry_price * 0.995
            else:
                return entry_price * 0.99, entry_price * 1.005
    
    def calculate_position_size(self, symbol: str, entry_price: float) -> int:
        """Calculate position size based on available capital."""
        position_pct = 0.1  # Use 10% of capital per position
        position_value = self.current_capital * position_pct
        shares = int(position_value / entry_price)
        return max(1, shares)  # Minimum 1 share
    
    def place_order(self, symbol: str, signal_type: str, entry_price: float, signal_data: dict = None, confidence: float = 0):
        """
        Place an order based on the signal.
        
        Args:
            symbol: Stock symbol
            signal_type: 'buy' or 'sell'
            entry_price: Current market price
            signal_data: Dictionary containing STM, TD, Zigzag signals
        """
        try:
            # Calculate position size
            shares = self.calculate_position_size(symbol, entry_price)
            
            # Get current US time and market hours
            current_us_time = datetime.now(pytz.timezone('US/Eastern'))
            market_open = current_us_time.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = current_us_time.replace(hour=16, minute=0, second=0, microsecond=0)
            
            contract = self.contracts[symbol]
            ib = self.ib
            if ib is None:
                self.logger.error("No IB connection available for placing order")
                return False
            
            if signal_type == 'buy':
                action = 'BUY'
                limit_price = entry_price * 1.005  # 0.5% above current price
            else:
                action = 'SELL'
                limit_price = entry_price * 0.995  # 0.5% below current price
            
            # Determine order type and market hours status
            is_market_hours = market_open <= current_us_time < market_close
            
            if is_market_hours:
                # Market hours - use market order
                order = Order()
                order.action = action
                order.orderType = 'MKT'
                order.totalQuantity = shares
                order.tif = 'DAY'
                order_type = "Market"
                order.eTradeOnly = ""
                order.firmQuoteOnly = ""
                self.logger.info(f"Placing market order: {action} {shares} shares of {symbol}")
            else:
                # Outside market hours - use limit order
                order = Order()
                order.action = action
                order.orderType = 'LMT'
                order.lmtPrice = round(limit_price, 2)
                order.totalQuantity = shares
                order.tif = 'DAY'
                order.outsideRth = True
                order.eTradeOnly = ""
                order.firmQuoteOnly = ""
                order_type = f"Limit @ ${limit_price:.2f}"
                self.logger.info(f"Placing limit order: {action} {shares} shares of {symbol} at ${limit_price:.2f}")

            # Place the order
            order_id = self.ib.place_order(contract, order)
            
            # Wait for order to fill and get actual filled price
            self.logger.info(f"Waiting for order {order_id} to fill...")
            fill_details = self.ib.wait_for_fill(order_id, timeout=30.0)
            
            if fill_details:
                actual_entry_price = fill_details['avg_fill_price']
                self.logger.info(f"✅ Order filled at actual price: ${actual_entry_price:.2f}")
            else:
                # Fallback to estimated price if no fill received
                actual_entry_price = entry_price
                self.logger.warning(f"⚠️ No fill confirmation received, using estimated price: ${actual_entry_price:.2f}")
            
            # Calculate fibonacci levels using actual filled price
            take_profit, stop_loss = self.calculate_fibonacci_levels(symbol, actual_entry_price, signal_type, confidence)
            # Generate unique trade ID
            trade_id = self._generate_trade_id()
            
            # Store position information
            position_info = {
                'trade_id': trade_id,
                'symbol': symbol,
                'signal_type': signal_type,
                'entry_price': actual_entry_price,  # Use actual filled price
                'shares': shares,
                'take_profit': take_profit,
                'stop_loss': stop_loss,
                'entry_time': current_us_time,
                'trade': order_id,
                'order_type': order_type,
                'is_market_hours': is_market_hours,
                'signal_data': signal_data or {}
            }
            
            self.current_positions[symbol] = position_info
            self.current_capital -= shares * entry_price * 0.1  # Reserve capital
            
            # Log the trade to both CSV and text log
            self._log_trade_to_csv(position_info, "ENTRY")
            self._log_trade(position_info, "ENTRY")
            
            self.logger.info(f"Order placed for {symbol}: {action} {shares} shares")
            self.logger.info(f"Take Profit: ${take_profit:.2f}, Stop Loss: ${stop_loss:.2f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error placing order for {symbol}: {e}")
            return False
    
    def close_position(self, symbol: str, reason: str = "Manual Close"):
        """
        Close a position for a specific symbol.
        
        Args:
            symbol: Stock symbol
            reason: Reason for closing
        """
        if symbol not in self.current_positions or self.current_positions[symbol] is None:
            self.logger.info(f"No position to close for {symbol}")
            return
        
        try:
            position_info = self.current_positions[symbol]
            current_price = self.get_current_price(symbol)
            
            if current_price is None:
                self.logger.error(f"Cannot get current price for {symbol}")
                return
            
            # Determine order action (opposite of entry)
            if position_info['signal_type'] == 'buy':
                action = 'SELL'
                limit_price = current_price * 0.995
            else:
                action = 'BUY'
                limit_price = current_price * 1.005
            
            # Get market hours
            current_us_time = datetime.now(pytz.timezone('US/Eastern'))
            market_open = current_us_time.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = current_us_time.replace(hour=16, minute=0, second=0, microsecond=0)
            
            contract = self.contracts[symbol]
            shares = position_info['shares']
            if self.ib is None:
                self.logger.error("No IB connection available for closing position")
                return
            
            # Place closing order
            if market_open <= current_us_time < market_close:
                order = Order()
                order.action = action
                order.orderType = 'MKT'
                order.totalQuantity = shares
                order.tif = 'DAY'
                order.eTradeOnly = ""
                order.firmQuoteOnly = ""
            else:
                order = Order()
                order.action = action
                order.orderType = 'LMT'
                order.lmtPrice = round(limit_price, 2)
                order.totalQuantity = shares
                order.tif = 'DAY'
                order.outsideRth = True
                order.eTradeOnly = ""
                order.firmQuoteOnly = ""
            
            order_id = self.ib.place_order(contract, order)
            
            # Wait for closing order to fill and get actual exit price
            self.logger.info(f"Waiting for closing order {order_id} to fill...")
            fill_details = self.ib.wait_for_fill(order_id, timeout=30.0)
            
            if fill_details:
                actual_exit_price = fill_details['avg_fill_price']
                self.logger.info(f"✅ Closing order filled at actual price: ${actual_exit_price:.2f}")
            else:
                # Fallback to current market price if no fill received
                actual_exit_price = current_price
                self.logger.warning(f"⚠️ No fill confirmation for closing order, using market price: ${actual_exit_price:.2f}")

            # Calculate P&L using actual exit price
            if position_info['signal_type'] == 'buy':
                pnl_pct = ((actual_exit_price - position_info['entry_price']) / position_info['entry_price']) * 100
            else:
                pnl_pct = ((position_info['entry_price'] - actual_exit_price) / position_info['entry_price']) * 100
            
            # Calculate dollar P&L using actual exit price
            pnl_dollar = (actual_exit_price - position_info['entry_price']) * shares
            if position_info['signal_type'] == 'sell':
                pnl_dollar = -pnl_dollar
            
            # Calculate trade duration
            duration_minutes = (current_us_time - position_info['entry_time']).total_seconds() / 60
            
            # Update position info for logging
            position_info['exit_price'] = actual_exit_price  # Use actual filled price
            position_info['exit_time'] = current_us_time
            position_info['pnl_pct'] = pnl_pct
            position_info['pnl_dollar'] = pnl_dollar
            position_info['duration_minutes'] = duration_minutes
            position_info['reason'] = reason
            position_info['exit_order_type'] = "Market" if market_open <= current_us_time < market_close else f"Limit @ ${limit_price:.2f}"
            
            # Log the closing trade to both CSV and text log
            self._log_trade_to_csv(position_info, "EXIT")
            self._log_trade(position_info, "EXIT")
            
            # Clear the position
            self.current_positions[symbol] = None
            self.current_capital += shares * current_price * 0.1  # Return capital
            
            self.logger.info(f"Position closed for {symbol}: {reason}")
            self.logger.info(f"P&L: {pnl_pct:.2f}%")
            
        except Exception as e:
            self.logger.error(f"Error closing position for {symbol}: {e}")
    
    def check_exit_conditions(self):
        """Check all positions for exit conditions."""
        for symbol, position_info in self.current_positions.items():
            if position_info is None:
                continue
            
            current_price = self.get_current_price(symbol)
            if current_price is None:
                continue
            
            # Check fibonacci-based exits
            if position_info['signal_type'] == 'buy':
                if current_price >= position_info['take_profit']:
                    self.close_position(symbol, "TAKE PROFIT")
                elif current_price <= position_info['stop_loss']:
                    self.close_position(symbol, "STOP LOSS")
            else:  # sell
                if current_price <= position_info['take_profit']:
                    self.close_position(symbol, "TAKE PROFIT")
                elif current_price >= position_info['stop_loss']:
                    self.close_position(symbol, "STOP LOSS")
    
    def close_all_positions_daily(self):
        """Close all positions at 07:59 US/Eastern daily."""
        self.logger.info("Daily position closure: Closing all positions")
        for symbol in self.all_symbols:
            if self.current_positions[symbol] is not None:
                self.close_position(symbol, "DAILY CLOSE")
    
    def handle_opposite_signal(self, symbol: str, new_signal_type: str):
        """Handle opposite signal by closing existing position."""
        current_position = self.current_positions[symbol]
        if current_position is None:
            return
        
        current_signal = current_position['signal_type']
        
        # Check if signals are opposite
        if ((current_signal == 'buy' and new_signal_type == 'sell') or 
            (current_signal == 'sell' and new_signal_type == 'buy')):
            self.close_position(symbol, f"OPPOSITE SIGNAL ({new_signal_type.upper()})")
    
    def _log_trade_to_csv(self, position_info: dict, trade_type: str):
        """Log trade details to CSV file."""
        try:
            signal_data = position_info.get('signal_data', {})
            
            # Prepare row data
            row_data = [
                position_info.get('trade_id', ''),
                position_info.get('entry_time', '').strftime('%Y-%m-%d %H:%M:%S') if position_info.get('entry_time') else '',
                position_info.get('exit_time', '').strftime('%Y-%m-%d %H:%M:%S') if position_info.get('exit_time') else '',
                position_info.get('symbol', ''),
                position_info.get('signal_type', '').upper(),
                trade_type,
                position_info.get('shares', 0),
                position_info.get('entry_price', 0),
                position_info.get('exit_price', 0) if trade_type == "EXIT" else '',
                position_info.get('take_profit', 0),
                position_info.get('stop_loss', 0),
                position_info.get('pnl_dollar', 0) if trade_type == "EXIT" else '',
                position_info.get('pnl_pct', 0) if trade_type == "EXIT" else '',
                position_info.get('reason', '') if trade_type == "EXIT" else '',
                position_info.get('duration_minutes', 0) if trade_type == "EXIT" else '',
                signal_data.get('STM', ''),
                signal_data.get('TD', ''),
                signal_data.get('Zigzag', ''),
                'Yes' if position_info.get('is_market_hours', False) else 'No',
                position_info.get('exit_order_type' if trade_type == "EXIT" else 'order_type', ''),
                f"Trade {trade_type.lower()}"
            ]
            
            # Write to CSV
            with open(self.trades_csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row_data)
                
            self.logger.debug(f"Logged {trade_type} to CSV: {position_info['symbol']} - {position_info.get('trade_id', '')}")
            
        except Exception as e:
            self.logger.error(f"Error logging to CSV: {e}")
    
    def _log_trade(self, position_info: dict, trade_type: str):
        """Log trade details to text file (backup logging)."""
        with open(self.trades_log_file, "a") as f:
            f.write("\n" + "="*60 + "\n")
            f.write(f"TRADE {trade_type}: {position_info['symbol']}\n")
            f.write(f"Trade ID: {position_info.get('trade_id', 'N/A')}\n")
            f.write(f"Time: {position_info.get('entry_time' if trade_type == 'ENTRY' else 'exit_time', datetime.now(pytz.timezone('US/Eastern')))}\n")
            f.write(f"Signal Type: {position_info['signal_type'].upper()}\n")
            f.write(f"Shares: {position_info['shares']}\n")
            
            if trade_type == "ENTRY":
                f.write(f"Entry Price: ${position_info['entry_price']:.2f}\n")
                f.write(f"Take Profit: ${position_info['take_profit']:.2f}\n")
                f.write(f"Stop Loss: ${position_info['stop_loss']:.2f}\n")
                f.write(f"Order Type: {position_info.get('order_type', 'N/A')}\n")
                signal_data = position_info.get('signal_data', {})
                f.write(f"Signals - STM: {signal_data.get('STM', 'N/A')}, TD: {signal_data.get('TD', 'N/A')}, Zigzag: {signal_data.get('Zigzag', 'N/A')}\n")
            else:
                f.write(f"Entry Price: ${position_info['entry_price']:.2f}\n")
                f.write(f"Exit Price: ${position_info['exit_price']:.2f}\n")
                f.write(f"P&L: {position_info['pnl_pct']:.2f}% (${position_info.get('pnl_dollar', 0):.2f})\n")
                f.write(f"Duration: {position_info.get('duration_minutes', 0):.1f} minutes\n")
                f.write(f"Reason: {position_info['reason']}\n")
            
            f.write("="*60 + "\n")


def play_alert_sound():
    """Play an alert sound based on the operating system."""
    try:
        system = platform.system().lower()
        if system == "darwin":  # macOS
            os.system("afplay /System/Library/Sounds/Glass.aiff")
        elif system == "linux":
            os.system("paplay /usr/share/sounds/alsa/Front_Left.wav")
        elif system == "windows":
            import winsound
            winsound.Beep(2000, 1000)  # 1000Hz for 500ms
        else:
            # Fallback: print bell character
            print("\a")
    except Exception as e:
        # Fallback: print bell character
        print("\a")


def check_signal_alignment(stm: str, td: str, zigzag: str) -> tuple:
    """
    Check if all three signals are aligned (all buy or all sell).
    
    Returns:
        tuple: (is_aligned, signal_type, confidence) where signal_type is 'buy', 'sell', or 'none'
    """
    if stm == "buy" and td == "buy" and zigzag == "buy":
        return True, "buy", 1
    elif stm == "sell" and td == "sell" and zigzag == "sell":
        return True, "sell", 1
    elif stm == "buy" and zigzag == "buy":
        return True, "buy", 0.5
    elif stm == "sell" and zigzag == "sell":
        return True, "sell", 0.5
    else:
        return False, "none", 0


def show_alert_message(symbol: str, signal_type: str, stm: str, td: str, zigzag: str, logger: logging.Logger):
    """Show a prominent alert message in the terminal."""
    alert_symbol = "🚨" if signal_type == "sell" else "🚀"
    signal_emoji = "📉" if signal_type == "sell" else "📈"
    
    # Create a prominent border
    border = "=" * 80
    alert_line = f"{alert_symbol} ALERT: ALL SIGNALS ALIGNED - {signal_type.upper()} SIGNAL {alert_symbol}"
    
    print("\n" + border)
    print(alert_line)
    print(f"Symbol: {symbol}")
    print(f"Signal Type: {signal_type.upper()} {signal_emoji}")
    print(f"STM: {stm.upper()}")
    print(f"TD: {td.upper()}")
    print(f"Zigzag: {zigzag.upper()}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(border + "\n")
    
    # Log the alert
    logger.warning(f"ALERT: All signals aligned for {symbol} - {signal_type.upper()} (STM:{stm}, TD:{td}, Zigzag:{zigzag})")


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
    print("Browser is now open. Open all desired tabs and sign in if needed.")
    while True:
        try:
            user_input = input('Enter to continue: ').strip().lower()
        except EOFError:
            time.sleep(1)
            continue
        if user_input == "":
            logger.info("User confirmed start. Beginning scheduled operations.")
            print("Starting scheduled operations...")
            return
        logger.info("Input not recognized. Please type 'ok' when ready.")
        print("Input not recognized. Please type 'ok' when ready.")


def get_tab_metadata(driver) -> list:
    tab_infos = []
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        time.sleep(0.05)
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
            # logger.info(f"Original image size: {img.size} (width x height)")
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return None, None
        
        # CROP 1: Small top left corner (same coordinates as image_cropper.py)
        top_left_x = 160
        top_left_y = 0
        top_left_width = 140
        top_left_height = 60
        
        # CROP 2: Vertical long rectangle in the middle-right area
        vertical_x = 2430
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
        
        # logger.info(f"Using crop coordinates - Top left: ({top_left_x}, {top_left_y}, {top_left_width}, {top_left_height})")
        # logger.info(f"Using crop coordinates - Vertical: ({vertical_x}, {vertical_y}, {vertical_width}, {vertical_height})")
        
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
            # logger.info(f"✓ Top left corner saved: {top_left_path}")
            
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
        
        return top_left_path, vertical_path
            
    except Exception as e:
        logger.error(f"Cropping failed for {image_path}: {e}")
        return None, None


def open_new_tab(driver, url: str, logger: logging.Logger) -> str:
    """Open a new tab with given URL and return its handle."""
    try:
        old_handles = set(driver.window_handles)
        driver.execute_script(f"window.open('{url}', '_blank');")
        
        # Wait for new tab
        for _ in range(50):  # 5 seconds max
            new_handles = set(driver.window_handles) - old_handles
            if new_handles:
                new_handle = list(new_handles)[0]
                driver.switch_to.window(new_handle)
                driver.get(url)
                time.sleep(0.1)  # Wait for page to load
                return new_handle
            time.sleep(0.1)
        return None
    except Exception as e:
        logger.error(f"Error opening new tab for {url}: {e}")
        return None


def close_tab_safely(driver, handle: str, logger: logging.Logger) -> bool:
    """Close a tab safely with error handling."""
    try:
        # Check if tab still exists
        if handle not in driver.window_handles:
            return True  # Already closed
        
        driver.switch_to.window(handle)
        driver.close()
        return True
    except WebDriverException as e:
        if "no such window" in str(e).lower() or "target window already closed" in str(e).lower():
            return True  # Already closed
        else:
            logger.error(f"Error closing tab: {e}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error closing tab: {e}")
        return False


def capture_single_tab(driver, tab_info: dict, index: int, output_dir: str, timestamp_for_filename: str, logger: logging.Logger) -> str:
    """Capture a single tab and return the saved path."""
    try:
        driver.switch_to.window(tab_info["handle"])
        time.sleep(0.03)
        filename = f"{timestamp_for_filename}_tab{index}_{tab_info['host']}.png"
        path = os.path.join(output_dir, filename)
        
        ok = driver.save_screenshot(path)
        if ok:
            # logger.info(f"Saved screenshot: {path}")
            return path
        else:
            logger.error(f"Failed to save screenshot for tab {index}")
            return None
    except WebDriverException as e:
        logger.error(f"Failed to capture tab {index}: {e}")
        return None


def refresh_all_tabs_parallel(driver, logger: logging.Logger, max_workers: int = 4) -> bool:
    """Replace all tabs by opening new ones with same URLs and closing old ones."""
    try:
        # Get current tabs
        old_tabs = get_tab_metadata(driver)
        
        if not old_tabs:
            logger.warning("No tabs found to replace")
            return True
        
        # Open new tabs
        new_handles = []
        for tab in old_tabs:
            new_handle = open_new_tab(driver, tab['url'], logger)
            if new_handle:
                new_handles.append(new_handle)
            else:
                logger.error(f"Failed to open tab for: {tab['url']}")
                return False
        
        # # Verify new tabs are loaded
        # for i, handle in enumerate(new_handles, 1):
        #     driver.switch_to.window(handle)
        #     time.sleep(0.05)
        #     if driver.current_url and driver.current_url != "about:blank":
        #         # logger.info(f"✓ New tab {i} loaded")
        #         pass
        #     else:
        #         logger.error(f"✗ New tab {i} not loaded")
        #         return False
        
        # Close old tabs SEQUENTIALLY (this is the key fix)
        for i, tab in enumerate(old_tabs, 1):
            success = close_tab_safely(driver, tab['handle'], logger)
            if success:
                # logger.info(f"✓ Closed old tab {i}")
                pass
            else:
                logger.error(f"✗ Failed to close old tab {i}")
            time.sleep(0.02)  # Small delay between closes
        
        # Verify result
        final_tabs = get_tab_metadata(driver)
        # logger.info(f"Final tabs: {len(final_tabs)}")
        
        return len(final_tabs) == len(old_tabs)
                    
    except Exception as e:
        logger.exception(f"Unexpected error during tab replacement: {e}")
        return False


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

    # logger.info(f"Capturing screenshots for {len(tabs)} tab(s) sequentially → {output_dir}")
    
    saved_paths = []
    for index, tab in enumerate(tabs, start=1):
        try:
            result = capture_single_tab(driver, tab, index, output_dir, timestamp_for_filename, logger)
            if result:
                saved_paths.append(result)
        except Exception as e:
            logger.error(f"Capture failed for tab {index}: {e}")
    
    return saved_paths


def process_single_image(image_path: str, output_dir: str, logger: logging.Logger, trading_manager: IBTradingManager = None) -> tuple:
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
            
            # NEW: Handle IB Trading Integration
            if trading_manager and symbol in trading_manager.all_symbols:
                stm = results.get("STM", "none")
                td = results.get("TD", "none") 
                zigzag = results.get("Zigzag", "none")
                
                # Check for signal alignment
                is_aligned, signal_type, confidence = check_signal_alignment(stm, td, zigzag)
                
                # is_aligned = True # fk
                if is_aligned:
                    # Get current market price
                    current_price = trading_manager.get_current_price(symbol)
                    print(f"Current price: {current_price}")
                    if current_price:
                        # Check if we have an opposite position to close first
                        trading_manager.handle_opposite_signal(symbol, signal_type)
                        
                        # Place new order if we don't already have a position in this direction
                        current_position = trading_manager.current_positions.get(symbol)
                        if (current_position is None or 
                            current_position['signal_type'] != signal_type):
                            
                            # Prepare signal data for CSV logging
                            signal_data = {
                                'STM': stm,
                                'TD': td,
                                'Zigzag': zigzag
                            }
                            
                            success = trading_manager.place_order(symbol, signal_type, current_price, signal_data, confidence)
                            if success:
                                logger.info(f"🚀 TRADE EXECUTED: {signal_type.upper()} {symbol} at ${current_price:.2f}")
                            else:
                                logger.error(f"❌ TRADE FAILED: Could not execute {signal_type.upper()} for {symbol}")
        
        return (image_path, results)
        
    except Exception as e:
        logger.error(f"Processing failed for {image_path}: {e}")
        return (image_path, {"error": str(e)})


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


def precise_sleep_until(target_time: datetime) -> None:
    """Sleep until target_time with sub-100ms precision, minimizing drift."""
    while True:
        now = datetime.now()
        remaining = (target_time - now).total_seconds()
        if remaining <= 0:
            break
        # Coarse sleep when far, fine-grained as we approach
        if remaining > 1.0:
            time.sleep(remaining - 0.8)
        elif remaining > 0.2:
            time.sleep(remaining - 0.15)
        elif remaining > 0.05:
            time.sleep(remaining - 0.02)
        else:
            time.sleep(remaining)
            break


def capture_and_analyze_streamed(driver, logger: logging.Logger, output_base: str, capture_time: datetime, trading_manager: IBTradingManager = None, max_workers: int = 4) -> None:
    """Capture tabs sequentially but analyze each image as soon as it's saved (overlapped)."""
    tabs = get_tab_metadata(driver)
    output_dir = ensure_capture_dir(output_base, capture_time)
    timestamp_for_filename = capture_time.strftime("%Y%m%d_%H%M%S")

    if not tabs:
        logger.info("No tabs to capture.")
        return

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for index, tab in enumerate(tabs, start=1):
            try:
                path = capture_single_tab(driver, tab, index, output_dir, timestamp_for_filename, logger)
                if path:
                    futures.append(executor.submit(process_single_image, path, output_dir, logger, trading_manager))
            except Exception as e:
                logger.error(f"Capture failed for tab {index}: {e}")

        for future in as_completed(futures):
            try:
                img_path, result = future.result()
                if "error" in result:
                    logger.error(f"Processing failed for {img_path}: {result['error']}")
                    print(f"JSON Output: {{\"Symbol\":\"ERROR\",\"STM\":\"error\",\"TD\":\"error\",\"Zigzag\":\"error\"}}")
                else:
                    symbol = result.get("symbol", "UNKNOWN")
                    stm = result.get("STM", "none")
                    td = result.get("TD", "none")
                    zigzag = result.get("Zigzag", "none")
                    logger.info(f"🔥Analysis: Symbol={symbol}, STM={stm}, TD={td}, Zigzag={zigzag}")
                    is_aligned, signal_type, confidence = check_signal_alignment(stm, td, zigzag)
                    if is_aligned:
                        play_alert_sound()
                        show_alert_message(symbol, signal_type, stm, td, zigzag, logger)
                    print(f"🔥JSON Output: {{\"Symbol\":\"{symbol}\",\"STM\":\"{stm}\",\"TD\":\"{td}\",\"Zigzag\":\"{zigzag}\"}}")
            except Exception as e:
                logger.exception(f"Exception in streamed processing: {e}")
                print(f"JSON Output: {{\"Symbol\":\"ERROR\",\"STM\":\"error\",\"TD\":\"error\",\"Zigzag\":\"error\"}}")

def create_external_ib_connection(host: str = '127.0.0.1', port: int = 4002, client_id: int = None, logger: logging.Logger = None) -> IBApiApp:
    """
    Create an external IB connection that can be reused.
    
    Args:
        host: IB Gateway/TWS host
        port: IB Gateway/TWS port
        client_id: Client ID for the connection
        logger: Logger instance
    
    Returns:
        IBApiApp: Connected IB API instance
    """
    if not IB_AVAILABLE:
        raise RuntimeError("IB API not available")
    
    if client_id is None:
        # Generate a unique client ID
        today = datetime.now(pytz.timezone('US/Eastern'))
        weekday = today.weekday()
        random_number = random.randint(1, 60)
        client_id = random_number + weekday
    
    ib = IBApiApp(logger or logging.getLogger(__name__))
    ib.connect_and_start(host, port, client_id)
    return ib


def main():
    logger = configure_logging("main.log")

    if open_browser is None or auto_login is None:
        logger.error("Failed to import browser helpers from scrape.py. Exiting.")
        print("ERROR: scrape.py helpers not available. Cannot continue.")
        return

    # Create external IB connection (you can modify these parameters)
    external_ib_connection = None
    if IB_AVAILABLE:
        try:
            # Create your stable connection here with your specific client_id
            external_ib_connection = create_external_ib_connection(
                host='127.0.0.1',
                port=4002,
                client_id=1,  # Use your stable client_id here
                logger=logger
            )
            logger.info("✅ External IB connection created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create external IB connection: {e}")
            external_ib_connection = None

    # Initialize IB Trading Manager with external connection
    trading_manager = None
    if external_ib_connection:
        try:
            trading_manager = IBTradingManager(
                symbols=stock_list,
                special_symbols=special_symbols,
                ib_connection=external_ib_connection,  # Pass external connection
                logger=logger,
                init_capital=4000  # $4,000 initial capital
            )
            
            # Connect to IB (will use external connection)
            if trading_manager.connect():
                logger.info("✅ IB Trading Manager connected successfully using external connection")
            else:
                logger.error("❌ Failed to connect IB Trading Manager")
                trading_manager = None
        except Exception as e:
            logger.error(f"Error initializing IB Trading Manager: {e}")
            trading_manager = None
    else:
        logger.warning("No external IB connection available. Running in analysis-only mode.")

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
        if "symbol=" in first_tab_url:
            base, _ = first_tab_url.split("symbol=", 1)  # split once, discard the old stock part
            for stock in stock_list:
                new_url = f"{base}symbol={stock}"
                # Open new tab with the URL
                driver.execute_script(f"window.open('{new_url}', '_blank');")
        else:
            pass

        base_output_dir = "screen_caps"
        logger.info("Entering scheduled loop: refresh at -30s, capture at 5-minute marks.")
        print("Scheduled operations started. Monitoring every 5 minutes...")

        while True:
            now = datetime.now()
            us_time_now = datetime.now(pytz.timezone('US/Eastern'))
            capture_time = ceil_to_next_5min_mark(now)
            refresh_time = capture_time - timedelta(seconds=50)
            
            # Check for daily position closure at 07:59 US/Eastern
            if trading_manager and us_time_now.hour == 15 and us_time_now.minute == 55:
                time.sleep(240)
                trading_manager.close_all_positions_daily()
                print("Daily position closure: Closing all positions")
                time.sleep(130)  # Sleep for 2 minutes to avoid multiple closures
                continue

            a = True
            # Check exit conditions for existing positions
            # Need to check the exit conditions every seconds *************
            if trading_manager:
                try:
                    if a:
                        print("Checking exit conditions*****")
                        trading_manager.check_exit_conditions()
                        a = False
                except Exception as e:
                    logger.error(f"Error checking exit conditions: {e}")

            #########################################################

            # Refresh exactly at refresh_time, then wait precisely to capture_time
            if now < refresh_time:
                precise_sleep_until(refresh_time)
                replacement_success = refresh_all_tabs_parallel(driver, logger, max_workers=min(8, max(2, os.cpu_count() or 4)))
                if not replacement_success:
                    logger.warning("Tab replacement had issues, but continuing with capture...")
                precise_sleep_until(capture_time)
            elif now >= refresh_time and now < capture_time:
                replacement_success = refresh_all_tabs_parallel(driver, logger, max_workers=min(8, max(2, os.cpu_count() or 4)))
                if not replacement_success:
                    logger.warning("Tab replacement had issues, but continuing with capture...")
                precise_sleep_until(capture_time)
            # else: now >= capture_time → fall through to capture immediately

            #########################################################

            # At capture time (5-minute mark), just capture without refreshing
            now = datetime.now()
            # if True: # fk
            if now >= capture_time:
                us_time_now = datetime.now(pytz.timezone('US/Eastern'))
                # if False: # fk
                if not (((us_time_now.hour > 9 and us_time_now.hour < 16) or (us_time_now.hour == 9 and us_time_now.minute >= 30)) or (us_time_now.hour == 16 and us_time_now.minute < 1)):
                    # print("Not in market hours. Skipping capture...")
                    # time.sleep(30)
                    continue
                else:
                    logger.info("Time to capture screenshots (5-minute mark)")
                    # Streamed capture+analysis for minimal gap between first and last symbol
                    try:
                        capture_and_analyze_streamed(
                            driver,
                            logger,
                            base_output_dir,
                            capture_time,
                            trading_manager,
                            max_workers=min(8, max(2, os.cpu_count() or 4))
                        )
                    except Exception as e:
                        logger.exception(f"Error running streamed capture+analysis: {e}")

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Shutting down.")
        print("\nShutting down...")
    except Exception as e:
        logger.exception(f"Fatal error in main loop: {e}")
        print(f"ERROR: {e}")
    finally:
        # Close IB connection
        if trading_manager:
            logger.info("Closing all positions before shutdown...")
            # for symbol in trading_manager.all_symbols:
            #     if trading_manager.current_positions[symbol] is not None:
            #         trading_manager.close_position(symbol, "SYSTEM SHUTDOWN")
            trading_manager.disconnect()
        
        # Disconnect external connection if it exists
        if external_ib_connection:
            try:
                external_ib_connection.disconnect()
                logger.info("External IB connection closed")
            except Exception as e:
                logger.error(f"Error closing external IB connection: {e}")
        
        try:
            driver.quit()
        except Exception:
            pass
        logger.info("Browser closed. Done.")
        print("Done.")


if __name__ == "__main__":
    main()
