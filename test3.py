import signal
from typing import List

from ib_insync import IB, Stock


# ===== Configuration (adjust as needed) =====
HOST: str = "127.0.0.1"
PORT: int = 4002  # TWS paper: 7497, IB Gateway paper: 4002
CLIENT_ID: int = 125

# Market data type: 1=Live, 2=Frozen, 3=Delayed, 4=Delayed-Frozen
MARKET_DATA_TYPE: int = 1


def format_available_fields(fields: List[str]) -> str:
    parts = [field for field in fields if field]
    return "  ".join(parts)


def main() -> None:
    ib = IB()

    # Graceful Ctrl+C handling for clean disconnect
    interrupted = {"stop": False}

    def handle_sigint(signum, frame):  # type: ignore[unused-argument]
        interrupted["stop"] = True

    signal.signal(signal.SIGINT, handle_sigint)

    # Connect and configure market data mode
    ib.connect(HOST, PORT, clientId=CLIENT_ID)
    ib.reqMarketDataType(MARKET_DATA_TYPE)

    # Define AVGO contract via SMART routing
    contract = Stock(symbol="AVGO", exchange="SMART", currency="USD")
    ib.qualifyContracts(contract)

    # Request top-of-book market data
    ticker = ib.reqMktData(contract, genericTickList="", snapshot=False, regulatorySnapshot=False)

    def on_pending_tickers(_):
        # Build a concise, present-only fields line
        fields: List[str] = []
        if ticker.bid is not None:
            fields.append(f"bid={ticker.bid} ({ticker.bidSize or 0})")
        if ticker.ask is not None:
            fields.append(f"ask={ticker.ask} ({ticker.askSize or 0})")
        if ticker.last is not None:
            last_sz = ticker.lastSize or 0
            fields.append(f"last={ticker.last} ({last_sz})")
        if not fields:
            return
        print("AVGO | " + format_available_fields(fields))

    ib.pendingTickersEvent += on_pending_tickers

    print("Streaming AVGO quotes. Press Ctrl+C to stop.")
    try:
        while not interrupted["stop"]:
            ib.waitOnUpdate(timeout=1.0)
    finally:
        try:
            ib.cancelMktData(contract)
        except Exception:
            pass
        ib.disconnect()


if __name__ == "__main__":
    main()


