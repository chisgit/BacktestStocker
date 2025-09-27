import os
import argparse
from dotenv import load_dotenv
from providers.twelvedata_client import fetch_intraday_twelvedata
from backtester import Backtester, OpeningRangeBreakout, ConsolidationBreakout, VWAPReversion

def ensure_dirs(*paths):
    for p in paths: os.makedirs(p, exist_ok=True)

def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', default=os.getenv('SYMBOLS','NVDA,TSLA,QQQ'))
    parser.add_argument('--interval', default=os.getenv('INTERVAL','1min'))
    parser.add_argument('--days', type=int, default=int(os.getenv('DAYS_BACK','5')))
    parser.add_argument('--data-dir', default=os.getenv('DATA_DIR','./data'))
    parser.add_argument('--out-dir', default=os.getenv('OUT_DIR','./out'))
    parser.add_argument('--capital', type=float, default=100000.0)
    args = parser.parse_args()

    ensure_dirs(args.data_dir, args.out_dir)

    api_key = os.getenv('TWELVE_DATA_API_KEY')
    if not api_key:
        raise SystemExit("Missing TWELVE_DATA_API_KEY")

    symbols = [s.strip().upper() for s in args.symbols.split(',') if s.strip()]
    outputsize = max(500, args.days * 390)

    data_by_symbol = {}
    for sym in symbols:
        print(f"[Fetch] {sym}")
        df = fetch_intraday_twelvedata(sym, args.interval, outputsize, api_key)
        df.to_csv(os.path.join(args.data_dir, f"{sym}_{args.interval}.csv"), index=False)
        data_by_symbol[sym] = df

    strategies = [
        OpeningRangeBreakout(minutes=15, risk_per_trade=0.005, rr=2.0),
        ConsolidationBreakout(lookback=20, max_width_bps=30.0, vol_multiple=1.5, risk_per_trade=0.005, rr=2.0),
        VWAPReversion(band_atr=1.0, atr_period=14, risk_per_trade=0.005, rr=2.0),
    ]

    bt = Backtester(capital=args.capital)
    bt.run(data_by_symbol, strategies)
    trades, summary = bt.to_frames()

    trades.to_csv(os.path.join(args.out_dir, "trades.csv"), index=False)
    summary.to_csv(os.path.join(args.out_dir, "summary.csv"), index=False)
    print(f"[DONE] {os.path.join(args.out_dir, 'trades.csv')}")
    print(f"[DONE] {os.path.join(args.out_dir, 'summary.csv')}")

if __name__ == "__main__":
    main()
