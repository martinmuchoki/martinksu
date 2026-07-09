#!/bin/bash
cd /root/nse_signal_bot_v10_3
source venv/bin/activate
python -m py_compile app.py services/*.py || exit 1
sudo systemctl restart nse-v10-3
sleep 2
curl http://127.0.0.1:5000/health
