import requests
import pandas as pd

def fetch_intraday_twelvedata(symbol: str, interval: str, outputsize: int, api_key: str) -> pd.DataFrame:
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": api_key,
        "adjustment": "splits",
        "format": "JSON"
    }
    r = requests.get(url, params=params, timeout=30)
    j = r.json()
    if "values" not in j:
        raise RuntimeError(f"TwelveData error for {symbol}: {j}")
    df = pd.DataFrame(j["values"]).iloc[::-1].reset_index(drop=True)
    df["datetime"] = pd.to_datetime(df["datetime"])
    for col in ["open","high","low","close","volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["symbol"] = symbol
    return df[["datetime","open","high","low","close","volume","symbol"]]
