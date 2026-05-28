#!/usr/bin/env python3
"""
ACE Weekly Performance Report
Cron: 0 1 * * 1  (Monday 01:00 UTC = 09:00 SGT)

Reads JSONL logs + lesson files, builds an HTML report, and sends to Telegram.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running from any working directory
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("weekly_report")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
LOGS_DIR    = _ROOT / "logs"
LESSONS_DIR = _ROOT / "agents" / "memory" / "lessons"
STATE_FILE  = LOGS_DIR / "weekly_state.json"

# ---------------------------------------------------------------------------
# Benchmarks (from Phase 8 Extended Backtest — backtesting/BACKTEST_EXTENDED.md)
# ---------------------------------------------------------------------------
KILL_SWITCH_WR  = 25.0   # below this → kill switch recommended
BREAKEVEN_WR    = 33.33  # 2:1 R:R breakeven threshold
GOLIVE_WR       = 38.0   # go-live gate
GOLIVE_MIN_TRADES = 30   # minimum closed trades before assessing go-live
GOLIVE_MIN_WEEKS  = 4    # consecutive positive weeks required


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _parse_ts(ts_str: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(ts_str))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _week_range() -> tuple:
    """Previous 7 days ending at yesterday 23:59:59 UTC."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end   = today - timedelta(seconds=1)
    week_start = today - timedelta(days=7)
    return week_start, week_end


def _service_status(name: str) -> str:
    try:
        r = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=5,
        )
        state = r.stdout.strip()
        return "✅ ACTIVE" if state == "active" else f"❌ {state.upper()}"
    except FileNotFoundError:
        return "⚠️ systemctl not found (local env)"
    except Exception as exc:
        return f"⚠️ {exc}"


# ---------------------------------------------------------------------------
# State persistence  (tracks cumulative positive-week count + kill triggers)
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"weeks_positive": 0, "kill_triggers": 0, "last_week_key": ""}


def _save_state(s: dict) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, indent=2))


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _trade_stats(closed: list) -> dict:
    if not closed:
        return {
            "total": 0, "wins": 0, "losses": 0, "win_rate": 0.0,
            "pnl": 0.0, "pnl_pct": 0.0,
            "longs": 0, "shorts": 0,
            "avg_win_pct": 0.0, "avg_loss_pct": 0.0,
        }
    wins   = [t for t in closed if t.get("win")]
    losses = [t for t in closed if not t.get("win")]
    longs  = [t for t in closed if t.get("action", "").upper() in ("BUY", "LONG")]
    return {
        "total":        len(closed),
        "wins":         len(wins),
        "losses":       len(losses),
        "win_rate":     len(wins) / len(closed) * 100,
        "pnl":          sum(t.get("pnl", 0.0) for t in closed),
        "pnl_pct":      sum(t.get("pnl_pct", 0.0) for t in closed),
        "longs":        len(longs),
        "shorts":       len(closed) - len(longs),
        "avg_win_pct":  (sum(t.get("pnl_pct", 0) for t in wins)   / len(wins))   if wins   else 0.0,
        "avg_loss_pct": (sum(t.get("pnl_pct", 0) for t in losses) / len(losses)) if losses else 0.0,
    }


def collect_trades(week_start: datetime, week_end: datetime) -> dict:
    all_rows = _read_jsonl(LOGS_DIR / "trades.jsonl")

    closed_all  = [r for r in all_rows if r.get("event") == "position_closed"]
    filled_all  = [r for r in all_rows if r.get("event") == "order_filled"]

    closed_week = [r for r in closed_all  if week_start <= _parse_ts(r.get("ts","")) <= week_end]
    filled_week = [r for r in filled_all  if week_start <= _parse_ts(r.get("ts","")) <= week_end]

    return {
        "week":        _trade_stats(closed_week),
        "all_time":    _trade_stats(closed_all),
        "week_placed": len(filled_week),
        "open_count":  max(0, len(filled_all) - len(closed_all)),
    }


def collect_lessons(week_start: datetime, week_end: datetime) -> list:
    if not LESSONS_DIR.exists():
        return []
    lessons = []
    for p in sorted(LESSONS_DIR.glob("lesson_*.json")):
        try:
            data = json.loads(p.read_text())
            if week_start <= _parse_ts(data.get("timestamp","")) <= week_end:
                lessons.append(data)
        except Exception:
            pass
    return lessons


def collect_errors(week_start: datetime, week_end: datetime) -> int:
    rows = _read_jsonl(LOGS_DIR / "errors.jsonl")
    return sum(1 for r in rows if week_start <= _parse_ts(r.get("ts","")) <= week_end)


# ---------------------------------------------------------------------------
# Go-live criteria
# ---------------------------------------------------------------------------

def go_live_criteria(all_time: dict, weeks_positive: int, kill_triggers: int) -> dict:
    wr    = all_time["win_rate"]
    total = all_time["total"]

    c1 = (total >= GOLIVE_MIN_TRADES) and (wr >= GOLIVE_WR)
    c2 = weeks_positive >= GOLIVE_MIN_WEEKS
    c3 = kill_triggers == 0

    return {
        "c1": c1, "c1_label": f"Win rate ≥38% over 30+ trades  [{wr:.1f}% / {total} trades]",
        "c2": c2, "c2_label": f"4 consecutive positive weeks  [{weeks_positive}/{GOLIVE_MIN_WEEKS}]",
        "c3": c3, "c3_label": f"No kill switch triggers  [{kill_triggers} total]",
        "met": int(c1) + int(c2) + int(c3),
    }


# ---------------------------------------------------------------------------
# Kill switch recommendation
# ---------------------------------------------------------------------------

def recommendation(week: dict, all_time: dict) -> str:
    total    = all_time["total"]
    wr       = all_time["win_rate"]
    week_pnl = week["pnl"]

    if total < 10:
        return "⏳ ACCUMULATING — need 10+ closed trades before assessment"
    if wr < KILL_SWITCH_WR:
        return "🛑 ACTIVATE KILL SWITCH — win rate below 25% hard threshold"
    if week_pnl < -300:
        return "🛑 ACTIVATE KILL SWITCH — weekly loss exceeds $300"
    if wr < BREAKEVEN_WR:
        return "⚠️ CAUTION — below breakeven (33%). Watch closely, do not scale"
    if wr < GOLIVE_WR:
        return "🟡 CONTINUE — paper trading on track, accumulate more data"
    return "🟢 PERFORMING — holding above go-live threshold. Maintain course"


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def _badge(wr: float) -> str:
    if wr >= GOLIVE_WR:    return "🟢"
    if wr >= BREAKEVEN_WR: return "🟡"
    if wr >= KILL_SWITCH_WR: return "🟠"
    return "🔴"


def _fmt_pnl(pnl: float) -> str:
    sign = "+" if pnl >= 0 else ""
    return f"{sign}${pnl:,.2f}"


def _fmt_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def build_report(
    week_start: datetime,
    trades: dict,
    lessons: list,
    error_count: int,
    weeks_positive: int,
    kill_triggers: int,
) -> str:
    w  = trades["week"]
    at = trades["all_time"]
    gl = go_live_criteria(at, weeks_positive, kill_triggers)
    rec = recommendation(w, at)

    period = f"{week_start.strftime('%d %b')} – {(week_start + timedelta(days=6)).strftime('%d %b %Y')}"
    ts     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"<b>🤖 ACE Weekly Report — {period}</b>",
        f"<i>{ts}</i>",
        "",
        "<b>🏥 SERVICES</b>",
        f"  ace-bot       {_service_status('ace-bot.service')}",
        f"  ace-dashboard {_service_status('ace-dashboard.service')}",
        f"  ace-frontend  {_service_status('ace-frontend.service')}",
        f"  Errors this week: {error_count}",
        "",
        "<b>📊 THIS WEEK</b>",
        f"  Placed: {trades['week_placed']}  |  Closed: {w['total']} ({w['wins']}W/{w['losses']}L)",
        f"  Long/Short: {w['longs']} / {w['shorts']}",
        f"  Win Rate: {_badge(w['win_rate'])} <b>{w['win_rate']:.1f}%</b>",
        f"  P&amp;L: <b>{_fmt_pnl(w['pnl'])}</b> ({_fmt_pct(w['pnl_pct'])})",
        f"  Avg win: {_fmt_pct(w['avg_win_pct'])}  |  Avg loss: {_fmt_pct(w['avg_loss_pct'])}",
        f"  Open positions: {trades['open_count']}",
        "",
        "<b>📈 CUMULATIVE</b>",
        f"  Total closed: {at['total']} trades  |  Win Rate: {_badge(at['win_rate'])} <b>{at['win_rate']:.1f}%</b>",
        f"  Total P&amp;L: <b>{_fmt_pnl(at['pnl'])}</b> ({_fmt_pct(at['pnl_pct'])})",
        "",
        "<b>🎯 WIN RATE BENCHMARKS</b>",
        f"  &lt;25% Kill switch  : {'✅ Safe' if at['win_rate'] >= KILL_SWITCH_WR else '❌ DANGER — activate kill switch'}",
        "  33% Breakeven     : " + ("✅ Above" if at["win_rate"] >= BREAKEVEN_WR else f"❌ {BREAKEVEN_WR - at['win_rate']:.1f}pp below"),
        "  38% Go-live gate  : " + ("✅ MET"   if at["win_rate"] >= GOLIVE_WR    else f"⬜ {GOLIVE_WR - at['win_rate']:.1f}pp to go"),
        "",
    ]

    # Lessons
    if lessons:
        lines.append("<b>📚 LESSONS THIS WEEK</b>")
        for i, lesson in enumerate(lessons[:5], 1):
            icon = "✅" if lesson.get("win") else "❌"
            pair = lesson.get("pair", "?")
            text = lesson.get("lesson", "—")[:120]
            lines.append(f"  {i}. {icon} <b>{pair}</b>: {text}")
        if len(lessons) > 5:
            lines.append(f"  … and {len(lessons) - 5} more")
    else:
        lines.append("<b>📚 LESSONS</b>")
        lines.append("  No closed trades this week — lessons pending")

    lines += [
        "",
        "<b>🚦 RECOMMENDATION</b>",
        f"  {rec}",
        "",
        f"<b>🎯 GO-LIVE CRITERIA ({gl['met']}/3)</b>",
        f"  {'☑️' if gl['c1'] else '☐'} {gl['c1_label']}",
        f"  {'☑️' if gl['c2'] else '☐'} {gl['c2_label']}",
        f"  {'☑️' if gl['c3'] else '☐'} {gl['c3_label']}",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Telegram sender  (standalone asyncio.run — safe in cron context)
# ---------------------------------------------------------------------------

async def _send_telegram(text: str) -> bool:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.getenv("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        log.warning("Telegram not configured — BOT_TOKEN or CHAT_ID missing")
        return False
    try:
        from telegram import Bot
        from telegram.error import TelegramError
        bot = Bot(token=bot_token)
        # Telegram max message length is 4096 chars; split if needed
        chunk_size = 4000
        for i in range(0, len(text), chunk_size):
            await bot.send_message(chat_id=chat_id, text=text[i:i+chunk_size], parse_mode="HTML")
        return True
    except Exception as exc:
        log.error("Telegram send failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    week_start, week_end = _week_range()
    week_key = week_start.strftime("%Y-W%W")

    log.info("Weekly report — period %s to %s", week_start.date(), week_end.date())

    # Collect
    trades      = collect_trades(week_start, week_end)
    lessons     = collect_lessons(week_start, week_end)
    error_count = collect_errors(week_start, week_end)

    # Update state (count positive weeks — only once per week_key)
    state = _load_state()
    if state["last_week_key"] != week_key:
        if trades["week"]["pnl"] > 0:
            state["weeks_positive"] += 1
        state["last_week_key"] = week_key
        _save_state(state)

    # Build report
    report = build_report(
        week_start     = week_start,
        trades         = trades,
        lessons        = lessons,
        error_count    = error_count,
        weeks_positive = state["weeks_positive"],
        kill_triggers  = state["kill_triggers"],
    )

    log.info("Report built (%d chars)", len(report))
    print("\n" + report + "\n")

    # Send
    sent = asyncio.run(_send_telegram(report))
    if sent:
        log.info("Report delivered to Telegram")
    else:
        log.error("Telegram delivery failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
