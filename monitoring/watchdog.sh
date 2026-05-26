#!/usr/bin/env bash
# Watchdog for ACE — runs every 10 minutes via cron.
# Checks services, API credits, disk/memory usage, and sends UptimeRobot heartbeat.
#
# Crontab entry:
#   */10 * * * * /root/ACE/monitoring/watchdog.sh >> /root/ACE/logs/watchdog.log 2>&1

set -euo pipefail

# ---------------------------------------------------------------------------
# Config — load from project .env
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$(dirname "$SCRIPT_DIR")/.env"

if [[ -f "$ENV_FILE" ]]; then
    # Export only the vars we need, ignore comments and blank lines
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        export "$key"="${value}"
    done < <(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$')
fi

BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT_ID="${TELEGRAM_CHAT_ID:-}"
UPTIMEROBOT_URL="${UPTIMEROBOT_URL:-}"
TIMESTAMP="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# ---------------------------------------------------------------------------
# Helper: send Telegram message (curl-based, no Python dependency)
# ---------------------------------------------------------------------------
send_telegram() {
    local message="$1"
    if [[ -z "$BOT_TOKEN" || -z "$CHAT_ID" ]]; then
        echo "[$TIMESTAMP] WARNING: Telegram not configured"
        return
    fi
    curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${CHAT_ID}" \
        --data-urlencode "text=${message}" \
        --data-urlencode "parse_mode=HTML" \
        -o /dev/null || echo "[$TIMESTAMP] WARNING: Telegram send failed"
}

echo "[$TIMESTAMP] Watchdog starting"

# ---------------------------------------------------------------------------
# Check 1: ace-bot.service
# ---------------------------------------------------------------------------
if ! systemctl is-active --quiet ace-bot.service; then
    echo "[$TIMESTAMP] ALERT: ace-bot.service is down — restarting"
    systemctl restart ace-bot.service
    sleep 5
    if systemctl is-active --quiet ace-bot.service; then
        send_telegram "<b>WATCHDOG — ace-bot.service</b>
Service was down and has been restarted successfully.
Time: ${TIMESTAMP}"
        echo "[$TIMESTAMP] ace-bot.service restarted OK"
    else
        send_telegram "<b>WATCHDOG — ace-bot.service FAILED TO RESTART</b>
Manual intervention required.
Time: ${TIMESTAMP}"
        echo "[$TIMESTAMP] ERROR: ace-bot.service failed to restart"
    fi
else
    echo "[$TIMESTAMP] ace-bot.service OK"
fi

# ---------------------------------------------------------------------------
# Check 2: ace-dashboard.service
# ---------------------------------------------------------------------------
if ! systemctl is-active --quiet ace-dashboard.service; then
    echo "[$TIMESTAMP] ALERT: ace-dashboard.service is down — restarting"
    systemctl restart ace-dashboard.service
    sleep 5
    if systemctl is-active --quiet ace-dashboard.service; then
        send_telegram "<b>WATCHDOG — ace-dashboard.service</b>
Service was down and has been restarted successfully.
Time: ${TIMESTAMP}"
        echo "[$TIMESTAMP] ace-dashboard.service restarted OK"
    else
        send_telegram "<b>WATCHDOG — ace-dashboard.service FAILED TO RESTART</b>
Manual intervention required.
Time: ${TIMESTAMP}"
        echo "[$TIMESTAMP] ERROR: ace-dashboard.service failed to restart"
    fi
else
    echo "[$TIMESTAMP] ace-dashboard.service OK"
fi

# ---------------------------------------------------------------------------
# Check 3: ace-frontend.service
# ---------------------------------------------------------------------------
if ! systemctl is-active --quiet ace-frontend.service; then
    echo "[$TIMESTAMP] ALERT: ace-frontend.service is down — restarting"
    systemctl restart ace-frontend.service
    sleep 5
    if systemctl is-active --quiet ace-frontend.service; then
        send_telegram "<b>WATCHDOG — ace-frontend.service</b>
Service was down and has been restarted successfully.
Time: ${TIMESTAMP}"
        echo "[$TIMESTAMP] ace-frontend.service restarted OK"
    else
        send_telegram "<b>WATCHDOG — ace-frontend.service FAILED TO RESTART</b>
Manual intervention required.
Time: ${TIMESTAMP}"
        echo "[$TIMESTAMP] ERROR: ace-frontend.service failed to restart"
    fi
else
    echo "[$TIMESTAMP] ace-frontend.service OK"
fi

# ---------------------------------------------------------------------------
# Check 4: Anthropic API credits — test call, alert on credit/auth error
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
if [[ -n "$ANTHROPIC_API_KEY" ]]; then
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST "https://api.anthropic.com/v1/messages" \
        -H "x-api-key: ${ANTHROPIC_API_KEY}" \
        -H "anthropic-version: 2023-06-01" \
        -H "content-type: application/json" \
        --data '{"model":"claude-haiku-4-5-20251001","max_tokens":1,"messages":[{"role":"user","content":"ping"}]}')

    if [[ "$HTTP_STATUS" == "402" ]]; then
        send_telegram "<b>Anthropic Credits Exhausted</b>
API returned 402 Payment Required.
Top up: console.anthropic.com/settings/billing
Bot defaulting to HOLD until resolved.
Time: ${TIMESTAMP}"
        echo "[$TIMESTAMP] ALERT: Anthropic credits exhausted (HTTP 402)"
    elif [[ "$HTTP_STATUS" == "401" ]]; then
        send_telegram "<b>Anthropic API Key Invalid</b>
API returned 401 Unauthorized.
Check ANTHROPIC_API_KEY in .env
Time: ${TIMESTAMP}"
        echo "[$TIMESTAMP] ALERT: Anthropic API key invalid (HTTP 401)"
    elif [[ "$HTTP_STATUS" == "200" || "$HTTP_STATUS" == "400" ]]; then
        # 400 means the request was understood (bad payload is fine for a ping)
        echo "[$TIMESTAMP] Anthropic API OK (HTTP $HTTP_STATUS)"
    else
        echo "[$TIMESTAMP] WARNING: Anthropic API returned HTTP $HTTP_STATUS"
    fi
else
    echo "[$TIMESTAMP] WARNING: ANTHROPIC_API_KEY not set — skipping credit check"
fi

# ---------------------------------------------------------------------------
# Check 5: Disk usage > 80%
# ---------------------------------------------------------------------------
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
if [[ "$DISK_USAGE" -gt 80 ]]; then
    send_telegram "<b>WATCHDOG — Disk Usage High</b>
Root partition at ${DISK_USAGE}% — consider cleaning logs.
Time: ${TIMESTAMP}"
    echo "[$TIMESTAMP] ALERT: disk usage at ${DISK_USAGE}%"
else
    echo "[$TIMESTAMP] Disk usage OK (${DISK_USAGE}%)"
fi

# ---------------------------------------------------------------------------
# Check 6: Memory usage > 85%
# ---------------------------------------------------------------------------
MEM_TOTAL=$(grep MemTotal /proc/meminfo | awk '{print $2}')
MEM_AVAILABLE=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
MEM_USED=$(( MEM_TOTAL - MEM_AVAILABLE ))
MEM_PCT=$(( MEM_USED * 100 / MEM_TOTAL ))

if [[ "$MEM_PCT" -gt 85 ]]; then
    send_telegram "<b>WATCHDOG — Memory Usage High</b>
RAM at ${MEM_PCT}% (${MEM_USED}kB / ${MEM_TOTAL}kB used).
Consider restarting services or adding swap.
Time: ${TIMESTAMP}"
    echo "[$TIMESTAMP] ALERT: memory usage at ${MEM_PCT}%"
else
    echo "[$TIMESTAMP] Memory usage OK (${MEM_PCT}%)"
fi

# ---------------------------------------------------------------------------
# Check 7: UptimeRobot heartbeat ping
# ---------------------------------------------------------------------------
if [[ -n "$UPTIMEROBOT_URL" ]]; then
    curl -s "$UPTIMEROBOT_URL" -o /dev/null \
        && echo "[$TIMESTAMP] UptimeRobot heartbeat sent" \
        || echo "[$TIMESTAMP] WARNING: UptimeRobot heartbeat failed"
else
    echo "[$TIMESTAMP] WARNING: UPTIMEROBOT_URL not set — skipping heartbeat"
fi

echo "[$TIMESTAMP] Watchdog complete"
