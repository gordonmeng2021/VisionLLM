
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.common import TickerId


# ===== Configuration (no argparse; adjust variables here) =====
HOST = "127.0.0.1"
PORT = 4002  # TWS paper is typically 7497; IB Gateway often 4002
CLIENT_ID = 123

# Choose between "CMDTY" (commodity) and "CASH" (fx-like) for XAUUSD
# XAUUSD_MODE = "CMDTY"  # or "CASH"
XAUUSD_MODE = "CASH"  # or "CASH"

# Market data type: 1=Live, 2=Frozen, 3=Delayed, 4=Delayed-Frozen
MARKET_DATA_TYPE = 1


@dataclass
class Quote:
    bid: Optional[float] = None
    bid_size: Optional[float] = None
    ask: Optional[float] = None
    ask_size: Optional[float] = None
    last: Optional[float] = None
    last_size: Optional[float] = None
    last_time: Optional[int] = None


class IBStreamer(EWrapper, EClient):
    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)
        self._quotes: Dict[int, Quote] = {}
        self._quotes_lock = threading.Lock()
        self._stop_event = threading.Event()

    # ----- Connection lifecycle -----
    def connect_and_start(self, host: str, port: int, client_id: int) -> None:
        self.connect(host, port, client_id)
        thread = threading.Thread(target=self.run, name="IBAPI-Thread", daemon=True)
        thread.start()
        # Wait for connection to establish
        time.sleep(0.001)

    def stop(self) -> None:
        try:
            self._stop_event.set()
            if self.isConnected():
                self.disconnect()
        except Exception:
            pass

    # ----- Printing helper -----
    def _print_quote(self, ticker_id: int) -> None:
        with self._quotes_lock:
            q = self._quotes.get(ticker_id)
            if not q:
                return
            parts = []
            if q.bid is not None:
                parts.append(f"bid={q.bid} ({q.bid_size or 0})")
            if q.ask is not None:
                parts.append(f"ask={q.ask} ({q.ask_size or 0})")
            if q.last is not None:
                parts.append(f"last={q.last} ({q.last_size or 0})")
            if not parts:
                return
            print("XAUUSD | " + "  ".join(parts))

    # ----- Market data handlers -----
    def tickPrice(self, reqId: TickerId, tickType: int, price: float, attrib):
        # TickType constants: 1=BID, 2=ASK, 4=LAST
        with self._quotes_lock:
            q = self._quotes.setdefault(reqId, Quote())
            if tickType == 1:
                q.bid = price if price > 0 else q.bid
            elif tickType == 2:
                q.ask = price if price > 0 else q.ask
            elif tickType == 4:
                q.last = price if price > 0 else q.last
        self._print_quote(reqId)

    def tickSize(self, reqId: TickerId, tickType: int, size: int):
        # Size types: 0=Unknown, 3=BID_SIZE, 5=ASK_SIZE, 5? (LAST size arrives via 5/8/9 depending context)
        with self._quotes_lock:
            q = self._quotes.setdefault(reqId, Quote())
            if tickType == 3:
                q.bid_size = size
            elif tickType == 5:
                q.ask_size = size
            elif tickType in (8, 9):  # LAST_SIZE often 8; 9 is VOLUME
                q.last_size = size
        self._print_quote(reqId)

    # Optional: tick-by-tick last for more reliable last trade updates
    def tickByTickAllLast(self, reqId: int, tickType: int, time_: int, price: float, size: int, tickAttribLast, exchange: str, specialConditions: str):
        with self._quotes_lock:
            q = self._quotes.setdefault(reqId, Quote())
            q.last = price
            q.last_size = size
            q.last_time = time_
        self._print_quote(reqId)

    # Error handling
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        # Common errors: 354 (market data subscription), 200 (no security definition), 10167 (No market data permissions)
        if reqId >= 0:
            print(f"[ERROR] reqId={reqId} code={errorCode} msg={errorString}")
        else:
            print(f"[ERROR] code={errorCode} msg={errorString}")


def build_xauusd_contract(mode: str) -> Contract:
    mode_upper = (mode or "").upper()
    c = Contract()
    # FX-like representation; may require IDEALPRO
    c.symbol = "AVGO"
    c.secType = "STK"
    c.currency = "USD"
    c.exchange = "SMART"
    return c


def main() -> None:
    app = IBStreamer()
    try:
        app.connect_and_start(HOST, PORT, CLIENT_ID)

        # Select live/delayed market data mode
        app.reqMarketDataType(MARKET_DATA_TYPE)

        contract = build_xauusd_contract(XAUUSD_MODE)

        # Request top-of-book market data
        ticker_id = 1001
        app.reqMktData(ticker_id, contract, "", False, False, [])

        # Also request tick-by-tick last trade (if permissions allow)
        try:
            app.reqTickByTickData(ticker_id, contract, "Last", 1, False)
        except Exception:
            pass

        print("Streaming XAUUSD quotes. Press Ctrl+C to stop.")
        while app.isConnected():
            time.sleep(0.00001)
            if app._stop_event.is_set():
                break

    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        try:
            app.cancelMktData(1001)
        except Exception:
            pass
        try:
            app.cancelTickByTickData(1001)
        except Exception:
            pass
        app.stop()


if __name__ == "__main__":
    main()

