# Historical data preparation for JARVIS replay

`jarvis_historical_downloader.py` downloads completed public Binance spot OHLCV candles into a local CSV. It is only a data-preparation command: it does not start JARVIS, load Ollama, use the GPU, or send an order.

## Download data

Use one of `--days` or `--start` (not both). All times are UTC.

```bash
# First broad test: two years of BTC one-hour candles
python3 jarvis_historical_downloader.py --symbol BTCUSDT --tf 1h --days 730

# A detailed six-month ETH test
python3 jarvis_historical_downloader.py --symbol ETHUSDT --tf 15m --days 180

# Fixed, reproducible historical range (end is exclusive)
python3 jarvis_historical_downloader.py --symbol SOLUSDT --tf 5m \
  --start 2025-01-01 --end 2025-04-01
```

The command writes a CSV under `data/` with these columns:

```text
timestamp,open,high,low,close,volume
```

Only candles that had already closed when downloaded are written. Save the generated file unchanged so a replay can be repeated against the same data.

## Run historical replay

Pass the saved file to the backtester:

```bash
python3 jarvis_backtester.py \
  --data-file data/BTCUSDT_1h_20240914_20260914.csv \
  --symbol BTCUSDT --tf 1h --capital 1000 \
  --slippage-bps 5 --fee-bps 10
```

The filename includes the date range and will differ based on when the data is downloaded. Use the CSV path printed by the downloader.

## Scope and limits

The CSV contains price/volume candles only. The historical replay can use this data for the core JARVIS math/GPU decision path, but it cannot faithfully replay historical options-chain, funding, order-book, or cross-exchange snapshots without timestamp-aligned historical datasets for those inputs. Current-day market data must never be substituted for old timestamps because that would make the result invalid.
