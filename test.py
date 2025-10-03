from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

import threading
import time


class IBapi(EWrapper, EClient):
	def __init__(self):
		EClient.__init__(self, self)
		self.reqId_to_symbol = {}
	def tickPrice(self, reqId, tickType, price, attrib):
		if tickType == 4:
			symbol = self.reqId_to_symbol.get(reqId, str(reqId))
			print(f"{symbol} last price: {price}")

def run_loop():
	app.run()

app = IBapi()
app.connect('127.0.0.1', 4002, 123)

#Start the socket in a thread
api_thread = threading.Thread(target=run_loop, daemon=True)
api_thread.start()

time.sleep(0.1) #Sleep interval to allow time for connection to server

# Request market data for multiple symbols concurrently
def request_market_data(req_id, symbol):
	contract = Contract()
	contract.symbol = symbol
	contract.secType = 'STK'
	contract.exchange = 'SMART'
	contract.currency = 'USD'
	app.reqId_to_symbol[req_id] = symbol
	app.reqMktData(req_id, contract, '', False, False, [])

symbols = ['AVGO']
threads = []
for idx, sym in enumerate(symbols, start=1):
	t = threading.Thread(target=request_market_data, args=(idx, sym), daemon=True)
	threads.append(t)
	t.start()

time.sleep(10) #Sleep interval to allow time for incoming price data
app.disconnect()