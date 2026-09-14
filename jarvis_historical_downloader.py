#!/usr/bin/env python3
"""Download completed Binance spot OHLCV candles for offline JARVIS replay.

This is a data-preparation utility only. It never creates a trading client,
loads a model, or starts JARVIS. The output is a local CSV suitable for
jarvis_backtester.py.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
import requests

BASE_URL = "https://data-api.binance.vision/api/v3/klines"
VALID_INTERVALS = {
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"
}
INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000,
    "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000, "3d": 259_200_000,
    "1w": 604_800_000,
}
COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def parse_utc(value: str) -> datetime:
    """Parse ISO date/time; a date means 00:00:00 UTC."""
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid UTC date/time: {value}") from exc
    return dt.replace(tzinfo=dt.tzinfo or timezone.utc).astimezone(timezone.utc)


def interval_close_ms(open_ms: int, interval: str) -> int:
    """Return the nominal close boundary for fixed-duration Binance intervals."""
    if interval not in INTERVAL_MS:
        raise ValueError(f"Interval {interval} needs explicit --start/--end handling")
    return open_ms + INTERVAL_MS[interval]


def fetch_page(session: requests.Session, symbol: str, interval: str, start_ms: int, end_ms: int) -> list:
    params = {"symbol": symbol, "interval": interval, "startTime": start_ms, "endTime": end_ms, "limit": 1000}
    last_error: Optional[Exception] = None
    for attempt in range(4):
        try:
            response = session.get(BASE_URL, params=params, timeout=30)
            if response.status_code in (418, 429, 500, 502, 503, 504):
                response.raise_for_status()
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("Binance response was not a candle list")
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt == 3:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Could not download {symbol} {interval}: {last_error}")


def download(symbol: str, interval: str, start: datetime, end: datetime) -> pd.DataFrame:
    if interval not in VALID_INTERVALS:
        raise ValueError(f"Unsupported Binance interval: {interval}")
    if start >= end:
        raise ValueError("--start must be earlier than --end")
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    # Binance treats endTime as inclusive; subtract one millisecond so --end is
    # genuinely exclusive and an end-boundary candle cannot leak into the test.
    request_end_ms = end_ms - 1
    rows: List[list] = []
    cursor = start_ms
    with requests.Session() as session:
        session.headers.update({"User-Agent": "jarvis-historical-data-prep/1.0"})
        while cursor < end_ms:
            page = fetch_page(session, symbol, interval, cursor, request_end_ms)
            if not page:
                break
            rows.extend(page)
            next_cursor = int(page[-1][0]) + (INTERVAL_MS.get(interval, 1))
            if next_cursor <= cursor:
                raise RuntimeError("Non-advancing Binance candle page; stopped to avoid duplicate data")
            cursor = next_cursor
            if len(page) == 1000:
                time.sleep(0.15)
    if not rows:
        raise RuntimeError(f"No candles returned for {symbol} in requested range")
    frame = pd.DataFrame(rows).iloc[:, [0, 1, 2, 3, 4, 5]]
    frame.columns = COLUMNS
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    for col in COLUMNS[1:]:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    frame = frame.drop_duplicates("timestamp").sort_values("timestamp")

    # The final candle is usable only if its close boundary is strictly before now.
    # For monthly candles, Binance's close time is supplied in column 6; we skip
    # the newest row conservatively rather than risking an incomplete candle.
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    if interval == "1M":
        frame = frame.iloc[:-1]
    else:
        keep = [interval_close_ms(int(ts.timestamp() * 1000), interval) <= now_ms for ts in frame["timestamp"]]
        frame = frame.loc[keep]
    if frame.empty:
        raise RuntimeError("Requested range contains no completed candles")
    return frame


def default_output(symbol: str, interval: str, start: datetime, end: datetime) -> Path:
    stamp = f"{start:%Y%m%d}_{end:%Y%m%d}"
    return Path("data") / f"{symbol}_{interval}_{stamp}.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download completed Binance OHLCV candles for offline JARVIS backtests")
    parser.add_argument("--symbol", default="BTCUSDT", help="Binance spot symbol, e.g. BTCUSDT")
    parser.add_argument("--tf", default="1h", choices=sorted(VALID_INTERVALS), help="Binance candle timeframe")
    parser.add_argument("--start", type=parse_utc, help="UTC start (YYYY-MM-DD or ISO-8601)")
    parser.add_argument("--end", type=parse_utc, help="UTC end (exclusive; default: current UTC time)")
    parser.add_argument("--days", type=int, help="Number of calendar days ending at --end/current time; alternative to --start")
    parser.add_argument("--output", type=Path, help="Output CSV path (default: data/<symbol>_<tf>_<dates>.csv)")
    args = parser.parse_args()
    if bool(args.start) == bool(args.days):
        parser.error("Specify exactly one of --start or --days")
    if args.days is not None and args.days <= 0:
        parser.error("--days must be positive")
    end = args.end or datetime.now(timezone.utc)
    start = args.start or (end - timedelta(days=args.days))
    symbol = args.symbol.upper().strip()
    if not symbol.isalnum():
        parser.error("--symbol must contain letters/numbers only")
    output = args.output or default_output(symbol, args.tf, start, end)
    frame = download(symbol, args.tf, start, end)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
    print(f"Saved {len(frame):,} completed {args.tf} candles for {symbol}")
    print(f"Range: {frame['timestamp'].iloc[0]} to {frame['timestamp'].iloc[-1]}")
    print(f"CSV: {output}")
    print("Use this exact file with jarvis_backtester.py; it does not place orders or start JARVIS.")


if __name__ == "__main__":
    main()
