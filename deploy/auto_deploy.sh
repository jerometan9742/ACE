#!/bin/bash
set -e
cd /root/ACE

echo "[$(date)] Auto-deploy started"

# Pull latest code
git pull origin main

# Activate venv and update dependencies
source venv/bin/activate
pip install -r requirements.txt --quiet

# Rebuild React frontend
cd monitoring/dashboard/frontend
npm install --quiet
npm run build
cd /root/ACE

# Restart services
systemctl restart ace-bot.service
systemctl restart ace-dashboard.service
systemctl restart ace-frontend.service

echo "[$(date)] Auto-deploy complete"
