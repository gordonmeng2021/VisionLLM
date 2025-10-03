#!/usr/bin/env python3
"""
test4.py - Test script to place a limit order for AAPL at $257 and track the filled price
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime
import pytz

# Add the current directory to Python path to import from main_with_ib_trading
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.order import Order
    IB_AVAILABLE = True
except ImportError:
    IB_AVAILABLE = False
    print("Warning: ibapi not available. Trading functionality disabled.")

class OrderTrackingApp(EWrapper, EClient):
    """Enhanced IB API app with order execution tracking"""
    
    def __init__(self, logger: logging.Logger):
        EClient.__init__(self, self)
        self.logger = logger or logging.getLogger(__name__)
        self._thread = None
        self._connected_event = threading.Event()
        self._next_id_event = threading.Event()
        self.next_order_id = None
        self._req_id = 1000
        self._lock = threading.Lock()
        
        # Order tracking
        self.order_status = {}  # {order_id: order_status_info}
        self.executions = {}    # {order_id: [execution_details]}
        self.filled_orders = {} # {order_id: filled_price_info}
        
    def connect_and_start(self, host: str, port: int, client_id: int, wait_timeout: float = 5.0):
        """Connect to IB and start the message loop"""
        self.connect(host, port, client_id)
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        # Wait for nextValidId which signals readiness
        if not self._next_id_event.wait(timeout=wait_timeout):
            raise RuntimeError("Timed out waiting for nextValidId from TWS/Gateway")
    
    def disconnect(self):
        """Disconnect from IB"""
        try:
            super().disconnect()
        except Exception:
            pass
    
    # EWrapper callbacks
    def nextValidId(self, orderId: int):
        """Called when we get the next valid order ID"""
        self.next_order_id = orderId
        self._next_id_event.set()
        self.logger.info(f"Next valid order ID: {orderId}")
    
    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        """Handle errors"""
        self.logger.error(f"IB Error reqId={reqId}, code={errorCode}, msg={errorString}")
    
    def orderStatus(self, orderId, status, filled, remaining, avgFillPrice, permId, parentId, lastFillPrice, clientId, whyHeld, mktCapPrice):
        """Called when order status changes"""
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
    
    def execDetails(self, reqId, contract, execution):
        """Called when execution details are received"""
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
    
    def openOrder(self, orderId, contract, order, orderState):
        """Called when order details are received"""
        self.logger.info(f"Open order {orderId}: {order.action} {order.totalQuantity} {contract.symbol} @ {order.lmtPrice}")
    
    def openOrderEnd(self):
        """Called when all open orders have been sent"""
        self.logger.info("Open orders end")
    
    def place_limit_order(self, symbol: str, action: str, quantity: int, limit_price: float) -> int:
        """Place a limit order and return the order ID"""
        # Ensure we have a valid next order id
        start = time.time()
        while self.next_order_id is None and (time.time() - start) < 5.0:
            time.sleep(0.05)
        
        if self.next_order_id is None:
            raise RuntimeError("No next order id available from IB")
        
        with self._lock:
            order_id = self.next_order_id
            self.next_order_id += 1
        
        # Create contract
        contract = Contract()
        contract.symbol = symbol
        contract.secType = 'STK'
        contract.exchange = 'SMART'
        contract.currency = 'USD'
        
        # Create order
        order = Order()
        order.action = action
        order.orderType = 'LMT'
        order.lmtPrice = limit_price
        order.totalQuantity = quantity
        order.tif = 'DAY'
        order.outsideRth = True  # Allow trading outside regular hours
        order.eTradeOnly = ""
        order.firmQuoteOnly = ""
        
        try:
            self.placeOrder(order_id, contract, order)
            self.logger.info(f"Placed {action} order for {quantity} shares of {symbol} at ${limit_price:.2f} (Order ID: {order_id})")
            return order_id
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            raise
    
    def wait_for_fill(self, order_id: int, timeout: float = 30.0) -> dict:
        """Wait for order to be filled and return fill details"""
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
            
            time.sleep(0.1)
        
        self.logger.warning(f"Timeout waiting for order {order_id} to fill")
        return None
    
    def get_order_status(self, order_id: int) -> dict:
        """Get current status of an order"""
        return self.order_status.get(order_id, {})
    
    def get_executions(self, order_id: int) -> list:
        """Get execution details for an order"""
        return self.executions.get(order_id, [])

def configure_logging() -> logging.Logger:
    """Configure logging"""
    logger = logging.getLogger("test4_order_tracking")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger

def main():
    """Main function to test limit order placement and tracking"""
    logger = configure_logging()
    
    if not IB_AVAILABLE:
        logger.error("IB API not available. Cannot run test.")
        return
    
    # Configuration
    symbol = "AAPL"
    action = "BUY"
    quantity = 1  # 1 share for testing
    limit_price = 257.0
    
    logger.info("="*60)
    logger.info("TEST4: AAPL Limit Order Test")
    logger.info("="*60)
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Action: {action}")
    logger.info(f"Quantity: {quantity}")
    logger.info(f"Limit Price: ${limit_price:.2f}")
    logger.info("="*60)
    
    # Create and connect to IB
    app = OrderTrackingApp(logger)
    
    try:
        # Connect to IB Gateway/TWS
        logger.info("Connecting to IB Gateway...")
        app.connect_and_start('127.0.0.1', 4002, 1)
        logger.info("✅ Connected to IB Gateway")
        
        # Place the limit order
        logger.info(f"Placing {action} limit order for {quantity} share(s) of {symbol} at ${limit_price:.2f}...")
        order_id = app.place_limit_order(symbol, action, quantity, limit_price)
        
        # Wait for fill
        logger.info("Waiting for order to fill (timeout: 30 seconds)...")
        fill_details = app.wait_for_fill(order_id, timeout=30.0)
        
        if fill_details:
            logger.info("🎉 ORDER SUCCESSFULLY FILLED!")
            logger.info("="*40)
            logger.info("FILL DETAILS:")
            logger.info(f"Order ID: {order_id}")
            logger.info(f"Filled Quantity: {fill_details['filled_quantity']}")
            logger.info(f"Average Fill Price: ${fill_details['avg_fill_price']:.2f}")
            logger.info(f"Last Fill Price: ${fill_details['last_fill_price']:.2f}")
            logger.info(f"Fill Time: {fill_details['fill_time']}")
            logger.info(f"Status: {fill_details['status']}")
            logger.info("="*40)
            
            # Print the filled price as requested
            print(f"\n✅ FILLED PRICE: ${fill_details['avg_fill_price']:.2f}")
            
        else:
            logger.warning("❌ Order was not filled within timeout period")
            
            # Check final order status
            status = app.get_order_status(order_id)
            if status:
                logger.info(f"Final order status: {status['status']}")
                logger.info(f"Filled: {status['filled']}, Remaining: {status['remaining']}")
                if status['avgFillPrice'] > 0:
                    logger.info(f"Average Fill Price: ${status['avgFillPrice']:.2f}")
                    print(f"\n⚠️  PARTIAL FILL PRICE: ${status['avgFillPrice']:.2f}")
            else:
                logger.error("No order status information available")
        
        # Get execution details if available
        executions = app.get_executions(order_id)
        if executions:
            logger.info(f"Execution details: {len(executions)} execution(s)")
            for i, exec_detail in enumerate(executions, 1):
                logger.info(f"  Execution {i}: {exec_detail['shares']} shares at ${exec_detail['price']:.2f}")
    
    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Disconnect
        try:
            app.disconnect()
            logger.info("Disconnected from IB Gateway")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    logger.info("Test completed.")

if __name__ == "__main__":
    main()
