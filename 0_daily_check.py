from ib_insync import *
import pandas as pd
from datetime import datetime, timedelta
import pytz
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.float_format', lambda x: '${:,.2f}'.format(x) if isinstance(x, (float, int)) else str(x))
pd.set_option('display.width', None)
pd.set_option('display.colheader_justify', 'center')

class IBPortfolioMonitor:
    def __init__(self):
        self.ib = IB()
        
    def connect(self, host='127.0.0.1', port=4002, clientId=2):
        """Connect to TWS or IB Gateway"""
        try:
            self.ib.connect(host, port, clientId)
            return True
        except Exception as e:
            print("\n" + "="*50)
            print(f"Error connecting to IB: {str(e)}")
            print("="*50)
            return False
            
    def format_currency(self, value):
        """Format currency values with color indicators"""
        try:
            val = float(value)
            return f"${val:,.2f}"
        except:
            return str(value)
            
    def get_account_summary(self):
        """Get account summary including cash balance, equity, etc."""
        summary = {}
        account_values = self.ib.accountSummary()
        
        # Create a mapping of essential fields we want to display
        essential_fields = {
            'UnrealizedPnL_BASE': 'Unrealized P&L',
            'RealizedPnL_BASE': 'Realized P&L',
            'NetLiquidation_USD': 'Net Liquidation Value',
            'TotalCashValue_USD': 'Total Cash',
            'AvailableFunds_USD': 'Available Funds',
            'BuyingPower_USD': 'Buying Power',
            'GrossPositionValue_USD': 'Gross Position Value',
            'MaintMarginReq_USD': 'Maintenance Margin'
        }
        
        for av in account_values:
            field_key = f"{av.tag}_{av.currency}"
            if field_key in essential_fields:
                summary[essential_fields[field_key]] = float(av.value)
            
        df = pd.DataFrame([summary]).T.rename(columns={0: 'Value'})
        
        # Add total P&L row
        total_pnl = df.loc['Unrealized P&L', 'Value'] + df.loc['Realized P&L', 'Value']
        df.loc['Total P&L', 'Value'] = total_pnl
        
        # Reorder rows to show P&L first
        desired_order = [
            'Unrealized P&L', 'Realized P&L', 'Total P&L',
            'Net Liquidation Value', 'Total Cash', 'Available Funds',
            'Buying Power', 'Gross Position Value', 'Maintenance Margin'
        ]
        df = df.reindex(desired_order)
        
        return df
        
    def get_portfolio_positions(self):
        """Get current portfolio positions with details"""
        portfolio = self.ib.portfolio()
        
        positions = []
        for position in portfolio:
            pos_data = {
                'Symbol': position.contract.symbol,
                'Position': position.position,
                'Market Price': position.marketPrice,
                'Market Value': position.marketValue,
                'Avg Cost': position.averageCost,
                'Unrealized P&L': position.unrealizedPNL,
                'Realized P&L': position.realizedPNL,
                'Total P&L': position.unrealizedPNL + position.realizedPNL
            }
            positions.append(pos_data)
            
        df = pd.DataFrame(positions)
        if not df.empty:
            # Add totals row
            totals = df.sum(numeric_only=True)
            totals['Symbol'] = 'TOTAL'
            df = df._append(totals, ignore_index=True)
            
            # Reorder columns
            column_order = [
                'Symbol', 'Position', 'Market Price', 'Market Value',
                'Avg Cost', 'Unrealized P&L', 'Realized P&L', 'Total P&L'
            ]
            df = df[column_order]
            
            # Format specific columns
            for col in df.columns:
                if col == 'Position':
                    df[col] = df[col].apply(lambda x: f"{x:,.0f}")  # Format as integer with commas
                elif col != 'Symbol':
                    df[col] = df[col].apply(self.format_currency)  # Format as currency
                    
        return df
        
    def get_open_orders(self):
        """Get all open orders"""
        orders = self.ib.openOrders()
        
        order_details = []
        for order in orders:
            order_data = {
                'Symbol': order.contract.symbol,
                'Action': order.order.action,
                'Type': order.order.orderType,
                'Quantity': order.order.totalQuantity,
                'Price': order.order.lmtPrice if hasattr(order.order, 'lmtPrice') else None,
                'Stop Price': order.order.auxPrice if hasattr(order.order, 'auxPrice') else None,
                'Status': order.orderStatus.status
            }
            order_details.append(order_data)
            
        df = pd.DataFrame(order_details)
        if not df.empty:
            # Format numeric columns
            if 'Price' in df.columns:
                df['Price'] = df['Price'].apply(self.format_currency)
            if 'Stop Price' in df.columns:
                df['Stop Price'] = df['Stop Price'].apply(self.format_currency)
        return df
        
    def get_order_history(self):
        """Get execution history for the current session with essential trade details"""
        trades = self.ib.reqExecutions()
        # Get current time in US/Eastern timezone
        eastern_tz = pytz.timezone('US/Eastern')
        now = datetime.now(eastern_tz)
        yesterday = now - timedelta(days=1)
        yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        trade_details = []
        for trade in trades:
            # Convert trade time to US/Eastern
            trade_time = trade.time.astimezone(eastern_tz)
            
            # Skip if trade is older than yesterday
            if trade_time < yesterday:
                continue
                
            # Extract essential trade information
            trade_data = {
                'Time': trade_time.strftime('%Y-%m-%d %H:%M:%S'),
                'Symbol': trade.contract.symbol,
                'Side': trade.execution.side,
                'Quantity': trade.execution.shares,
                'Exchange': trade.execution.exchange,
                'Order ID': trade.execution.orderId,
                'Avg Price': trade.execution.avgPrice,
                'Commission': trade.commissionReport.commission
            }
            trade_details.append(trade_data)
            
        df = pd.DataFrame(trade_details)
        if not df.empty:
            # Sort by time
            df = df.sort_values('Time', ascending=False)
            
            # Format numeric columns
            df['Avg Price'] = df['Avg Price'].apply(self.format_currency)
            df['Commission'] = df['Commission'].apply(self.format_currency)
            df['Quantity'] = df['Quantity'].apply(lambda x: f"{x:,.0f}")
            
            # Add summary row
            summary = pd.DataFrame([{
                'Time': '',
                'Symbol': '',
                'Side': '',
                'Quantity': '',
                'Exchange': '',
                'Order ID': '',
                'Avg Price': '',
                'Commission': ''
            }])
            
            df = pd.concat([df, summary], ignore_index=True)
            
        return df
        
    def show_all_details(self):
        """Show all portfolio details including positions, orders, and PnL"""
        # Account Summary
        print("\n" + "="*80)
        print(" "*30 + "ACCOUNT SUMMARY")
        print("="*80)
        summary_df = self.get_account_summary()
        if summary_df.empty:
            print("No account summary available")
        else:
            print(summary_df)
        
        # Portfolio Positions
        print("\n" + "="*80)
        print(" "*30 + "PORTFOLIO POSITIONS")
        print("="*80)
        positions_df = self.get_portfolio_positions()
        if positions_df.empty:
            print("No positions found")
        else:
            print(positions_df.to_string(index=False))
        
        # Open Orders
        print("\n" + "="*80)
        print(" "*30 + "OPEN ORDERS")
        print("="*80)
        orders_df = self.get_open_orders()
        if orders_df.empty:
            print("No open orders")
        else:
            print(orders_df.to_string(index=False))
        
        # Recent Executions
        print("\n" + "="*80)
        print(" "*30 + "RECENT EXECUTIONS")
        print("="*80)
        executions_df = self.get_order_history()
        if executions_df.empty:
            print("No recent executions")
        else:
            print(executions_df.to_string(index=False))
        
    def disconnect(self):
        """Disconnect from IB"""
        self.ib.disconnect()
        print("\n" + "="*80)
        print(" "*30 + "Disconnected from IB")
        print("="*80)

# Example usage
if __name__ == "__main__":
    # Create monitor instance
    monitor = IBPortfolioMonitor()
    
    # Connect to IB (make sure TWS or IB Gateway is running)
    if monitor.connect():
        try:
            # Show all portfolio details
            monitor.show_all_details()
        finally:
            # Disconnect when done
            monitor.disconnect() 