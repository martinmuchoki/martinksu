#!/bin/bash

CRON_TMP=$(mktemp)

# Export current cron (ignore error if none exists)
crontab -l 2>/dev/null > "$CRON_TMP"

# Remove old daily scan entry
sed -i '/run_daily_scan.py/d' "$CRON_TMP"

# Remove old daily update entry
sed -i '/daily_update.sh/d' "$CRON_TMP"

# Add the updated jobs
cat >> "$CRON_TMP" <<CRON

# NSE Signal Bot Daily History Collection
10 15 * * 1-5 /root/nse_signal_bot_v10_3/daily_update.sh >> /root/nse_signal_bot_v10_3/logs/daily_update.log 2>&1

# NSE Signal Bot Daily AI Scan
20 15 * * 1-5 cd /root/nse_signal_bot_v10_3 && /root/nse_signal_bot_v10_3/venv/bin/python /root/nse_signal_bot_v10_3/run_daily_scan.py >> /root/nse_signal_bot_v10_3/logs/daily_scan.log 2>&1

# Weekly Company Synchronization
0 6 * * 0 cd /root/nse_signal_bot_v10_3 && /root/nse_signal_bot_v10_3/venv/bin/python /root/nse_signal_bot_v10_3/run_company_sync.py >> /root/nse_signal_bot_v10_3/logs/company_sync.log 2>&1
CRON

# Install new crontab
crontab "$CRON_TMP"

rm "$CRON_TMP"

echo
echo "======================================"
echo "Cron jobs updated successfully."
echo "======================================"
crontab -l
