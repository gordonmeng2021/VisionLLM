#!/usr/bin/env python3
"""
Trading Records Analysis Script
Analyzes the CSV trading records from the IB trading system.
"""

import pandas as pd
import os
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

def load_trading_data(csv_file="trading_records.csv"):
    """Load trading data from CSV file."""
    if not os.path.exists(csv_file):
        print(f"❌ Trading records file not found: {csv_file}")
        return None
    
    try:
        df = pd.read_csv(csv_file)
        print(f"✅ Loaded {len(df)} trading records from {csv_file}")
        return df
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return None

def analyze_trading_performance(df):
    """Analyze overall trading performance."""
    if df is None or len(df) == 0:
        print("No data to analyze")
        return
    
    print("\n" + "="*60)
    print("TRADING PERFORMANCE ANALYSIS")
    print("="*60)
    
    # Filter only EXIT records for P&L analysis
    exit_trades = df[df['Action'] == 'EXIT'].copy()
    
    if len(exit_trades) == 0:
        print("No completed trades found")
        return
    
    # Convert numeric columns
    exit_trades['PnL_Dollar'] = pd.to_numeric(exit_trades['PnL_Dollar'], errors='coerce')
    exit_trades['PnL_Percent'] = pd.to_numeric(exit_trades['PnL_Percent'], errors='coerce')
    exit_trades['Duration_Minutes'] = pd.to_numeric(exit_trades['Duration_Minutes'], errors='coerce')
    
    # Basic statistics
    total_trades = len(exit_trades)
    winning_trades = len(exit_trades[exit_trades['PnL_Dollar'] > 0])
    losing_trades = len(exit_trades[exit_trades['PnL_Dollar'] < 0])
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    
    total_pnl = exit_trades['PnL_Dollar'].sum()
    avg_pnl = exit_trades['PnL_Dollar'].mean()
    avg_win = exit_trades[exit_trades['PnL_Dollar'] > 0]['PnL_Dollar'].mean() if winning_trades > 0 else 0
    avg_loss = exit_trades[exit_trades['PnL_Dollar'] < 0]['PnL_Dollar'].mean() if losing_trades > 0 else 0
    
    print(f"📊 OVERALL STATISTICS")
    print(f"Total Trades: {total_trades}")
    print(f"Winning Trades: {winning_trades}")
    print(f"Losing Trades: {losing_trades}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"")
    print(f"💰 P&L ANALYSIS")
    print(f"Total P&L: ${total_pnl:.2f}")
    print(f"Average P&L per Trade: ${avg_pnl:.2f}")
    print(f"Average Win: ${avg_win:.2f}")
    print(f"Average Loss: ${avg_loss:.2f}")
    print(f"Risk/Reward Ratio: {abs(avg_win/avg_loss):.2f}" if avg_loss != 0 else "N/A")
    
    # Duration analysis
    avg_duration = exit_trades['Duration_Minutes'].mean()
    print(f"")
    print(f"⏱️  DURATION ANALYSIS")
    print(f"Average Trade Duration: {avg_duration:.1f} minutes")
    
    return exit_trades

def analyze_by_symbol(df):
    """Analyze performance by symbol."""
    if df is None or len(df) == 0:
        return
    
    print("\n" + "="*60)
    print("PERFORMANCE BY SYMBOL")
    print("="*60)
    
    exit_trades = df[df['Action'] == 'EXIT'].copy()
    exit_trades['PnL_Dollar'] = pd.to_numeric(exit_trades['PnL_Dollar'], errors='coerce')
    
    symbol_stats = exit_trades.groupby('Symbol').agg({
        'PnL_Dollar': ['count', 'sum', 'mean'],
        'PnL_Percent': 'mean',
        'Duration_Minutes': 'mean'
    }).round(2)
    
    symbol_stats.columns = ['Trades', 'Total_PnL', 'Avg_PnL', 'Avg_PnL_Pct', 'Avg_Duration']
    
    # Calculate win rates
    win_rates = []
    for symbol in symbol_stats.index:
        symbol_trades = exit_trades[exit_trades['Symbol'] == symbol]
        wins = len(symbol_trades[symbol_trades['PnL_Dollar'] > 0])
        total = len(symbol_trades)
        win_rate = (wins / total) * 100 if total > 0 else 0
        win_rates.append(win_rate)
    
    symbol_stats['Win_Rate'] = win_rates
    
    print(symbol_stats)

def analyze_by_signal_type(df):
    """Analyze performance by signal type (BUY vs SELL)."""
    if df is None or len(df) == 0:
        return
    
    print("\n" + "="*60)
    print("PERFORMANCE BY SIGNAL TYPE")
    print("="*60)
    
    exit_trades = df[df['Action'] == 'EXIT'].copy()
    exit_trades['PnL_Dollar'] = pd.to_numeric(exit_trades['PnL_Dollar'], errors='coerce')
    
    signal_stats = exit_trades.groupby('Signal_Type').agg({
        'PnL_Dollar': ['count', 'sum', 'mean'],
        'PnL_Percent': 'mean',
        'Duration_Minutes': 'mean'
    }).round(2)
    
    signal_stats.columns = ['Trades', 'Total_PnL', 'Avg_PnL', 'Avg_PnL_Pct', 'Avg_Duration']
    
    print(signal_stats)

def analyze_exit_reasons(df):
    """Analyze exit reasons."""
    if df is None or len(df) == 0:
        return
    
    print("\n" + "="*60)
    print("EXIT REASONS ANALYSIS")
    print("="*60)
    
    exit_trades = df[df['Action'] == 'EXIT'].copy()
    exit_trades['PnL_Dollar'] = pd.to_numeric(exit_trades['PnL_Dollar'], errors='coerce')
    
    reason_stats = exit_trades.groupby('Exit_Reason').agg({
        'PnL_Dollar': ['count', 'sum', 'mean'],
        'PnL_Percent': 'mean'
    }).round(2)
    
    reason_stats.columns = ['Count', 'Total_PnL', 'Avg_PnL', 'Avg_PnL_Pct']
    
    print(reason_stats)

def show_recent_trades(df, n=10):
    """Show the most recent trades."""
    if df is None or len(df) == 0:
        return
    
    print(f"\n" + "="*60)
    print(f"RECENT {n} TRADES")
    print("="*60)
    
    # Sort by entry time and show recent trades
    df_sorted = df.sort_values('Entry_Time', ascending=False)
    recent = df_sorted.head(n)
    
    # Select key columns for display
    display_cols = ['Entry_Time', 'Symbol', 'Signal_Type', 'Action', 'Shares', 'Entry_Price', 'Exit_Price', 'PnL_Dollar', 'Exit_Reason']
    available_cols = [col for col in display_cols if col in recent.columns]
    
    print(recent[available_cols].to_string(index=False))

def export_summary_report(df, filename="trading_summary.txt"):
    """Export a summary report to a text file."""
    if df is None or len(df) == 0:
        return
    
    with open(filename, 'w') as f:
        f.write("TRADING PERFORMANCE SUMMARY REPORT\n")
        f.write("=" * 50 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        exit_trades = df[df['Action'] == 'EXIT'].copy()
        exit_trades['PnL_Dollar'] = pd.to_numeric(exit_trades['PnL_Dollar'], errors='coerce')
        
        if len(exit_trades) > 0:
            total_trades = len(exit_trades)
            winning_trades = len(exit_trades[exit_trades['PnL_Dollar'] > 0])
            win_rate = (winning_trades / total_trades) * 100
            total_pnl = exit_trades['PnL_Dollar'].sum()
            
            f.write(f"Total Completed Trades: {total_trades}\n")
            f.write(f"Winning Trades: {winning_trades}\n")
            f.write(f"Win Rate: {win_rate:.1f}%\n")
            f.write(f"Total P&L: ${total_pnl:.2f}\n")
        
        f.write("\nDetailed analysis available in CSV file: trading_records.csv\n")
    
    print(f"📄 Summary report exported to: {filename}")

def main():
    """Main analysis function."""
    print("🔍 Trading Records Analysis")
    print("=" * 60)
    
    # Load data
    df = load_trading_data()
    if df is None:
        return
    
    # Run analysis
    exit_trades = analyze_trading_performance(df)
    analyze_by_symbol(df)
    analyze_by_signal_type(df)
    analyze_exit_reasons(df)
    show_recent_trades(df)
    
    # Export summary
    export_summary_report(df)
    
    print(f"\n✅ Analysis complete!")
    print(f"📊 Data file: trading_records.csv")
    print(f"📄 Summary: trading_summary.txt")

if __name__ == "__main__":
    main()
