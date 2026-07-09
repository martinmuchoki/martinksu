#!/bin/bash
echo "=== Service Status ==="
sudo systemctl status nse-v10-3 --no-pager -l

echo ""
echo "=== Health Check ==="
curl http://127.0.0.1:5000/health

echo ""
echo "=== Public Check ==="
curl http://164.92.133.0/health
