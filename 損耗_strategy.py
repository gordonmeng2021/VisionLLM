import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple, Optional, Dict

import pandas as pd
import matplotlib.pyplot as plt


# Global default holding period in months (1 = same month end). Change as needed.
HOLD_MONTHS_DEFAULT: int = 1


@dataclass
class Trade:
    symbol: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    shares: float
    allocated_cash: float
    return_pct: float
    pnl_amount: float


def read_symbol_csv(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if 'date' not in df.columns or 'open' not in df.columns or 'close' not in df.columns:
        raise ValueError(f"CSV {csv_path} must contain 'date', 'open', 'close' columns")
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    return df


def month_key(ts: pd.Timestamp) -> Tuple[int, int]:
    return ts.year, ts.month


def add_months(year: int, month: int, n: int) -> Tuple[int, int]:
    # Simple month arithmetic
    total = (year * 12 + (month - 1)) + n
    y = total // 12
    m = (total % 12) + 1
    return y, m


def generate_trades_for_symbol(
    df: pd.DataFrame,
    symbol: str,
    hold_months: int,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
    cash_per_leg: float = 10_000.0,
) -> List[Trade]:
    # Filter by date range if provided
    if start_date is not None:
        df = df[df['date'] >= start_date]
    if end_date is not None:
        df = df[df['date'] <= end_date]
    if df.empty:
        return []

    # Precompute first and last valid rows per month
    df['ym'] = df['date'].dt.to_period('M')
    grouped = df.groupby('ym', as_index=False)
    first_rows = grouped.apply(lambda g: g.nsmallest(1, 'date')).reset_index(drop=True)
    last_rows = grouped.apply(lambda g: g.nlargest(1, 'date')).reset_index(drop=True)

    # Map (year, month) -> (first_row, last_row)
    first_map: Dict[Tuple[int, int], pd.Series] = {
        (row['date'].year, row['date'].month): row for _, row in first_rows.iterrows()
    }
    last_map: Dict[Tuple[int, int], pd.Series] = {
        (row['date'].year, row['date'].month): row for _, row in last_rows.iterrows()
    }

    # Iterate entry months in order
    ym_sorted = sorted(first_map.keys())

    trades: List[Trade] = []
    for (y, m) in ym_sorted:
        entry_row = first_map[(y, m)]
        # Determine exit month after hold_months - 0 months (1 => same month end)
        exit_y, exit_m = add_months(y, m, hold_months - 1)
        exit_key = (exit_y, exit_m)
        exit_row = last_map.get(exit_key)
        if exit_row is None:
            # Not enough data to exit; skip this entry
            continue

        entry_date = pd.Timestamp(entry_row['date'])
        exit_date = pd.Timestamp(exit_row['date'])
        # Ensure chronological
        if exit_date < entry_date:
            continue

        entry_price = float(entry_row['open'])
        exit_price = float(exit_row['close'])
        # Size position with fractional shares so invested cash equals cash_per_leg
        shares = cash_per_leg / entry_price
        # Short return: (entry - exit) / entry
        ret = (entry_price - exit_price) / entry_price
        # PnL for short using fractional shares
        pnl = shares * (entry_price - exit_price)

        trades.append(
            Trade(
                symbol=symbol,
                entry_date=entry_date,
                exit_date=exit_date,
                entry_price=entry_price,
                exit_price=exit_price,
                shares=shares,
                allocated_cash=cash_per_leg,
                return_pct=ret,
                pnl_amount=pnl,
            )
        )

    return trades


def build_equity_curve(
    trades: List[Trade],
    starting_equity: float,
) -> pd.Series:
    # Equity updates at each trade exit date
    if not trades:
        return pd.Series(dtype=float)

    # Aggregate PnL by exit date
    pnl_by_date: Dict[pd.Timestamp, float] = {}
    for t in trades:
        pnl_by_date[t.exit_date] = pnl_by_date.get(t.exit_date, 0.0) + t.pnl_amount

    # Sort by date and cumulatively add to starting equity
    dates = sorted(pnl_by_date.keys())
    equity_values = []
    equity = starting_equity
    for d in dates:
        equity += pnl_by_date[d]
        equity_values.append(equity)

    return pd.Series(data=equity_values, index=pd.to_datetime(dates), name='equity')


def main():
    parser = argparse.ArgumentParser(description="Monthly short-and-cover strategy for SOXL & SOXS")
    parser.add_argument('--symbols', nargs='*', default=['SOXL', 'SOXS'], help='Symbols to include')
    parser.add_argument('--data-dir', default='data', help='Directory containing {SYMBOL}.csv files')
    parser.add_argument('--hold-months', type=int, default=HOLD_MONTHS_DEFAULT, help='Holding period in months (1 = same month end)')
    parser.add_argument('--cash-per-leg', type=float, default=10_000.0, help='Capital allocated per short leg')
    parser.add_argument('--start-date', type=str, default=None, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default=None, help='End date (YYYY-MM-DD)')
    parser.add_argument('--plot-file', type=str, default='損耗_strategy_equity.png', help='Output plot file path')
    parser.add_argument('--trades-csv', type=str, default='損耗_strategy_trades.csv', help='Output trades CSV path')

    args = parser.parse_args()

    start_date = pd.to_datetime(args.start_date) if args.start_date else None
    end_date = pd.to_datetime(args.end_date) if args.end_date else None

    all_trades: List[Trade] = []
    for symbol in args.symbols:
        csv_path = f"{args.data_dir}/{symbol}.csv"
        df = read_symbol_csv(csv_path)
        trades = generate_trades_for_symbol(
            df=df,
            symbol= symbol,
            hold_months=args.hold_months,
            start_date=start_date,
            end_date=end_date,
            cash_per_leg=args.cash_per_leg,
        )
        all_trades.extend(trades)

    # Compute starting equity as total capital allocated across legs
    starting_equity = args.cash_per_leg * len(args.symbols)

    # Build equity curve aggregated across symbols (PnL summed by exit day)
    equity_curve = build_equity_curve(all_trades, starting_equity=starting_equity)

    # Net return
    if equity_curve.empty:
        print("No trades generated (check data range or holding period).")
        return

    final_equity = float(equity_curve.iloc[-1])
    net_return = (final_equity / starting_equity) - 1.0

    # Save trades CSV
    trades_df = pd.DataFrame([
        {
            'symbol': t.symbol,
            'entry_date': t.entry_date.date(),
            'exit_date': t.exit_date.date(),
            'entry_price': t.entry_price,
            'exit_price': t.exit_price,
            'shares': t.shares,
            'allocated_cash': t.allocated_cash,
            'return_pct': t.return_pct,
            'pnl_amount': t.pnl_amount,
        }
        for t in all_trades
    ])
    trades_df.sort_values(['exit_date', 'symbol']).to_csv(args.trades_csv, index=False)

    # Plot equity curve
    plt.figure(figsize=(10, 5))
    equity_curve.plot()
    plt.title(f"損耗 Strategy Equity Curve (hold_months={args.hold_months})\nNet Return: {net_return:.2%}")
    plt.xlabel('Date')
    plt.ylabel('Equity')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(args.plot_file, dpi=150)

    # Print summary
    print(f"Starting equity: {starting_equity:,.2f}")
    print(f"Final equity:    {final_equity:,.2f}")
    print(f"Net return:      {net_return:.2%}")
    print(f"Trades saved to:  {args.trades_csv}")
    print(f"Plot saved to:    {args.plot_file}")


if __name__ == '__main__':
    main()


