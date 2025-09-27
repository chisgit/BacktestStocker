# Alpha Backtest: NVDA / TSLA / QQQ (Intraday)

Fetch intraday data via **Twelve Data** and run three intraday strategies:
- Opening Range Breakout (15m)
- Consolidation Breakout (tight-range + volume surge)
- VWAP Mean Reversion (ATR bands)

## Setup
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # then edit .env and add your TWELVE_DATA_API_KEY
```

## Run
```bash
bash run.sh
```

Outputs: `./out/trades.csv` and `./out/summary.csv`

## Direct run
```bash
python fetch_and_backtest.py --symbols NVDA,TSLA,QQQ --interval 1min --days 7 --data-dir ./data --out-dir ./out
```
