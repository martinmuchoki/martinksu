import pandas as pd
import numpy as np
from services.market_data import get_price_history

def calculate_indicators_from_history(history):
    df = pd.DataFrame(history)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["sma20"] = df["close"].rolling(20).mean()
    df["sma50"] = df["close"].rolling(50).mean()
    df["sma200"] = df["close"].rolling(200).mean()

    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    mid = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    df["bb_mid"] = mid
    df["bb_upper"] = mid + 2 * std
    df["bb_lower"] = mid - 2 * std

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["close"].shift()).abs()
    tr3 = (df["low"] - df["close"].shift()).abs()
    df["true_range"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["atr"] = df["true_range"].rolling(14).mean()

    df["momentum10"] = df["close"] - df["close"].shift(10)
    df["volume_avg20"] = df["volume"].rolling(20).mean()
    df["volume_signal"] = np.where(df["volume"] > df["volume_avg20"], "High volume", "Normal volume")

    return df

def build_signal(latest):
    score = 50
    reasons = []

    if latest["close"] > latest["ema20"]:
        score += 10
        reasons.append("Price above EMA20")
    if latest["close"] > latest["ema50"]:
        score += 10
        reasons.append("Price above EMA50")
    if latest["rsi"] < 35:
        score += 10
        reasons.append("RSI oversold")
    elif latest["rsi"] > 70:
        score -= 10
        reasons.append("RSI overbought")
    if latest["macd"] > latest["macd_signal"]:
        score += 10
        reasons.append("MACD bullish crossover")
    if latest["momentum10"] > 0:
        score += 10
        reasons.append("Positive 10-day momentum")
    if latest["volume_signal"] == "High volume":
        score += 5
        reasons.append("High volume confirmation")

    score = max(0, min(100, int(score)))

    if score >= 80:
        signal = "STRONG BUY"
    elif score >= 65:
        signal = "BUY"
    elif score >= 45:
        signal = "HOLD"
    else:
        signal = "WATCH"

    return signal, score, reasons

def technical_score(stock):
    history = get_price_history(stock["symbol"])
    df = calculate_indicators_from_history(history)
    latest = df.iloc[-1]

    signal, score, reasons = build_signal(latest)

    return {
        "symbol": stock["symbol"],
        "price": round(float(latest["close"]), 2),
        "signal": signal,
        "score": score,
        "rsi": round(float(latest["rsi"]), 2),
        "macd": round(float(latest["macd"]), 3),
        "macd_signal": round(float(latest["macd_signal"]), 3),
        "ema20": round(float(latest["ema20"]), 2),
        "ema50": round(float(latest["ema50"]), 2),
        "ema200": round(float(latest["ema200"]), 2),
        "sma20": round(float(latest["sma20"]), 2),
        "sma50": round(float(latest["sma50"]), 2),
        "sma200": round(float(latest["sma200"]), 2),
        "bb_upper": round(float(latest["bb_upper"]), 2),
        "bb_lower": round(float(latest["bb_lower"]), 2),
        "atr": round(float(latest["atr"]), 2),
        "momentum10": round(float(latest["momentum10"]), 2),
        "volume_signal": latest["volume_signal"],
        "trend": "Uptrend" if latest["close"] > latest["ema50"] else "Downtrend / sideways",
        "reasons": reasons
    }

def analyze_market(stocks):
    return [technical_score(s) for s in stocks]
