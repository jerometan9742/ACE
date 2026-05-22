"""CCXT WebSocket streams — subscribes to 1m/5m/15m OHLCV for all WATCHLIST pairs and fires signal callbacks on candle close."""

import asyncio
import logging
import os
from typing import Callable, Dict, List

from dotenv import load_dotenv

load_dotenv()

EXCHANGE_ID = os.getenv("EXCHANGE", "binance")
TRADING_MODE = os.getenv("TRADING_MODE", "paper")
WATCHLIST = [p.strip() for p in os.getenv("WATCHLIST", "BTC/USDT,ETH/USDT,SOL/USDT").split(",")]
TIMEFRAMES = ["1m", "5m", "15m"]

logger = logging.getLogger(__name__)

_running = False
_exchange = None
_candle_cache: Dict[str, Dict[str, List[Dict]]] = {}  # pair → timeframe → candle list


def _ohlcv_to_dict(row: List) -> Dict:
    """Convert a raw CCXT OHLCV list to a named dict."""
    return {
        "timestamp": row[0],
        "open": row[1],
        "high": row[2],
        "low": row[3],
        "close": row[4],
        "volume": row[5],
    }


async def _build_exchange():
    """Instantiate and return the CCXT Pro exchange, switching to sandbox for paper mode."""
    import ccxt.pro as ccxtpro  # noqa: PLC0415 — deferred to avoid hard dep at import time

    params: Dict = {}
    if TRADING_MODE == "paper" and EXCHANGE_ID == "binance":
        params["options"] = {"defaultType": "future"}

    exchange_class = getattr(ccxtpro, EXCHANGE_ID)
    exchange = exchange_class(params)

    if TRADING_MODE == "paper":
        exchange.set_sandbox_mode(True)

    return exchange


async def _stream_pair_tf(exchange, pair: str, timeframe: str, callback: Callable) -> None:
    """Watch a single pair/timeframe and invoke callback on each new candle close."""
    prev_ts = None

    while _running:
        try:
            ohlcv = await exchange.watch_ohlcv(pair, timeframe)

            if pair not in _candle_cache:
                _candle_cache[pair] = {}
            _candle_cache[pair][timeframe] = [_ohlcv_to_dict(row) for row in ohlcv]

            latest_ts = ohlcv[-1][0] if ohlcv else None
            if latest_ts and latest_ts != prev_ts:
                prev_ts = latest_ts
                candles = _candle_cache[pair][timeframe]
                try:
                    callback(
                        {
                            "pair": pair,
                            "timeframe": timeframe,
                            "candles": candles,
                            "latest": candles[-1] if candles else {},
                        }
                    )
                except Exception as cb_err:
                    logger.error("Callback error for %s %s: %s", pair, timeframe, cb_err)

        except asyncio.CancelledError:
            break
        except Exception as err:
            logger.error("Stream error for %s %s: %s — retrying in 5s", pair, timeframe, err)
            await asyncio.sleep(5)


async def _run_all(callback: Callable) -> None:
    """Launch all pair × timeframe streams concurrently and wait for completion."""
    global _exchange
    _exchange = await _build_exchange()

    tasks = [
        asyncio.create_task(_stream_pair_tf(_exchange, pair, tf, callback))
        for pair in WATCHLIST
        for tf in TIMEFRAMES
    ]

    try:
        await asyncio.gather(*tasks)
    finally:
        if _exchange:
            await _exchange.close()


def start_streams(callback: Callable) -> None:
    """
    Start WebSocket streams for all WATCHLIST pairs on 1m/5m/15m.
    Calls callback(signal_dict) on each candle close.
    Blocking — intended to run as the main event loop.
    """
    global _running
    _running = True
    asyncio.run(_run_all(callback))


def stop_streams() -> None:
    """Signal all WebSocket streams to stop after their next candle."""
    global _running
    _running = False
    logger.info("WebSocket streams stopping")


def get_latest_candles(pair: str, timeframe: str, limit: int = 50) -> List[Dict]:
    """
    Return the most recent cached candles for a pair/timeframe.
    Returns an empty list if no data has been received yet.
    """
    try:
        candles = _candle_cache.get(pair, {}).get(timeframe, [])
        return candles[-limit:] if candles else []
    except Exception as err:
        logger.error("Cache read error for %s %s: %s", pair, timeframe, err)
        return []
