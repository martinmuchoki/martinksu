import pandas as pd
import numpy as np

from services.market_engine import get_symbol_history


def calculate_indicators(history):
    if not history or len(history) < 30:
        raise ValueError("At least 30 historical rows are required")

    df = pd.DataFrame(history).copy()

    for column in ["open", "high", "low", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

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
    df["macd_histogram"] = df["macd"] - df["macd_signal"]

    middle = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()

    df["bb_middle"] = middle
    df["bb_upper"] = middle + (2 * std)
    df["bb_lower"] = middle - (2 * std)

    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)

    df["atr14"] = true_range.rolling(14).mean()
    df["momentum10"] = df["close"] - df["close"].shift(10)
    df["volume_average20"] = df["volume"].rolling(20).mean()

    df["volume_ratio"] = (
        df["volume"] / df["volume_average20"].replace(0, np.nan)
    )

    return df


def build_signal(latest):
    score = 50
    reasons = []

    if latest["close"] > latest["ema20"]:
        score += 10
        reasons.append("Price is above EMA20")

    if latest["close"] > latest["ema50"]:
        score += 10
        reasons.append("Price is above EMA50")

    if latest["close"] > latest["sma200"]:
        score += 10
        reasons.append("Price is above SMA200")

    if latest["rsi"] < 35:
        score += 10
        reasons.append("RSI is near oversold")

    elif latest["rsi"] > 70:
        score -= 10
        reasons.append("RSI is overbought")

    if latest["macd"] > latest["macd_signal"]:
        score += 10
        reasons.append("MACD is bullish")

    else:
        score -= 5
        reasons.append("MACD is below signal")

    if latest["momentum10"] > 0:
        score += 10
        reasons.append("Positive 10-day momentum")

    if latest["volume_ratio"] >= 1.25:
        score += 5
        reasons.append("Volume confirms the move")

    score = max(0, min(100, int(score)))

    if score >= 80:
        signal = "STRONG BUY"
    elif score >= 65:
        signal = "BUY"
    elif score >= 45:
        signal = "HOLD"
    elif score >= 30:
        signal = "WATCH"
    else:
        signal = "SELL"

    return signal, score, reasons


def analyze_symbol(symbol):
    result = get_symbol_history(symbol, 260)

    if not result:
        return None

    df = calculate_indicators(result["history"])
    latest = df.iloc[-1]

    signal, score, reasons = build_signal(latest)

    return {
        "symbol": result["stock"]["symbol"],
        "name": result["stock"]["name"],
        "sector": result["stock"]["sector"],
        "trade_date": str(latest["trade_date"]),
        "price": round(float(latest["close"]), 2),
        "signal": signal,
        "score": score,
        "rsi": round(float(latest["rsi"]), 2),
        "macd": round(float(latest["macd"]), 4),
        "macd_signal": round(float(latest["macd_signal"]), 4),
        "ema20": round(float(latest["ema20"]), 2),
        "ema50": round(float(latest["ema50"]), 2),
        "ema200": round(float(latest["ema200"]), 2),
        "sma20": round(float(latest["sma20"]), 2),
        "sma50": round(float(latest["sma50"]), 2),
        "sma200": round(float(latest["sma200"]), 2),
        "bb_upper": round(float(latest["bb_upper"]), 2),
        "bb_middle": round(float(latest["bb_middle"]), 2),
        "bb_lower": round(float(latest["bb_lower"]), 2),
        "atr14": round(float(latest["atr14"]), 2),
        "momentum10": round(float(latest["momentum10"]), 2),
        "volume_ratio": round(float(latest["volume_ratio"]), 2),
        "trend": (
            "Uptrend"
            if latest["close"] > latest["ema50"]
            else "Downtrend / sideways"
        ),
        "reasons": reasons,
    }


def analyze_all_symbols(stocks):
    results = []

    for stock in stocks:
        try:
            analysis = analyze_symbol(stock["symbol"])

            if analysis:
                results.append(analysis)

        except Exception as exc:
            results.append(
                {
                    "symbol": stock["symbol"],
                    "error": str(exc),
                }
            )

    return results
