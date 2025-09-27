#!/usr/bin/env bash
set -euo pipefail

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
python "$SCRIPT_DIR/fetch_and_backtest.py"   --symbols "${SYMBOLS:-NVDA,TSLA,QQQ}"   --interval "${INTERVAL:-1min}"   --days "${DAYS_BACK:-5}"   --data-dir "${DATA_DIR:-./data}"   --out-dir "${OUT_DIR:-./out}"
