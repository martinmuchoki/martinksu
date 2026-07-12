from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from services.market_data import get_price_history


REQUIRED_HISTORY_COLUMNS = {
    "open",
    "high",
    "low",
    "close",
    "volume",
}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)

        if math.isnan(number) or math.isinf(number):
            return default

        return number

    except (TypeError, ValueError):
        return default


def calculate_indicators_from_history(
    history: List[Dict[str, Any]],
) -> pd.DataFrame:
    """
    Calculate technical indicators from local historical OHLCV records.

    Returns an empty DataFrame when history is missing or malformed instead
    of raising KeyError errors.
    """
    if not history:
        return pd.DataFrame()

    df = pd.DataFrame(history)

    missing_columns = REQUIRED_HISTORY_COLUMNS.difference(df.columns)

    if missing_columns:
        return pd.DataFrame()

    for column in REQUIRED_HISTORY_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])

    if df.empty:
        return pd.DataFrame()

    df["volume"] = df["volume"].fillna(0)

    df["sma20"] = df["close"].rolling(20).mean()
    df["sma50"] = df["close"].rolling(50).mean()
    df["sma200"] = df["close"].rolling(200).mean()

    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()

    relative_strength = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + relative_strength))

    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()

    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    middle_band = df["close"].rolling(20).mean()
    standard_deviation = df["close"].rolling(20).std()

    df["bb_mid"] = middle_band
    df["bb_upper"] = middle_band + (2 * standard_deviation)
    df["bb_lower"] = middle_band - (2 * standard_deviation)

    true_range_1 = df["high"] - df["low"]
    true_range_2 = (df["high"] - df["close"].shift()).abs()
    true_range_3 = (df["low"] - df["close"].shift()).abs()

    df["true_range"] = pd.concat(
        [true_range_1, true_range_2, true_range_3],
        axis=1,
    ).max(axis=1)

    df["atr"] = df["true_range"].rolling(14).mean()
    df["momentum10"] = df["close"] - df["close"].shift(10)
    df["volume_avg20"] = df["volume"].rolling(20).mean()

    df["volume_signal"] = np.where(
        df["volume"] > df["volume_avg20"],
        "High volume",
        "Normal volume",
    )

    return df


def build_signal(latest: pd.Series) -> tuple[str, int, List[str]]:
    score = 50
    reasons: List[str] = []

    close = safe_float(latest.get("close"))
    ema20 = safe_float(latest.get("ema20"), close)
    ema50 = safe_float(latest.get("ema50"), close)
    rsi = safe_float(latest.get("rsi"), 50)
    macd = safe_float(latest.get("macd"))
    macd_signal = safe_float(latest.get("macd_signal"))
    momentum10 = safe_float(latest.get("momentum10"))

    if close > ema20:
        score += 10
        reasons.append("Price above EMA20")

    if close > ema50:
        score += 10
        reasons.append("Price above EMA50")

    if rsi < 35:
        score += 10
        reasons.append("RSI suggests oversold conditions")
    elif rsi > 70:
        score -= 10
        reasons.append("RSI suggests overbought conditions")

    if macd > macd_signal:
        score += 10
        reasons.append("MACD is above its signal line")

    if momentum10 > 0:
        score += 10
        reasons.append("Positive 10-day momentum")

    if latest.get("volume_signal") == "High volume":
        score += 5
        reasons.append("Above-average volume confirms momentum")

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


def live_snapshot_score(stock: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback model for securities without at least 30 valid OHLCV rows.

    This is a market-snapshot ranking, not a full historical technical model.
    """
    symbol = str(stock.get("symbol") or "").upper()
    price = safe_float(stock.get("price"))
    previous_close = safe_float(stock.get("previous_close"))
    change_pct = safe_float(stock.get("change_pct"))
    volume = int(safe_float(stock.get("volume")))

    score = 50
    reasons = [
        "Using the latest MyStocks Africa market snapshot",
        "Historical OHLCV is not yet sufficient for full technical indicators",
    ]

    if change_pct >= 5:
        score += 20
        reasons.append("Strong positive daily price movement")
    elif change_pct >= 3:
        score += 15
        reasons.append("Positive daily momentum")
    elif change_pct >= 1:
        score += 10
        reasons.append("Moderate positive daily movement")
    elif change_pct <= -5:
        score -= 20
        reasons.append("Strong negative daily price movement")
    elif change_pct <= -3:
        score -= 15
        reasons.append("Negative daily momentum")
    elif change_pct < 0:
        score -= 5
        reasons.append("Slight negative daily movement")

    if volume >= 1_000_000:
        score += 10
        reasons.append("Very strong trading volume")
    elif volume >= 100_000:
        score += 5
        reasons.append("Healthy trading volume")
    elif volume < 1_000:
        score -= 5
        reasons.append("Low liquidity requires caution")

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

    trend = (
        "Uptrend"
        if change_pct > 0
        else "Downtrend / sideways"
    )

    return {
        "symbol": symbol,
        "price": price,
        "previous_close": previous_close,
        "signal": signal,
        "score": score,
        "rsi": 50.0,
        "macd": 0.0,
        "macd_signal": 0.0,
        "ema20": price,
        "ema50": price,
        "ema200": price,
        "sma20": price,
        "sma50": price,
        "sma200": price,
        "bb_upper": price,
        "bb_lower": price,
        "atr": 0.0,
        "atr14": 0.0,
        "momentum10": change_pct,
        "volume_ratio": 1.0,
        "volume_signal": "Live Snapshot",
        "trend": trend,
        "reasons": reasons,
        "analysis_mode": "LIVE_SNAPSHOT",
        "history_rows": 0,
    }


def technical_score(stock: Dict[str, Any]) -> Dict[str, Any]:
    symbol = str(stock.get("symbol") or "").upper()
    history = get_price_history(symbol)

    if len(history) < 30:
        result = live_snapshot_score(stock)
        result["history_rows"] = len(history)
        return result

    df = calculate_indicators_from_history(history)

    if df.empty or len(df) < 30:
        result = live_snapshot_score(stock)
        result["history_rows"] = len(df)
        return result

    latest = df.iloc[-1]
    signal, score, reasons = build_signal(latest)

    live_price = safe_float(
        stock.get("price"),
        safe_float(latest.get("close")),
    )

    ema50 = safe_float(latest.get("ema50"), live_price)
    average_volume = safe_float(latest.get("volume_avg20"))
    current_volume = safe_float(latest.get("volume"))

    volume_ratio = (
        current_volume / average_volume
        if average_volume > 0
        else 1.0
    )

    atr = safe_float(latest.get("atr"))

    return {
        "symbol": symbol,
        "price": round(live_price, 2),
        "previous_close": safe_float(stock.get("previous_close")),
        "signal": signal,
        "score": score,
        "rsi": round(safe_float(latest.get("rsi"), 50), 2),
        "macd": round(safe_float(latest.get("macd")), 3),
        "macd_signal": round(
            safe_float(latest.get("macd_signal")),
            3,
        ),
        "ema20": round(
            safe_float(latest.get("ema20"), live_price),
            2,
        ),
        "ema50": round(ema50, 2),
        "ema200": round(
            safe_float(latest.get("ema200"), live_price),
            2,
        ),
        "sma20": round(
            safe_float(latest.get("sma20"), live_price),
            2,
        ),
        "sma50": round(
            safe_float(latest.get("sma50"), live_price),
            2,
        ),
        "sma200": round(
            safe_float(latest.get("sma200"), live_price),
            2,
        ),
        "bb_upper": round(
            safe_float(latest.get("bb_upper"), live_price),
            2,
        ),
        "bb_lower": round(
            safe_float(latest.get("bb_lower"), live_price),
            2,
        ),
        "atr": round(atr, 2),
        "atr14": round(atr, 2),
        "momentum10": round(
            safe_float(latest.get("momentum10")),
            2,
        ),
        "volume_ratio": round(volume_ratio, 2),
        "volume_signal": str(
            latest.get("volume_signal") or "Normal volume"
        ),
        "trend": (
            "Uptrend"
            if safe_float(latest.get("close")) > ema50
            else "Downtrend / sideways"
        ),
        "reasons": reasons,
        "analysis_mode": "FULL_TECHNICAL",
        "history_rows": len(df),
    }


def analyze_market(
    stocks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for stock in stocks:
        try:
            results.append(technical_score(stock))
        except Exception as exc:
            results.append(
                {
                    "symbol": stock.get("symbol", "UNKNOWN"),
                    "error": str(exc),
                    "score": 0,
                    "signal": "WATCH",
                    "analysis_mode": "ERROR",
                }
            )

    return results
