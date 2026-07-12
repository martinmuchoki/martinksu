#!/bin/bash

cd ~/nse_signal_bot_v10_3

source venv/bin/activate

python run_history_collector.py

./restart.sh
