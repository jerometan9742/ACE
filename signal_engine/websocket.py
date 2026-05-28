"""CCXT WebSocket streams — subscribes to 1m/5m/15m OHLCV for all WATCHLIST pairs and fires signal callbacks on candle close."""

import asyncio
import logging
import os
from typing import Callable, Dict, List, Optional

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

_WS_MAX_RETRIES = 10
_WS_ALERT_AFTER = 180  # seconds before sending Telegram alert about sustained outage


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


def _ws_backoff(retry: int) -> int:
    """Exponential backoff: 5s → 10s → 20s → 40s → 60s max."""
    return min(5 * (2 ** (retry - 1)), 60)


async def _cancellable_sleep(seconds: int) -> None:
    """Sleep in 1-second ticks so a _running=False check terminates it promptly."""
    for _ in range(seconds):
        if not _running:
            return
        await asyncio.sleep(1)


async def _stream_pair_tf(exchange, pair: str, timeframe: str, callback: Callable) -> None:
    """Watch a single pair/timeframe with exponential backoff reconnection."""
    prev_ts = None
    retry = 0
    down_since: Optional[float] = None

    while _running:
        err_msg = None
        try:
            ohlcv = await exchange.watch_ohlcv(pair, timeframe)

            # Successful data — reset backoff counters
            if retry > 0:
                logger.info("Stream %s %s reconnected after %d attempt(s)", pair, timeframe, retry)
                retry = 0
                down_since = None

            _candle_cache.setdefault(pair, {})[timeframe] = [_ohlcv_to_dict(row) for row in ohlcv]

            latest_ts = ohlcv[-1][0] if ohlcv else None
            if latest_ts and latest_ts != prev_ts:
                prev_ts = latest_ts
                candles = _candle_cache[pair][timeframe]
                try:
                    callback({
                        "pair": pair,
                        "timeframe": timeframe,
                        "candles": candles,
                        "latest": candles[-1] if candles else {},
                    })
                except Exception as cb_err:
                    logger.error("Callback error for %s %s: %s", pair, timeframe, cb_err)
            continue  # success — skip reconnect block below

        except asyncio.CancelledError:
            if not _running:
                break  # intentional shutdown — exit cleanly
            # CCXT raised CancelledError internally (connection drop in aiohttp layer)
            err_msg = "CancelledError (WebSocket dropped)"
            logger.warning("CancelledError on %s %s — treating as connection drop", pair, timeframe)

        except Exception as err:
            err_msg = str(err)

        # --- reconnect logic (only reached on error) ---
        if not _running:
            break

        loop = asyncio.get_event_loop()
        if down_since is None:
            down_since = loop.time()

        retry += 1
        down_duration = loop.time() - down_since

        if retry > _WS_MAX_RETRIES:
            logger.error(
                "Stream %s %s gave up after %d retries — stream is dead",
                pair, timeframe, _WS_MAX_RETRIES,
            )
            break

        wait = _ws_backoff(retry)

        if down_duration >= _WS_ALERT_AFTER:
            try:
                from monitoring.telegram_alerts import _send
                _send(
                    f"⚠️ ACE WebSocket {pair} {timeframe} down for "
                    f"{int(down_duration)}s — retry {retry}/{_WS_MAX_RETRIES}"
                )
            except Exception:
                pass

        logger.error(
            "Stream error %s %s: %s — retry %d/%d in %ds",
            pair, timeframe, err_msg, retry, _WS_MAX_RETRIES, wait,
        )
        await _cancellable_sleep(wait)


async def _run_all(callback: Callable) -> None:
    """Launch all pair × timeframe streams concurrently with graceful shutdown."""
    global _exchange
    _exchange = await _build_exchange()

    tasks = [
        asyncio.create_task(
            _stream_pair_tf(_exchange, pair, tf, callback),
            name=f"ws-{pair}-{tf}",
        )
        for pair in WATCHLIST
        for tf in TIMEFRAMES
    ]

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        logger.info("WebSocket gather cancelled — shutting down streams")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if _exchange:
            await _exchange.close()
            _exchange = None


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
    """Signal all WebSocket streams to stop after their next candle (or backoff tick)."""
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
