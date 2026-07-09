from flask import Flask, render_template, jsonify
from datetime import datetime
from services.ai_committee import run_committee

app = Flask(__name__)
VERSION = "10.3.1"

@app.route("/")
def dashboard():
    committee = run_committee()
    return render_template(
        "dashboard.html",
        version=VERSION,
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        market_status="Foundation Mode",
        telegram_status="Not configured",
        system_status="Online",
        committee=committee
    )

@app.route("/committee")
def committee():
    return jsonify(run_committee())

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "version": VERSION,
        "service": "NSE Signal Bot V10.3 Enterprise",
        "time": datetime.now().isoformat()
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
