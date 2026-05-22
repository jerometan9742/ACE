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
| **Session Momentum Score** | RAG memory query — weights current setup against historical patterns from similar sessions |

### Layer 4 — Supporting Technicals
| Indicator | Role |
|-----------|------|
| VWAP | Bias filter only — not entry trigger |
| RSI (14) | Divergence detection — adds +1 to Confluence Engine |
| ATR (14) | SL/TP sizing: 1.5× ATR stop, 3.0× ATR target (same as Fred, proven) |
| Volume Profile | POC and Value Area for TP placement |

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
| Consensus Builder | Ruflo-inspired supermajority logic: requires 5/7 signals to agree |
| Risk Manager | Kill zone gates, daily drawdown halt, correlation check, position limits |
| Fund Manager | Final BUY/SELL/HOLD decision + confidence score |

### Layer 3 — Memory (always running)
| Agent | Role |
|-------|------|
| Swarm Memory Manager | Vector-indexed RAG memory — retrieves similar past setups before each analysis |
| Reflection Engine | Post-trade analysis — writes structured lessons back to memory |

---

## Decision Flow (Single Trade Cycle)

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
4. If score ≥ 7 → agents fire:
   → Layer 1 agents analyse in parallel (Haiku)
   → Bull vs Bear debate
   → Consensus Builder: 5/7 required
   → Risk Manager veto check
   → Fund Manager: final decision + confidence
5. Confidence ≥ 7.0 → RiskGate checks:
   → Kill switch off?
   → Within daily loss limit?
   → Correlation check passed?
   → Position limits OK?
6a. PASS → PositionSizer → order placed via CCXT
6b. FAIL → logged, Telegram alert, no trade
7. Price monitor watches SL/TP in real time
8. Trade closes → Reflection Engine → Swarm Memory updated
```

---

## Tech Stack

| Component | Tool | Notes |
|-----------|------|-------|
| Language | Python 3.11+ | |
| AI backbone | Claude Sonnet 4.6 (decisions) + Haiku 4.5 (fast agents) | |
| Agent orchestration | LangGraph | Same as Fred/TradingAgents |
| Exchange connectivity | CCXT | Free, 100+ exchanges, WebSocket support |
| Target exchange | Binance / Bybit | Paper trading testnet first |
| Memory | ruflo-rag-memory (vector store) | Upgrade from Fred's flat lessons file |
| Dashboard | React (sci-fi Mission Control UI) | Built from day 1, not afterthought |
| Notifications | Telegram Bot API | Same bot as Fred |
| VPS | Hetzner CX22 (separate from Fred) | Ubuntu 24.04 |
| Services | systemd | Both bot + dashboard as services from day 1 |
| CI/CD | GitHub Actions + Anthropic GitHub Action | Auto-review PRs before deploy |
| Monitoring | UptimeRobot + custom watchdog | Telegram alert if anything goes down |

---

## Infrastructure

- VPS: Hetzner CX22 — separate from Fred's VPS
- Both `ace-bot.service` and `ace-dashboard.service` as systemd services from day 1
- Watchdog cron runs every 10 minutes: checks services, API credits, disk space
- Auto-deploy: GitHub push → VPS pulls and restarts services
- Anthropic billing alert set at $5 remaining (lesson from Fred)

---

## Running Costs (estimated)

| Item | Cost |
|------|------|
| Hetzner VPS (CX22) | ~$6–10/mo |
| Claude API (Haiku + Sonnet with caching) | ~$20–60/mo |
| Exchange data (CCXT WebSocket) | Free |
| Telegram, GitHub, UptimeRobot | Free |
| **Total** | **~$26–70/mo** |

---

## Plugins (Claude Code)

| Plugin | Purpose |
|--------|---------|
| claude-mem | Session memory across Claude Code sessions |
| Security Review | Catches API key exposure and credential leaks |
| Code Review | Auto-review on every code change |
| Superpowers | Spec-first discipline — ADR before any code |
| Anthropic GitHub Action | Auto-reviews PRs before deploy |
| ruflo-neural-trader | Trading-specific agent templates |
| ruflo-rag-memory | Vector memory for Swarm Memory Manager |

---

## Lessons Applied from Fred

1. Every indicator referenced in agent prompts MUST be fetched (Fred's ADX ghost filter lesson)
2. systemd services configured before first line of trading code
3. Anthropic billing alert set on day 1
4. README and CLAUDE.md written before coding starts
5. Backtest every strategy change before implementing
6. Use Haiku for speed-critical agents, Sonnet for reasoning agents
7. Paper trade minimum 4 weeks before live capital
8. Simple beats complex — start lean, add indicators only when backtested
9. All pushes end with `git push` — no local-only changes

---

## Phases

| Phase | Goal | Status |
|-------|------|--------|
| 1 | Foundation: repo, CLAUDE.md, folder structure, .env | Planned |
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

*Built with Claude (Anthropic) · CCXT · LangGraph · Ruflo*
