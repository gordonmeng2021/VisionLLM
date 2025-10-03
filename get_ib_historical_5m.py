from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.common import BarData
import threading
import time
import datetime

class IBApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.data = []  # to store bars
        self.done = False

    def historicalData(self, reqId: int, bar: BarData):
        print(f"HistoricalData. ReqId: {reqId}, Date: {bar.date}, Open: {bar.open}, High: {bar.high}, "
              f"Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}")
        self.data.append(bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        print(f"HistoricalDataEnd. ReqId: {reqId}, from {start} to {end}")
        self.done = True

def run_loop(app):
    app.run()

def get_sl_tp(symbol: str, signal_type: str):
    """Fetch 5-minute historical bars for the past 1 day for a given stock symbol,
    compute last-20-bar recent low/high on closes, then compute SL/TP based on signal_type.

    Returns a tuple: (SL, TP)
    """
    app = IBApp()
    # connect to TWS / Gateway
    app.connect("127.0.0.1", 4002, clientId=110)

    # Start the socket in a thread
    api_thread = threading.Thread(target=run_loop, args=(app,), daemon=True)
    api_thread.start()

    time.sleep(0.01)
    # Define the contract
    contract = Contract()
    contract.symbol = symbol
    contract.secType = "STK"
    contract.currency = "USD"
    contract.exchange = "SMART"  # or "NASDAQ" etc., but SMART is usual

    end_time = datetime.datetime.now().strftime("%Y%m%d %H:%M:%S")
    # Request historical data
    # useRTH = 0 => include extended hours (non-regular trading hours)
    # durationStr: how far back you want (e.g. "1 D", "5 D", etc.)
    # barSizeSetting: e.g. "5 mins", "1 hour", etc.
    # whatToShow: e.g. "TRADES"
    # formatDate: 1 or 2 (affects date format)
    app.reqHistoricalData(
        reqId=1,
        contract=contract,
        endDateTime=end_time,
        durationStr="1 D",
        barSizeSetting="5 mins",
        whatToShow="TRADES",
        useRTH=0,        # <-- **include extended hours**
        formatDate=1,
        keepUpToDate=False,
        chartOptions=[]
    )

    # Wait until data is received via historicalData + historicalDataEnd
    while not app.done:
        time.sleep(0.01)

    # Now app.data has the bars
    num_bars = len(app.data)
    print(f"Received {num_bars} bars for {symbol}")

    if num_bars == 0:
        app.disconnect()
        raise RuntimeError("No historical bars received")

    # Take last 20 bars (or fewer if not enough)
    last_bars = app.data[-20:] if num_bars >= 20 else app.data[:]
    highs = [float(b.high) for b in last_bars]
    lows = [float(b.low) for b in last_bars]
    recent_low = min(lows)
    recent_high = max(highs)
    # Dummy current price provider
    def get_current_price(sym: str) -> float:
        # For now, use the last bar close as a proxy for current price
        return float(app.data[-1].close)

    current_price = get_current_price(symbol)

    # Default confidences (can be wired to your model later)
    confidence_bull = 0.5
    confidence_bear = 0.5

    if signal_type.lower() == "buy":
        risk_long = current_price - recent_low
        if risk_long == 0:
            risk_long = recent_high - recent_low
        fib_sl_long = 0.382 + (1 - confidence_bull) * (0.618 - 0.382)
        fib_tp_long = 1.382 + confidence_bull * (1.618 - 1.382)
        sl = current_price - risk_long * fib_sl_long
        tp = current_price + risk_long * fib_tp_long
    elif signal_type.lower() == "sell":
        risk_short = recent_high - current_price
        if risk_short == 0:
            risk_short = recent_high - recent_low
        fib_sl_short = 0.382 + (1 - confidence_bear) * (0.618 - 0.382)
        fib_tp_short = 1.382 + confidence_bear * (1.618 - 1.382)
        sl = current_price + risk_short * fib_sl_short
        tp = current_price - risk_short * fib_tp_short
    else:
        app.disconnect()
        raise ValueError("signal_type must be 'buy' or 'sell'")
    app.disconnect()
    return tp, sl

def main():
    # Example usage
    # _sl, _tp = fetch_historical_5m("AAPL", "buy")
    # print("BUY -> SL:", _sl, "TP:", _tp)
    _sl, _tp = get_sl_tp("TSLA", "sell")
    print("SELL -> SL:", _sl, "TP:", _tp)

if __name__ == "__main__":
    main()
