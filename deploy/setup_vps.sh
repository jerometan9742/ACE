#!/bin/bash
set -e

echo "Setting up ACE VPS..."

# System updates
apt-get update && apt-get upgrade -y

# Install Python 3.11
apt-get install -y python3.11 python3.11-venv \
  python3-pip git curl wget tmux \
  build-essential libssl-dev

# Install Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# Install serve for React production build
npm install -g serve

# Clone the repo
git clone https://github.com/jerometan9742/ACE.git /root/ACE
cd /root/ACE

# Create Python venv
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Build React frontend
cd monitoring/dashboard/frontend
npm install
npm run build
cd /root/ACE

# Create logs directory
mkdir -p logs
mkdir -p agents/memory/lessons

echo "Setup complete. Now copy .env and start services."
