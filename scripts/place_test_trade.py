#!/usr/bin/env python3
"""Place a single paper BUY on BTC/USDT for manual end-to-end testing.

Usage:
    /root/ACE/venv/bin/python /root/ACE/scripts/place_test_trade.py

The trade will appear on the dashboard Positions tab and trigger Telegram
alerts on open. When SL or TP is hit the price monitor sends a close alert.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from execution.ccxt_client import get_current_price
from execution.paper_trader import place_order

pair = "BTC/USDT"
price = get_current_price(pair)
if price <= 0:
    print(f"ERROR: Could not fetch {pair} price from exchange")
    sys.exit(1)

sl = round(price - 100, 2)
tp = round(price + 100, 2)

print(f"{pair} current price : ${price:,.2f}")
print(f"Placing BUY 0.001 BTC | SL: ${sl:,.2f} | TP: ${tp:,.2f}")

decision = {
    "action": "BUY",
    "confidence": 8.0,
    "confluence_score": 8,
    "reasoning": "manual test trade",
}

result = place_order(
    pair=pair,
    side="BUY",
    quantity=0.001,
    price=price,
    sl_price=sl,
    tp_price=tp,
    decision=decision,
)

if result.get("status") == "filled":
    print(f"Order filled : {result['order_id']}")
    print(f"  Entry : ${result['entry_price']:,.2f}")
    print(f"  SL    : ${result['sl_price']:,.2f}")
    print(f"  TP    : ${result['tp_price']:,.2f}")
    print("Trade logged to logs/trades.jsonl — check dashboard Positions tab")
else:
    print(f"Order failed : {result.get('error')}")
    sys.exit(1)
