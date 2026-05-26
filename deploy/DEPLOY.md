# ACE — VPS Deployment Guide

> Deploy ACE to a fresh Ubuntu 24.04 VPS.
> VPS: 204.168.254.128 (separate from Fred at 46.62.165.36 — never touch that server)

---

## Prerequisites

- Fresh Ubuntu 24.04 VPS (Hetzner CX22 recommended)
- SSH access as root
- GitHub repo: https://github.com/jerometan9742/ACE
- Your `.env` file ready locally
- GitHub secrets configured (see Step 7)

---

## Step 1 — SSH into the VPS

```bash
ssh root@204.168.254.128
```

---

## Step 2 — Run the setup script

This installs Python 3.11, Node 20, clones the repo, builds the frontend, and creates the venv.

```bash
bash <(curl -s https://raw.githubusercontent.com/jerometan9742/ACE/main/deploy/setup_vps.sh)
```

Expected output: `Setup complete. Now copy .env and start services.`

---

## Step 3 — Copy your .env file

From your **local machine** (not the VPS):

```bash
scp .env root@204.168.254.128:/root/ACE/.env
```

Verify it landed:

```bash
# On VPS:
ls -la /root/ACE/.env
```

**Never commit .env to GitHub.**

---

## Step 4 — Install and start services

```bash
bash /root/ACE/deploy/install_services.sh
```

This will:
- Copy systemd service files to `/etc/systemd/system/`
- Enable all 3 services (start on boot)
- Start all 3 services immediately
- Add watchdog to cron (every 10 min)
- Install logrotate config

---

## Step 5 — Add logrotate config

Already done by `install_services.sh`. To verify:

```bash
cat /etc/logrotate.d/ace
```

---

## Step 6 — Verify everything is running

```bash
systemctl status ace-bot.service --no-pager
systemctl status ace-dashboard.service --no-pager
systemctl status ace-frontend.service --no-pager
```

All three should show `active (running)`.

Check logs:

```bash
journalctl -u ace-bot.service -f
journalctl -u ace-dashboard.service -f
```

Open dashboard in browser:

```
http://204.168.254.128:3000
```

---

## Step 7 — Add GitHub Secrets

Go to: https://github.com/jerometan9742/ACE/settings/secrets/actions

Add these secrets:

| Secret | Value |
|--------|-------|
| `VPS_IP` | `204.168.254.128` |
| `VPS_SSH_KEY` | Contents of `/root/.ssh/id_rsa` (VPS private key) |
| `ANTHROPIC_API_KEY` | Your Anthropic API key (for PR review action) |

To generate a deploy key on the VPS:

```bash
ssh-keygen -t ed25519 -C "ace-deploy" -f /root/.ssh/ace_deploy -N ""
cat /root/.ssh/ace_deploy.pub >> /root/.ssh/authorized_keys
cat /root/.ssh/ace_deploy  # copy this as VPS_SSH_KEY secret
```

---

## Step 8 — Test auto-deploy

Push any commit to `main` on GitHub. Watch the Actions tab:
https://github.com/jerometan9742/ACE/actions

The deploy workflow should SSH in and run `deploy/auto_deploy.sh`.

---

## Step 9 — Set up UptimeRobot (optional but recommended)

1. Go to https://uptimerobot.com and create a free account
2. Add a new monitor: HTTP(s) → `http://204.168.254.128:3000`
3. Add a heartbeat monitor and copy the URL
4. Add `UPTIMEROBOT_URL=<your-heartbeat-url>` to `.env`

---

## Useful Commands

```bash
# View live bot logs
journalctl -u ace-bot.service -f

# View dashboard logs
journalctl -u ace-dashboard.service -f

# Restart a service
systemctl restart ace-bot.service

# Check watchdog log
tail -f /root/ACE/logs/watchdog.log

# Run watchdog manually
bash /root/ACE/monitoring/watchdog.sh

# Manual tmux session (for debugging)
tmux new -s ace
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Service won't start | `journalctl -u ace-bot.service -n 50` — check for import errors |
| Dashboard not loading on :3000 | Check `ace-frontend.service` and that `dist/` exists |
| API returns 401 | Check `ANTHROPIC_API_KEY` in `.env` |
| Bot not trading | Check `TRADING_MODE=paper` and kill switch status in dashboard |
| Auto-deploy fails | Check GitHub Actions secrets are set correctly |

---

## Important: Never Do These

- Never edit `.env` directly on VPS — push from local, let auto-deploy handle it
- Never touch Fred's VPS at 46.62.165.36
- Never run `systemctl stop ace-bot ace-dashboard` simultaneously
- Never switch `TRADING_MODE=live` without explicit confirmation
