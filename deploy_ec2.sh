#!/bin/bash
set -e

# AlphaQuant Automated EC2 Deployment & Setup Script
# Run this on a clean Ubuntu 22.04 / 24.04 LTS AWS EC2 instance

echo "================================================"
echo "    AlphaQuant Automated Server Provisioning    "
echo "================================================"

# 1. Update system packages
echo "Updating packages..."
sudo apt update && sudo apt upgrade -y

# 2. Install essential dependencies
echo "Installing system tools & Nginx..."
sudo apt install -y python3-pip python3-venv git nginx certbot python3-certbot-nginx curl ufw

# 3. Setup firewall
echo "Configuring firewall..."
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

# 4. Clone or pull repo
INSTALL_DIR="/home/ubuntu/AlphaQuantScanner"
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Cloning repository..."
    git clone https://github.com/rahulnnn77/AlphaQuantScanner.git "$INSTALL_DIR"
else
    echo "Updating existing repository..."
    cd "$INSTALL_DIR" && git pull origin main
fi

cd "$INSTALL_DIR"

# 5. Setup Python Virtual Environment
echo "Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

# 6. Setup Systemd Service for 24/7 background persistence
echo "Configuring systemd service..."
sudo bash -c "cat <<EOF > /etc/systemd/system/alphaquant.service
[Unit]
Description=AlphaQuant Indian Equity Screener & Alert Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$INSTALL_DIR/backend
ExecStart=$INSTALL_DIR/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080 --workers 2
Restart=always
RestartSec=5
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable alphaquant
sudo systemctl restart alphaquant

echo "================================================"
echo "AlphaQuant backend service is running on port 8080!"
echo "Now configure Nginx reverse proxy and SSL certificate."
echo "================================================"
