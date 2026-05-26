#!/bin/bash
set -e
cd /root/ACE

# Copy service files
cp deploy/ace-bot.service /etc/systemd/system/
cp deploy/ace-dashboard.service /etc/systemd/system/
cp deploy/ace-frontend.service /etc/systemd/system/

# Make watchdog executable
chmod +x monitoring/watchdog.sh

# Reload systemd
systemctl daemon-reload

# Enable all services (start on boot)
systemctl enable ace-bot.service
systemctl enable ace-dashboard.service
systemctl enable ace-frontend.service

# Start all services
systemctl start ace-bot.service
systemctl start ace-dashboard.service
systemctl start ace-frontend.service

# Add watchdog to cron (every 10 min)
(crontab -l 2>/dev/null; echo "*/10 * * * * /root/ACE/monitoring/watchdog.sh >> /root/ACE/logs/watchdog.log 2>&1") | crontab -

# Install logrotate config
cp /root/ACE/deploy/logrotate_ace /etc/logrotate.d/ace

# Install tmux for manual sessions
apt-get install -y tmux

echo "All services installed and running."
systemctl status ace-bot.service --no-pager
systemctl status ace-dashboard.service --no-pager
systemctl status ace-frontend.service --no-pager
