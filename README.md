# ACE — AI Intraday Trading Bot

> Autonomous intraday crypto trading system powered by Claude (Anthropic), a 10-agent pipeline, and a proprietary confluence-based signal engine.

---

## What ACE Does

ACE is an intraday trading bot that trades crypto (BTC, ETH, SOL) on 1m/5m/15m timeframes using a layered strategy combining ICT/SMC concepts with custom-built signal scoring. It runs 24/7 on a VPS, monitors multiple pairs simultaneously via WebSocket streams, and uses a team of 10 specialised AI agents to debate and decide every trade.

ACE is the evolution of Fred (swing trading bot). Where Fred trades once or twice per day on daily charts, ACE trades 10–30 times per day on intraday charts using a completely different edge.

---

## Strategy Stack

### Layer 1 — Market Structure (AMD + SMC)
| Concept | Role |
|---------|------|
| AMD (Accumulation → Manipulation → Distribution) | Primary framework — identifies which phase price is in |
| Break of Structure (BOS) | Confirms institutional momentum direction |
| Change of Character (CHoCH) | Flags potential reversals |
| Fair Value Gaps (FVG) | Precise entry zones — unmitigated gaps price returns to fill |
| Order Blocks (OB) | Institutional support/resistance zones — entry and TP targets |

### Layer 2 — ICT Kill Zones (when to trade)
| Session | UTC Time | Role |
|---------|----------|------|
| Asia | 00:00–04:00 | Accumulation mapping — minimal trading |
| London open | 07:00–09:00 | Manipulation kill zone — fade Judas swings |
| NY open | 13:30–15:00 | Primary trading window — highest volume, best R:R |
| NY afternoon | 17:00–19:00 | Secondary window — confidence threshold raised to 7.5 |

### Layer 3 — Custom ACE Indicators
| Indicator | What It Does |
|-----------|-------------|
| **Judas Swing Detector** | Detects manipulation candle: range break on low volume that closes back inside within 1–3 candles |
| **Liquidity Sweep Score (0–10)** | Scores quality of a liquidity grab: equal H/L count, reversal speed, volume spike, OB proximity |
| **Confluence Engine (0–10)** | Pre-scores each setup before agents see it: FVG(+2) + OB(+2) + Kill Zone(+2) + BOS(+1) + Judas(+2) + Volume(+1). Score ≥ 7 required |
| **Multi-Pair Correlation Filter** | Requires BTC + ETH agreement; reduces position size if correlation > 0.85 to avoid double exposure |

### Layer 4 — Supporting Technicals
| Indicator | Role |
|-----------|------|
| VWAP | Bias filter only — not entry trigger |
| RSI (14) | Divergence detection |
| ATR (14) | SL/TP sizing: 1.5× ATR stop, 3.0× ATR target |

---

## Agent Pipeline

### Layer 1 — Fast Signal Agents (Claude Haiku — speed-critical)
| Agent | Role |
|-------|------|
| Regime Detector | Identifies current AMD phase in real time |
| Technical Analyst | Multi-timeframe signals: FVG, OB, BOS/CHoCH, VWAP |
| Order Flow Analyst | Live order book depth, buy/sell pressure, iceberg detection |
| Sentiment Pulse | Crypto Fear & Greed, social sentiment — runs every 30 min |

### Layer 2 — Decision Agents (Claude Sonnet — fires when Confluence ≥ 7)
| Agent | Role |
|-------|------|
| Bull Researcher | Argues bullish case with AMD phase context |
| Bear Researcher | Argues bearish case — debates Bull |
| Consensus Builder | Supermajority logic: requires 5/7 signals to agree |
| Risk Manager | Kill zone gates, daily drawdown halt, correlation check, position limits |
| Fund Manager | Final BUY/SELL/HOLD decision + confidence score |

### Layer 3 — Memory (always running)
| Agent | Role |
|-------|------|
| Swarm Memory Manager | Vector-indexed RAG memory — retrieves similar past setups before each analysis |
| Reflection Engine | Post-trade analysis — writes structured lessons back to memory |

---

## Decision Flow

```
1. WebSocket stream: new candle closes on 1m/5m/15m
2. Signal Engine (Python — fast, no LLM):
   → AMD phase detection
   → BOS / CHoCH check
   → FVG zone detection
   → Order Block identification
   → Judas Swing Detector
   → Confluence Engine scores setup 0–10
3. If score < 7 → discard silently (no agents fired)
4. If score ≥ 7 → agents fire in parallel
5. Consensus Builder: 5/7 required
6. Risk Manager veto check
7. Fund Manager: final decision + confidence
8. Confidence ≥ 7.0 → RiskGate → PositionSizer → order via CCXT
9. Price monitor watches SL/TP in real time
10. Trade closes → Reflection Engine → Swarm Memory updated
```

---

## Tech Stack

| Component | Tool |
|-----------|------|
| Language | Python 3.11+ |
| AI backbone | Claude Sonnet 4.6 (decisions) + Haiku 4.5 (fast agents) |
| Agent orchestration | LangGraph |
| Exchange connectivity | CCXT |
| Target exchange | Binance (paper testnet first) |
| Memory | ChromaDB vector store |
| Dashboard | React (sci-fi Mission Control UI) |
| Notifications | Telegram Bot API |
| VPS | Hetzner CX22 — Ubuntu 24.04 |
| Services | systemd |
| CI/CD | GitHub Actions + Anthropic GitHub Action |
| Monitoring | UptimeRobot + custom watchdog |

---

## Quickstart

```bash
# 1. Clone and install dependencies
git clone <repo-url>
cd ACE
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in your keys in .env

# 3. Run tests
pytest tests/ -v

# 4. Start the bot (paper mode)
python scheduler.py
```

---

## Phases

| Phase | Goal | Status |
|-------|------|--------|
| 1 | Foundation: repo, folder structure, Telegram, watchdog | ✅ Done |
| 2 | Signal Engine: WebSocket + AMD + FVG + Confluence Engine | Planned |
| 3 | Agent Pipeline: all 10 agents wired | Planned |
| 4 | Risk Layer: RiskGate + PositionSizer + kill zones | Planned |
| 5 | Execution: paper trading via Binance testnet | Planned |
| 6 | Dashboard: sci-fi Mission Control React app | Planned |
| 7 | Infrastructure: systemd, watchdog, GitHub Actions | Planned |
| 8 | Backtesting: historical validation of full strategy | Planned |
| 9 | Paper trading: 4 weeks minimum | Planned |
| 10 | Live trading: real capital, small allocation first | Planned |

---

*Built with Claude (Anthropic) · CCXT · LangGraph · ChromaDB*
