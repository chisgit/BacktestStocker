import pandas as pd
import numpy as np
import math

# ===== Helpers =====

def vwap(prices: pd.Series, volumes: pd.Series) -> pd.Series:
    pv = prices * volumes
    cum_pv = pv.cumsum()
    cum_vol = volumes.cumsum().replace(0, np.nan)
    return cum_pv / cum_vol

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()

def first_minutes_range(df: pd.DataFrame, minutes: int = 15):
    start = df.index[0]
    end = start + pd.Timedelta(minutes=minutes)
    window = df[(df.index >= start) & (df.index < end)]
    return window['high'].max(), window['low'].min()

def detect_consolidation(df: pd.DataFrame, lookback: int = 20, max_width_bps: float = 25.0) -> pd.Series:
    hh = df['high'].rolling(lookback, min_periods=lookback).max()
    ll = df['low'].rolling(lookback, min_periods=lookback).min()
    mid = (hh + ll) / 2.0
    width_bps = ((hh - ll) / mid.replace(0, np.nan)) * 10000.0
    return width_bps <= max_width_bps

def volume_surge(df: pd.DataFrame, lookback: int = 20, multiple: float = 1.5) -> pd.Series:
    vol_ma = df['volume'].rolling(lookback, min_periods=1).mean()
    return df['volume'] >= multiple * vol_ma

# ===== Trade / Strategies =====

class Trade:
    def __init__(self, ts_open, side, qty, entry, stop=None, target=None, meta=None):
        self.ts_open = ts_open
        self.side = side  # 'long' or 'short'
        self.qty = qty
        self.entry = entry
        self.stop = stop
        self.target = target
        self.ts_close = None
        self.exit = None
        self.pnl = 0.0
        self.meta = meta or {}

class Strategy:
    def __init__(self, name: str, risk_per_trade: float = 0.005, rr: float = 2.0):
        self.name = name
        self.risk_per_trade = risk_per_trade
        self.rr = rr

    def generate_signals(self, df: pd.DataFrame, symbol: str, capital: float):
        raise NotImplementedError

class OpeningRangeBreakout(Strategy):
    def __init__(self, minutes: int = 15, **kwargs):
        super().__init__("OpeningRangeBreakout", **kwargs)
        self.minutes = minutes

    def generate_signals(self, df: pd.DataFrame, symbol: str, capital: float):
        trades = []
        if df.empty:
            return trades
        hi, lo = first_minutes_range(df, self.minutes)
        rng = hi - lo
        if pd.isna(rng) or rng <= 0:
            return trades
        risk_dollars = capital * self.risk_per_trade
        stop_size = rng * 0.5
        if stop_size <= 0:
            return trades

        for ts, row in df.iterrows():
            if row.name <= df.index[0] + pd.Timedelta(minutes=self.minutes):
                continue
            if row['high'] > hi:
                entry = max(hi, row['open'])
                qty = math.floor(risk_dollars / stop_size) if stop_size > 0 else 0
                if qty > 0:
                    stop = entry - stop_size
                    target = entry + stop_size * self.rr
                    trades.append(Trade(ts_open=ts, side='long', qty=qty, entry=entry, stop=stop, target=target, meta={'symbol': symbol, 'strategy': self.name}))
                break
        for ts, row in df.iterrows():
            if row.name <= df.index[0] + pd.Timedelta(minutes=self.minutes):
                continue
            if row['low'] < lo:
                entry = min(lo, row['open'])
                qty = math.floor(risk_dollars / stop_size) if stop_size > 0 else 0
                if qty > 0:
                    stop = entry + stop_size
                    target = entry - stop_size * self.rr
                    trades.append(Trade(ts_open=ts, side='short', qty=qty, entry=entry, stop=stop, target=target, meta={'symbol': symbol, 'strategy': self.name}))
                break
        return trades

class ConsolidationBreakout(Strategy):
    def __init__(self, lookback: int = 20, max_width_bps: float = 25.0, vol_multiple: float = 1.5, **kwargs):
        super().__init__("ConsolidationBreakout", **kwargs)
        self.lookback = lookback
        self.max_width_bps = max_width_bps
        self.vol_multiple = vol_multiple

    def generate_signals(self, df: pd.DataFrame, symbol: str, capital: float):
        trades = []
        if df.empty:
            return trades
        cons = detect_consolidation(df, self.lookback, self.max_width_bps)
        vol_ok = volume_surge(df, lookback=max(10, self.lookback//2), multiple=self.vol_multiple)
        hh = df['high'].rolling(self.lookback, min_periods=self.lookback).max()
        ll = df['low'].rolling(self.lookback, min_periods=self.lookback).min()
        risk_dollars = capital * self.risk_per_trade

        for i in range(self.lookback, len(df)):
            if cons.iloc[i] and vol_ok.iloc[i]:
                if df['high'].iloc[i] >= hh.iloc[i]:
                    entry = max(hh.iloc[i], df['open'].iloc[i])
                    stop_size = (hh.iloc[i] - ll.iloc[i]) * 0.5
                    stop_size = max(stop_size, entry * 0.002)
                    qty = math.floor(risk_dollars / stop_size) if stop_size > 0 else 0
                    if qty > 0:
                        stop = entry - stop_size
                        target = entry + stop_size * self.rr
                        trades.append(Trade(ts_open=df.index[i], side='long', qty=qty, entry=entry, stop=stop, target=target, meta={'symbol': symbol, 'strategy': self.name}))
                elif df['low'].iloc[i] <= ll.iloc[i]:
                    entry = min(ll.iloc[i], df['open'].iloc[i])
                    stop_size = (hh.iloc[i] - ll.iloc[i]) * 0.5
                    stop_size = max(stop_size, entry * 0.002)
                    qty = math.floor(risk_dollars / stop_size) if stop_size > 0 else 0
                    if qty > 0:
                        stop = entry + stop_size
                        target = entry - stop_size * self.rr
                        trades.append(Trade(ts_open=df.index[i], side='short', qty=qty, entry=entry, stop=stop, target=target, meta={'symbol': symbol, 'strategy': self.name}))
        return trades

class VWAPReversion(Strategy):
    def __init__(self, band_atr: float = 1.0, atr_period: int = 14, **kwargs):
        super().__init__("VWAPReversion", **kwargs)
        self.band_atr = band_atr
        self.atr_period = atr_period

    def generate_signals(self, df: pd.DataFrame, symbol: str, capital: float):
        trades = []
        if df.empty:
            return trades
        px = df['close']; vol = df['volume']
        v = vwap(px, vol)
        a = atr(df['high'], df['low'], df['close'], period=self.atr_period)
        upper = v + self.band_atr * a
        lower = v - self.band_atr * a
        risk_dollars = capital * self.risk_per_trade

        for i in range(1, len(df)):
            if df['high'].iloc[i] > upper.iloc[i] and df['close'].iloc[i] < df['open'].iloc[i]:
                entry = df['close'].iloc[i]
                stop_size = max(a.iloc[i] * 0.75, entry * 0.002)
                qty = math.floor(risk_dollars / stop_size) if stop_size > 0 else 0
                if qty > 0:
                    stop = entry + stop_size
                    target = v.iloc[i]
                    trades.append(Trade(ts_open=df.index[i], side='short', qty=qty, entry=entry, stop=stop, target=target, meta={'symbol': symbol, 'strategy': self.name}))
            elif df['low'].iloc[i] < lower.iloc[i] and df['close'].iloc[i] > df['open'].iloc[i]:
                entry = df['close'].iloc[i]
                stop_size = max(a.iloc[i] * 0.75, entry * 0.002)
                qty = math.floor(risk_dollars / stop_size) if stop_size > 0 else 0
                if qty > 0:
                    stop = entry - stop_size
                    target = v.iloc[i]
                    trades.append(Trade(ts_open=df.index[i], side='long', qty=qty, entry=entry, stop=stop, target=target, meta={'symbol': symbol, 'strategy': self.name}))
        return trades

# ===== Backtester =====

class Backtester:
    def __init__(self, capital: float = 100_000.0):
        self.capital = capital
        self.trades = []

    def run(self, data_by_symbol, strategies):
        for symbol, df in data_by_symbol.items():
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                df = df.sort_values('datetime').set_index('datetime')
            df = df[['open','high','low','close','volume']].copy()
            for strat in strategies:
                strat_trades = strat.generate_signals(df, symbol, self.capital)
                for tr in strat_trades:
                    exit_price, exit_ts = self._simulate_exit(df, tr)
                    tr.exit = exit_price
                    tr.ts_close = exit_ts
                    tr.pnl = self._pnl(tr)
                    self.trades.append(tr)

    def _simulate_exit(self, df: pd.DataFrame, tr: Trade):
        idx = df.index.get_loc(tr.ts_open)
        for i in range(idx, len(df)):
            hi = df['high'].iloc[i]; lo = df['low'].iloc[i]
            if tr.side == 'long':
                if tr.target is not None and hi >= tr.target: return tr.target, df.index[i]
                if tr.stop   is not None and lo <= tr.stop:   return tr.stop,   df.index[i]
            else:
                if tr.target is not None and lo <= tr.target: return tr.target, df.index[i]
                if tr.stop   is not None and hi >= tr.stop:   return tr.stop,   df.index[i]
        return df['close'].iloc[-1], df.index[-1]

    def _pnl(self, tr: Trade) -> float:
        return (tr.exit - tr.entry) * tr.qty if tr.side=='long' else (tr.entry - tr.exit) * tr.qty

    def to_frames(self):
        rows = []
        for t in self.trades:
            rows.append({
                'strategy': t.meta.get('strategy',''),
                'symbol': t.meta.get('symbol',''),
                'side': t.side,
                'entry_ts': t.ts_open,
                'exit_ts': t.ts_close,
                'entry': t.entry,
                'exit': t.exit,
                'qty': t.qty,
                'pnl': t.pnl,
                'stop': t.stop,
                'target': t.target
            })
        trades_df = pd.DataFrame(rows)
        summary_df = trades_df.groupby(['symbol','strategy','side'])['pnl'].sum().reset_index().sort_values('pnl', ascending=False)
        return trades_df, summary_df
