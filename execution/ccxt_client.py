"""CCXT exchange connector — handles order placement, balance fetching, and WebSocket market data for paper and live modes."""

import logging
import os
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_TRADING_MODE = os.getenv("TRADING_MODE", "paper")
_EXCHANGE_ID = os.getenv("EXCHANGE", "binance")
_TESTNET_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", "")
_TESTNET_SECRET = os.getenv("BINANCE_TESTNET_SECRET", "")
_LIVE_CONFIRMED = os.getenv("LIVE_CONFIRMED", "false").lower() == "true"

_exchange_instance = None


def _guard_live_mode() -> None:
    """Raise immediately if live mode is attempted without explicit confirmation."""
    if _TRADING_MODE == "live":
        if not _LIVE_CONFIRMED:
            raise RuntimeError(
                "LIVE trading mode requires LIVE_CONFIRMED=true in .env — "
                "this is not set. Refusing to run to protect real funds."
            )
        logger.warning("LIVE MODE ACTIVE — real funds are at risk on every call")


def get_exchange():
    """
    Return a cached CCXT exchange instance.

    Paper mode: Binance testnet (sandbox=True).
    Live mode: only if TRADING_MODE=live AND LIVE_CONFIRMED=true.
    """
    global _exchange_instance
    if _exchange_instance is not None:
        return _exchange_instance

    import ccxt  # deferred — not required at import time

    _guard_live_mode()

    if _TRADING_MODE == "paper":
        exchange = ccxt.binance({
            "apiKey": _TESTNET_API_KEY,
            "secret": _TESTNET_SECRET,
            "options": {"defaultType": "spot"},
            "urls": {
                "api": {
                    "public":  "https://testnet.binance.vision/api",
                    "private": "https://testnet.binance.vision/api",
                },
            },
        })
        exchange.set_sandbox_mode(True)
        logger.info("CCXT connected to Binance testnet (paper mode)")
    else:
        # Live — only reachable when _guard_live_mode() passes
        exchange = ccxt.binance({
            "apiKey": os.getenv("BINANCE_API_KEY", ""),
            "secret": os.getenv("BINANCE_SECRET", ""),
            "options": {"defaultType": "spot"},
        })
        logger.warning("CCXT connected to Binance LIVE — real funds at risk")

    _exchange_instance = exchange
    return exchange


def _reset_exchange_for_testing() -> None:
    """Clear cached exchange instance for test isolation."""
    global _exchange_instance
    _exchange_instance = None


def get_balance() -> dict:
    """Return USDT balance: {total, free, used, currency}."""
    try:
        balance = get_exchange().fetch_balance()
        usdt = balance.get("USDT", {})
        return {
            "total": float(usdt.get("total", 0.0)),
            "free":  float(usdt.get("free", 0.0)),
            "used":  float(usdt.get("used", 0.0)),
            "currency": "USDT",
        }
    except Exception as exc:
        logger.error("get_balance failed: %s", exc)
        return {"total": 0.0, "free": 0.0, "used": 0.0, "currency": "USDT"}


def get_current_price(pair: str) -> float:
    """Return the latest ticker price for pair. Returns 0.0 on error."""
    try:
        ticker = get_exchange().fetch_ticker(pair)
        return float(ticker.get("last", 0.0))
    except Exception as exc:
        logger.error("get_current_price(%s) failed: %s", pair, exc)
        return 0.0


def get_order_book(pair: str, limit: int = 20) -> dict:
    """Return {bids, asks, timestamp} for pair."""
    try:
        ob = get_exchange().fetch_order_book(pair, limit=limit)
        return {
            "bids": ob.get("bids", []),
            "asks": ob.get("asks", []),
            "timestamp": ob.get("timestamp", 0),
        }
    except Exception as exc:
        logger.error("get_order_book(%s) failed: %s", pair, exc)
        return {"bids": [], "asks": [], "timestamp": 0}


def get_ohlcv(pair: str, timeframe: str, limit: int = 100) -> List[dict]:
    """Return list of {timestamp, open, high, low, close, volume} candle dicts."""
    try:
        raw = get_exchange().fetch_ohlcv(pair, timeframe, limit=limit)
        return [
            {"timestamp": r[0], "open": r[1], "high": r[2],
             "low": r[3], "close": r[4], "volume": r[5]}
            for r in raw
        ]
    except Exception as exc:
        logger.error("get_ohlcv(%s, %s) failed: %s", pair, timeframe, exc)
        return []


def get_atr(pair: str, period: int = 14) -> float:
    """Calculate ATR(period) from recent 15m OHLCV. Returns 0.0 on error."""
    try:
        candles = get_ohlcv(pair, "15m", limit=period + 1)
        if len(candles) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(candles)):
            h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return round(sum(trs[-period:]) / period, 8)
    except Exception as exc:
        logger.error("get_atr(%s) failed: %s", pair, exc)
        return 0.0
