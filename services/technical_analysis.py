def technical_score(stock):
    change = float(stock.get("change_pct", 0))
    volume = int(stock.get("volume", 0))

    rsi = round(min(80, max(25, 55 + change * 5)), 2)
    momentum = round(50 + change * 10 + min(volume / 100000, 20), 2)

    if momentum >= 80:
        signal = "STRONG BUY"
    elif momentum >= 65:
        signal = "BUY"
    elif momentum >= 45:
        signal = "HOLD"
    else:
        signal = "WATCH"

    return {
        "symbol": stock["symbol"],
        "price": stock["price"],
        "change_pct": change,
        "signal": signal,
        "score": round(momentum),
        "rsi": rsi,
        "ema20": round(stock["price"] * 0.98, 2),
        "ema50": round(stock["price"] * 0.95, 2),
        "macd": round(change * 0.35, 2),
        "bollinger": "Inside band" if abs(change) < 2 else "Breakout watch",
        "trend": "Uptrend" if change > 0 else "Weak / sideways"
    }

def analyze_market(stocks):
    return [technical_score(s) for s in stocks]
