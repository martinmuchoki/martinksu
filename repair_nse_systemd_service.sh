#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE_NAME="nse-v10-3.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"
PROJECT_DIR="/root/nse_signal_bot_v10_3"
BACKUP_FILE="${SERVICE_FILE}.backup.$(date +%Y%m%d_%H%M%S)"

restore_service() {
    echo
    echo "Repair failed. Restoring $BACKUP_FILE ..."

    sudo cp "$BACKUP_FILE" "$SERVICE_FILE"
    sudo systemctl daemon-reload
    sudo systemctl restart "$SERVICE_NAME" || true
    sudo systemctl status "$SERVICE_NAME" --no-pager -l || true
}

trap restore_service ERR

echo "======================================================"
echo "Repairing $SERVICE_NAME"
echo "======================================================"

echo
echo "Creating backup:"
echo "$BACKUP_FILE"

sudo cp "$SERVICE_FILE" "$BACKUP_FILE"

sudo tee "$SERVICE_FILE" >/dev/null <<'UNIT'
[Unit]
Description=NSE Signal Bot V10.3 Enterprise
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/nse_signal_bot_v10_3
Environment="PATH=/root/nse_signal_bot_v10_3/venv/bin"
ExecStart=/root/nse_signal_bot_v10_3/venv/bin/gunicorn --workers 2 --bind 127.0.0.1:5000 --access-logfile - --error-logfile - --capture-output --log-level info app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

echo
echo "New unit file:"
sudo nl -ba "$SERVICE_FILE"

echo
echo "Validating systemd unit..."

VERIFY_OUTPUT="$(
    sudo systemd-analyze verify "$SERVICE_FILE" 2>&1
)" || {
    echo "$VERIFY_OUTPUT"
    exit 1
}

if [[ -n "$VERIFY_OUTPUT" ]]; then
    echo "$VERIFY_OUTPUT"
else
    echo "PASS: systemd unit syntax is valid."
fi

echo
echo "Reloading systemd..."
sudo systemctl daemon-reload

echo
echo "Restarting service..."
sudo systemctl restart "$SERVICE_NAME"
sleep 3

sudo systemctl is-active --quiet "$SERVICE_NAME"
echo "PASS: service is active."

echo
echo "Testing health endpoint..."

curl \
    --fail \
    --silent \
    --show-error \
    --max-time 30 \
    http://127.0.0.1:5000/health

echo
echo
echo "Checking unit status..."
sudo systemctl status "$SERVICE_NAME" \
    --no-pager \
    -l \
    --lines=20

echo
echo "Checking warnings since this restart..."

ACTIVE_TIME="$(
    systemctl show "$SERVICE_NAME" \
        --property=ActiveEnterTimestamp \
        --value
)"

sudo journalctl \
    -u "$SERVICE_NAME" \
    --since "$ACTIVE_TIME" \
    --priority=warning \
    --no-pager || true

echo
echo "======================================================"
echo "Systemd service repair completed successfully"
echo "======================================================"
echo "Backup retained at:"
echo "$BACKUP_FILE"
