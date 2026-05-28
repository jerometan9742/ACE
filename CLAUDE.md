# CLAUDE.md — ACE Intraday Trading Bot

> Claude Code reads this file before executing any prompt.
> This is the single source of truth for the ACE project.

---

## What This Project Is

ACE is an autonomous intraday crypto trading bot. It trades BTC, ETH, and SOL on 1m/5m/15m timeframes using a 10-agent Claude pipeline, a proprietary Confluence Engine, and an AMD/SMC/ICT strategy stack.

ACE is a separate project from Fred (swing trading bot at /root/TradingBot). Do NOT mix files between these two projects.

---

## Critical Rules — Read Before Every Change

### Never Do These
- NEVER push API keys, secrets, or credentials to GitHub
- NEVER reference an indicator in an agent prompt without fetching its value in the data layer (Fred's ADX ghost filter bug — never repeat this)
- NEVER modify live trading parameters without backtesting first
- NEVER switch from paper trading to live without explicit user confirmation
- NEVER hardcode equity values — always fetch live from exchange
- NEVER run `systemctl stop` on both services simultaneously
- NEVER edit .env directly on VPS — always push from local and let auto-deploy handle it

### Always Do These
- ALWAYS read CLAUDE.md before making any changes
- ALWAYS end every Claude Code prompt with: push to GitHub when done
- ALWAYS run unit tests before pushing: `pytest tests/ -v`
- ALWAYS check that every indicator in agent prompts has a corresponding fetch call in `signal_engine/`
- ALWAYS use `paper` mode until explicitly told to switch to `live`
- ALWAYS use `systemd` for services — never run processes directly in terminal
- ALWAYS add a watchdog check for any new service or API dependency added

---

## Architecture Overview

```
signal_engine/          ← Pure Python, fast, no LLM
    websocket.py        ← CCXT WebSocket streams
    amd_detector.py     ← AMD phase detection
    fvg.py              ← Fair Value Gap detection
    order_blocks.py     ← Order Block identification
    bos_choch.py        ← Break of Structure / Change of Character
    judas_swing.py      ← Manipulation candle detector (custom)
    liquidity_score.py  ← Liquidity sweep quality scorer (custom)
    confluence.py       ← Confluence Engine 0–10 scorer (custom)
    session.py          ← Kill zone detection (Asia/London/NY)
    correlation.py      ← Multi-pair correlation filter (custom)

agents/
    regime_detector.py  ← AMD phase agent (Haiku)
    technical.py        ← Multi-timeframe technical agent (Haiku)
    order_flow.py       ← Order book depth agent (Haiku)
    sentiment.py        ← Crypto sentiment agent (Haiku)
    bull_researcher.py  ← Bull case agent (Sonnet)
    bear_researcher.py  ← Bear case agent (Sonnet)
    consensus.py        ← Consensus builder — 5/7 supermajority (Sonnet)
    risk_manager.py     ← Risk veto agent (Sonnet)
    fund_manager.py     ← Final decision agent (Sonnet)
    memory/
        swarm_memory.py ← RAG vector memory manager
        reflection.py   ← Post-trade reflection engine
        lessons/        ← Stored lessons and patterns

risk/
    risk_gate.py        ← Trade filter (kill switch, confidence, daily loss)
    position_sizer.py   ← Position sizing with confidence tiers
    kill_zones.py       ← Session-based trading windows

execution/
    ccxt_client.py      ← CCXT exchange connector (paper + live)
    paper_trader.py     ← Paper trading simulation

monitoring/
    dashboard/          ← React sci-fi Mission Control UI
    telegram_alerts.py  ← Telegram notifications
    price_monitor.py    ← Real-time SL/TP watcher
    watchdog.sh         ← Health check cron script
    logger.py           ← Structured trade logging

scheduler.py            ← Main bot runner
tests/                  ← All unit + integration tests
```

---

## Trading Strategy

### Confluence Engine — the gate before agents fire
Only setups scoring ≥ 7/10 reach the agent pipeline. Lower scores are discarded silently.

| Signal | Points |
|--------|--------|
| Fair Value Gap present | +2 |
| Order Block nearby | +2 |
| Inside kill zone | +2 |
| BOS confirmed | +1 |
| Judas Swing detected | +2 |
| Volume confirms | +1 |
| **Threshold to fire agents** | **≥ 7** |

### Confidence Tiers (position sizing)
| Confidence | Multiplier | Max position |
|------------|------------|-------------|
| 8.5–10.0 | 1.5× | 7.5% of capital |
| 7.5–8.4 | 1.0× | 5.0% of capital |
| 7.0–7.4 | 0.5× | 2.5% of capital |
| < 7.0 | HOLD | No trade |

### Exit Parameters (do not change without backtesting)
- Stop loss: 1.5× ATR(14)
- Take profit: 3.0× ATR(14)
- R:R ratio: 2:1

### Kill Zones (active trading windows only)
| Session | UTC | Confidence threshold |
|---------|-----|---------------------|
| London open | 07:00–09:00 | 7.0 |
| NY open | 13:30–15:00 | 7.0 |
| NY afternoon | 17:00–19:00 | 7.5 |
| Outside these | Any | No new entries |

---

## Agent Model Split

| Agents | Model | Why |
|--------|-------|-----|
| Regime Detector, Technical, Order Flow, Sentiment | claude-haiku-4-5-20251001 | Speed-critical — runs on every qualifying signal |
| Bull, Bear, Consensus, Risk, Fund Manager | claude-sonnet-4-6 | Reasoning-critical — only fires when Confluence ≥ 7 |

---

## Environment Variables

Required in `.env` (never commit this file):

```
# Exchange
EXCHANGE=binance
TRADING_MODE=paper          # paper or live — never change to live without explicit approval
PAPER_BALANCE=10000         # starting paper balance in USD

# Pairs to trade
WATCHLIST=BTC/USDT,ETH/USDT,SOL/USDT

# Anthropic
ANTHROPIC_API_KEY=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Risk parameters (do not change without backtesting)
CONFLUENCE_MIN_SCORE=7
MIN_CONFIDENCE_SCORE=7.0
MAX_POSITION_SIZE_PCT=0.05
RISK_PER_TRADE_PCT=0.01
MAX_DAILY_LOSS_PCT=0.03
ATR_SL_MULTIPLIER=1.5
ATR_TP_MULTIPLIER=3.0
MAX_TRADES_PER_SESSION=10
CORRELATION_LIMIT=0.85
```

---

## VPS & Infrastructure

- VPS IP: 204.168.254.128 (new server, separate from Fred at 46.62.165.36)
- OS: Ubuntu 24.04
- Services: `ace-bot.service` and `ace-dashboard.service` via systemd
- Auto-deploy: GitHub push triggers VPS pull and service restart
- Watchdog: `/monitoring/watchdog.sh` runs every 10 min via cron
- Dashboard port: 3000 (React) or 8503 (Streamlit fallback)

---

## GitHub

- Repo: https://github.com/jerometan9742/ACE
- Branch strategy: `main` = production, `dev` = development
- Every Claude Code prompt must end with: push to GitHub when done
- GitHub Actions: Anthropic review action runs on every PR

---

## Key Decisions Made (do not reverse without discussion)

| Decision | Reason |
|----------|--------|
| Crypto over equities | No PDT rule, 24/7, suits SGT timezone, free data |
| CCXT over broker-specific API | Exchange-agnostic, free, WebSocket support |
| Haiku for Layer 1 agents | Latency matters — intraday can't wait for Sonnet on every candle |
| Confluence Engine pre-filter | Stops weak signals reaching LLM — saves cost and improves win rate |
| Separate VPS from Fred | Isolation — Fred going down doesn't affect ACE and vice versa |
| ATR 1.5×/3.0× SL/TP | Proven in Fred's backtesting — do not change without new backtest |
| Paper trade 4 weeks minimum | Intraday slippage and spread are not visible in backtests |
| RAG vector memory | Fred's flat lessons_learned.md doesn't scale — ACE needs pattern search |
| AMD on 5m/15m not daily | FVG + BOS work on intraday charts (proven) — failed on Fred's daily charts |

---

## What Not to Build (already tested and rejected for Fred — applies to ACE too)

- Full SMC on daily charts → zero trades generated
- FVG as daily chart filter → too restrictive
- Ichimoku on daily → worse than baseline
- Dynamic TP/SL → hurts performance
- VWAP as entry trigger → not as entry trigger, bias filter only

---

## Relationship to Fred

ACE and Fred are siblings — separate repos, separate VPSes, separate Telegram chats, separate Anthropic API keys. They share:
- Same Telegram bot (different chat ID)
- Same claude-mem plugin in Claude Code
- Same reflection engine pattern
- Same ATR SL/TP parameters

They do NOT share:
- Code (no copy-paste between repos)
- VPS
- Trading capital
- Strategy logic

---

## Fred Reference

Fred (swing bot) lives at:
- VPS: 46.62.165.36
- Repo: jerome's TradingBot GitHub repo
- Strategy: Daily ADX(15) + RSI(40) + MACD + ATR 1.5x/3.0x
- Dashboard: http://46.62.165.36:8502
