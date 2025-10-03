from ib_insync import *
import sys
import datetime
import pytz

def is_regular_market_hours():
    # Get current time in US/Eastern
    eastern = pytz.timezone('US/Eastern')
    now = datetime.datetime.now(eastern)
    
    # Regular market hours are 9:30 AM to 4:00 PM Eastern
    market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_start <= now <= market_end

def adjust_price_for_extended_hours(price, action):
    # For pre/post market:
    # If selling: set price 1% lower to ensure execution
    # If buying: set price 1% higher to ensure execution
    adjustment = 0.01  # 1% adjustment
    
    if action == 'SELL':
        return price * (1 - adjustment)
    else:  # BUY
        return price * (1 + adjustment)

def place_quick_order(symbol, quantity, action):
    if action not in ['BUY', 'SELL']:
        print("Error: Action must be either 'BUY' or 'SELL'")
        return
        
    # Create IB connection
    ib = IB()
    
    try:
        # Connect to IB TWS or IB Gateway
        ib.connect('127.0.0.1', 4002, clientId=120)
        
        # Create stock contract
        contract = Stock(symbol, 'SMART', 'USD')
        
        is_regular_hours = is_regular_market_hours()
        
        # Get current market price
        ticker = ib.reqMktData(contract)
        ib.sleep(1)  # Wait for market data to arrive
        
        if is_regular_hours:
            # During regular hours, use market order
            order = MarketOrder(action, quantity)
            print(f'Using market order during regular trading hours')
        else:
            # During extended hours, use limit order with adjusted price
            current_price = ticker.last if ticker.last > 0 else ticker.close
            if current_price <= 0:
                print("Error: Unable to get current market price")
                return
                
            adjusted_price = adjust_price_for_extended_hours(current_price, action)
            order = LimitOrder(action=action, totalQuantity=quantity, lmtPrice=adjusted_price, transmit=True, outsideRth=True)
            print(f'Using limit order during extended hours at price: {adjusted_price}')
        
        # Place the order
        trade = ib.placeOrder(contract, order)
        
        print(f'Order placed for {symbol}:')
        print(f'Action: {action}, Quantity: {quantity}')
        
        # Wait for order to fill
        while not trade.isDone():
            ib.sleep(1)  # Wait for 1 second
            
        print(f'Order Status: {trade.orderStatus.status}')
        print(f'Filled at: {trade.orderStatus.avgFillPrice}')
            
    except Exception as e:
        print(f'Error: {str(e)}')
        
    finally:
        # Disconnect from IB
        ib.disconnect()

if __name__ == '__main__':
    # symbol = "NVDA"
    symbol = "IBM"
    quantity = 1
    action = "SELL"
    # action = "SELL"

    place_quick_order(symbol, quantity, action) 