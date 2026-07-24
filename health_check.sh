#!/bin/bash
set +e

echo "=========================================="
echo "  NSE SIGNAL BOT ENTERPRISE HEALTH CHECK"
echo "=========================================="

echo
echo "[1/10] Python Syntax"
python3 -m py_compile app.py && echo "✓ app.py OK" || echo "✗ app.py FAILED"

echo
echo "[2/10] Services Syntax"
find services -name "*.py" -print0 | while IFS= read -r -d '' file
do
    python3 -m py_compile "$file" >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✓ $file"
    else
        echo "✗ $file"
    fi
done

echo
echo "[3/10] Templates"
find templates -name "*.html"

echo
echo "[4/10] Portfolio KPI"
if [ -f templates/_portfolio_kpis.html ]; then
    echo "✓ Portfolio KPI template exists"
else
    echo "✗ Portfolio KPI template missing"
fi

echo
echo "[5/10] Dashboard Include"
grep -n "_portfolio_kpis" templates/dashboard_v115.html

echo
echo "[6/10] Flask Route"
grep -n "dashboard_v115.html" app.py

echo
echo "[7/10] Gunicorn Status"
systemctl is-active nse-v10-3.service

echo
echo "[8/10] Flask HTTP"
curl -I -s http://127.0.0.1:5000/ | head -5

echo
echo "[9/10] Disk Usage"
df -h /

echo
echo "[10/10] Memory"
free -h

echo
echo "=========================================="
echo "Health Check Complete"
echo "=========================================="
