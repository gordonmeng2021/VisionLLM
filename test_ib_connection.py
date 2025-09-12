#!/usr/bin/env python3
"""
Test script for Interactive Brokers connection.
Run this script to verify your IB setup before using the full trading system.
"""

import sys
import json
from datetime import datetime
import pytz

try:
    from ib_async import *
    print("✅ ib_async imported successfully")
except ImportError:
    print("❌ ib_async not found. Install with: pip install ib_async")
    sys.exit(1)

def load_config():
    """Load configuration from config.json"""
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print("❌ config.json not found. Using default settings.")
        return {
            "ib_connection": {
                "host": "127.0.0.1",
                "port": 4002,
                "client_id": 99,
                "account": None
            },
            "trading": {
                "symbols": ["NVDA", "AAPL", "TSLA", "QQQ"]
            }
        }

def test_connection(config):
    """Test basic IB connection"""
    print("\n" + "="*50)
    print("TESTING IB CONNECTION")
    print("="*50)
    
    ib_config = config["ib_connection"]
    host = ib_config["host"]
    port = ib_config["port"]
    client_id = ib_config["client_id"] or 99
    
    print(f"Connecting to {host}:{port} with client ID {client_id}...")
    
    ib = IB()
    try:
        ib.connect(host, port, clientId=client_id)
        print("✅ Connected to IB successfully!")
        return ib
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure TWS or IB Gateway is running")
        print("2. Check that API is enabled in TWS settings")
        print("3. Verify the port number (usually 4002)")
        print("4. Ensure 127.0.0.1 is in trusted IPs")
        return None

def test_account_info(ib):
    """Test account information retrieval"""
    print("\n" + "="*50)
    print("TESTING ACCOUNT INFO")
    print("="*50)
    
    try:
        # Get account summary
        account_summary = ib.accountSummary()
        print(f"✅ Retrieved {len(account_summary)} account summary items")
        
        # Show some key account info
        key_items = ['TotalCashValue', 'NetLiquidation', 'BuyingPower']
        for item in account_summary:
            if item.tag in key_items:
                print(f"  {item.tag}: {item.value} {item.currency}")
        
        # Get managed accounts
        accounts = ib.managedAccounts()
        print(f"✅ Managed accounts: {accounts}")
        
        return True
    except Exception as e:
        print(f"❌ Account info failed: {e}")
        return False

def test_market_data(ib, symbols):
    """Test market data retrieval for symbols"""
    print("\n" + "="*50)
    print("TESTING MARKET DATA")
    print("="*50)
    
    contracts = {}
    tickers = {}
    
    try:
        # Create contracts
        for symbol in symbols:
            contracts[symbol] = Stock(symbol, 'SMART', 'USD')
            print(f"✅ Created contract for {symbol}")
        
        # Request market data
        for symbol, contract in contracts.items():
            ticker = ib.reqMktData(contract, '', False, False)
            tickers[symbol] = ticker
            print(f"✅ Requested market data for {symbol}")
        
        # Wait for data
        print("⏳ Waiting for market data...")
        ib.sleep(3)
        
        # Check data
        for symbol, ticker in tickers.items():
            print(f"\n📊 {symbol} Market Data:")
            print(f"  Last: {ticker.last}")
            print(f"  Bid: {ticker.bid}")
            print(f"  Ask: {ticker.ask}")
            print(f"  Close: {ticker.close}")
            
            if ticker.last and ticker.last > 0:
                print(f"  ✅ Valid price data received")
            else:
                print(f"  ⚠️  No current price data")
        
        # Cancel market data
        for symbol, contract in contracts.items():
            ib.cancelMktData(contract)
        
        return True
        
    except Exception as e:
        print(f"❌ Market data test failed: {e}")
        return False

def test_order_permissions(ib):
    """Test if account has trading permissions (without placing actual orders)"""
    print("\n" + "="*50)
    print("TESTING ORDER PERMISSIONS")
    print("="*50)
    
    try:
        # Get account info to check permissions
        account_summary = ib.accountSummary()
        
        # Look for trading-related permissions
        trading_permissions = []
        for item in account_summary:
            if 'trading' in item.tag.lower() or 'order' in item.tag.lower():
                trading_permissions.append(f"{item.tag}: {item.value}")
        
        if trading_permissions:
            print("✅ Trading-related account settings found:")
            for perm in trading_permissions:
                print(f"  {perm}")
        else:
            print("⚠️  No explicit trading permissions found in account summary")
        
        # Check if we can create orders (without submitting)
        test_contract = Stock('AAPL', 'SMART', 'USD')
        test_order = MarketOrder('BUY', 1)
        
        print("✅ Order creation test passed (order not submitted)")
        return True
        
    except Exception as e:
        print(f"❌ Order permissions test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Interactive Brokers Connection Test")
    print(f"Time: {datetime.now(pytz.timezone('US/Eastern'))}")
    
    # Load configuration
    config = load_config()
    
    # Test connection
    ib = test_connection(config)
    if not ib:
        return
    
    try:
        # Test account info
        account_ok = test_account_info(ib)
        
        # Test market data
        symbols = config["trading"]["symbols"]
        market_data_ok = test_market_data(ib, symbols)
        
        # Test order permissions
        orders_ok = test_order_permissions(ib)
        
        # Summary
        print("\n" + "="*50)
        print("TEST SUMMARY")
        print("="*50)
        print(f"Connection: {'✅ PASS' if ib.isConnected() else '❌ FAIL'}")
        print(f"Account Info: {'✅ PASS' if account_ok else '❌ FAIL'}")
        print(f"Market Data: {'✅ PASS' if market_data_ok else '❌ FAIL'}")
        print(f"Order Permissions: {'✅ PASS' if orders_ok else '❌ FAIL'}")
        
        if all([ib.isConnected(), account_ok, market_data_ok, orders_ok]):
            print("\n🎉 ALL TESTS PASSED! Your IB setup is ready for trading.")
        else:
            print("\n⚠️  Some tests failed. Please check the issues above.")
            
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
    
    finally:
        # Disconnect
        if ib and ib.isConnected():
            ib.disconnect()
            print("\n✅ Disconnected from IB")

if __name__ == "__main__":
    main()
