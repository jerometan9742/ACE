"""Telegram notification layer — all outbound alerts and inbound command handling for ACE."""

import os
import asyncio
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TRADING_MODE = os.getenv("TRADING_MODE", "paper")
WATCHLIST = os.getenv("WATCHLIST", "BTC/USDT,ETH/USDT,SOL/USDT")
PAPER_BALANCE = os.getenv("PAPER_BALANCE", "10000")

logger = logging.getLogger(__name__)

_kill_switch_active = False


# ---------------------------------------------------------------------------
# Core sender
# ---------------------------------------------------------------------------

async def send_message(text: str) -> bool:
    """Send a plain-text message to the configured chat; returns True on success."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram not configured — BOT_TOKEN or CHAT_ID missing")
        return False
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")
        return True
    except TelegramError as e:
        logger.error("Telegram send failed: %s", e)
        return False


def _send(text: str) -> bool:
    """Synchronous wrapper — works in both async and non-async contexts.

    Uses get_running_loop() (not get_event_loop()) to detect context safely on
    Python 3.10+, where get_event_loop() raises when there is no current loop.
    """
    try:
        loop = asyncio.get_running_loop()
        # Inside a running event loop (e.g. called from a WebSocket callback):
        # schedule as a fire-and-forget task and return immediately.
        loop.create_task(send_message(text))
        return True
    except RuntimeError:
        # No running loop — pure sync context (startup, cron, post-shutdown).
        try:
            return asyncio.run(send_message(text))
        except Exception as e:
            logger.error("Telegram sync send failed: %s", e)
            return False


# ---------------------------------------------------------------------------
# Alert functions
# ---------------------------------------------------------------------------

def send_startup_alert() -> bool:
    text = (
        "<b>ACE Online — Intraday Bot v1.0</b>\n"
        f"Mode: <code>{TRADING_MODE.upper()}</code>\n"
        f"Pairs: {WATCHLIST}\n"
        f"Paper balance: ${PAPER_BALANCE}\n"
        "Systems operational"
    )
    return _send(text)


def send_trade_alert(
    pair: str,
    action: str,
    quantity: float,
    price: float,
    confidence: float,
    sl: float,
    tp: float,
    confluence_score: float,
) -> bool:
    action_upper = action.upper()
    if action_upper == "HOLD":
        text = f"<b>HOLD {pair}</b>"
        return _send(text)

    emoji = "" if action_upper == "BUY" else ""
    text = (
        f"{emoji} <b>{action_upper} {pair}</b>\n"
        f"{quantity} @ ${price:,.2f}\n"
        f"Conf: {confidence}/10  Confluence: {confluence_score}/10\n"
        f"SL: ${sl:,.2f}  TP: ${tp:,.2f}"
    )
    return _send(text)


def send_hold_alert(pair: str, reason: str) -> bool:
    text = f"<b>HOLD {pair}</b> — {reason}"
    return _send(text)


def send_trade_closed(
    pair: str,
    action: str,
    entry: float,
    exit_price: float,
    pnl: float,
    pnl_pct: float,
    reason: str,
) -> bool:
    outcome = "WIN" if pnl >= 0 else "LOSS"
    sign = "+" if pnl >= 0 else ""
    emoji = "" if outcome == "WIN" else ""
    text = (
        f"{emoji} <b>CLOSED {pair} — {outcome}</b>\n"
        f"Entry ${entry:,.2f} → Exit ${exit_price:,.2f}\n"
        f"P&amp;L: {sign}${pnl:,.2f} ({sign}{pnl_pct:.2f}%)\n"
        f"Exit: {reason}"
    )
    return _send(text)


def send_daily_summary(
    date: str,
    total_pnl: float,
    win_rate: float,
    trades: int,
    best_trade: str,
    worst_trade: str,
) -> bool:
    sign = "+" if total_pnl >= 0 else ""
    text = (
        f"<b>Daily Summary — {date}</b>\n"
        f"P&amp;L: {sign}${total_pnl:,.2f}\n"
        f"Win rate: {win_rate:.1f}% ({trades} trades)\n"
        f"Best: {best_trade}\n"
        f"Worst: {worst_trade}"
    )
    return _send(text)


def send_error_alert(error_type: str, message: str) -> bool:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        f"<b>ERROR — {error_type}</b>\n"
        f"{message}\n"
        f"Time: {timestamp}"
    )
    return _send(text)


def send_credit_warning(remaining: float) -> bool:
    text = (
        "<b>Anthropic Credits Low</b>\n"
        f"Remaining: ${remaining:.2f}\n"
        "Top up: console.anthropic.com/settings/billing\n"
        "Bot defaulting to HOLD until resolved"
    )
    return _send(text)


def send_watchdog_alert(service: str, action: str) -> bool:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    text = (
        f"<b>WATCHDOG — {service}</b>\n"
        f"{action}\n"
        f"Time: {timestamp}"
    )
    return _send(text)


# ---------------------------------------------------------------------------
# Telegram /commands
# ---------------------------------------------------------------------------

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return bot status, mode, and open positions."""
    from risk.risk_gate import is_kill_switch_active as _ks
    status = "FULLY PAUSED (signal evaluation stopped)" if _ks() else "RUNNING"
    text = (
        f"<b>ACE Status</b>\n"
        f"Status: {status}\n"
        f"Mode: {TRADING_MODE.upper()}\n"
        f"Pairs: {WATCHLIST}\n"
        "Open positions: (not yet implemented — Phase 5)"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_pnl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return today's P&L summary."""
    await update.message.reply_text(
        "<b>Today's P&amp;L</b>\nP&amp;L tracking not yet implemented — Phase 5.",
        parse_mode="HTML",
    )


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Activate full pause — halt all signal evaluation, keep price monitor and dashboard alive."""
    from risk.risk_gate import activate_kill_switch as _activate
    _activate("manual_pause")
    await update.message.reply_text(
        "⏸️ ACE FULLY PAUSED — all chart evaluation and signal processing stopped. "
        "Existing open positions (if any) still monitored for SL/TP. "
        "Dashboard and bot commands remain active. Resume with /resume.",
    )


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove kill_switch.lock — resume signal evaluation and trading."""
    from risk.risk_gate import deactivate_kill_switch as _deactivate
    _deactivate()
    await update.message.reply_text(
        "<b>ACE RESUMED</b> — signal evaluation and trading restored.",
        parse_mode="HTML",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all available commands."""
    text = (
        "<b>ACE Commands</b>\n"
        "/status  — bot status, mode, open positions\n"
        "/pnl     — today's P&amp;L summary\n"
        "/pause   — activate kill switch (stops new trades)\n"
        "/resume  — deactivate kill switch\n"
        "/help    — this message"
    )
    await update.message.reply_text(text, parse_mode="HTML")


def is_kill_switch_active() -> bool:
    """Return kill switch state from lock file — survives restarts."""
    from risk.risk_gate import is_kill_switch_active as _ks
    return _ks()


def build_application() -> Application:
    """Build and return the Telegram Application with all command handlers registered."""
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("pnl", cmd_pnl))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("help", cmd_help))
    return app


if __name__ == "__main__":
    send_startup_alert()
    if BOT_TOKEN:
        build_application().run_polling()
