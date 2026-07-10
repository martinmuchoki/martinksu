from services.market_engine import get_symbol_history
from services.indicator_engine import calculate_indicators


def safe_value(value):
    if value is None:
        return None

    try:
        if value != value:
            return None
    except TypeError:
        pass

    return round(float(value), 4)


def get_chart_data(symbol, limit=120):
    result = get_symbol_history(symbol, 260)

    if not result:
        return None

    df = calculate_indicators(result["history"])
    df = df.tail(limit)

    candles = []
    indicators = []
    volume = []

    for _, row in df.iterrows():
        trade_date = str(row["trade_date"])

        candles.append({
            "date": trade_date,
            "open": safe_value(row["open"]),
            "high": safe_value(row["high"]),
            "low": safe_value(row["low"]),
            "close": safe_value(row["close"]),
        })

        indicators.append({
            "date": trade_date,
            "close": safe_value(row["close"]),
            "ema20": safe_value(row["ema20"]),
            "ema50": safe_value(row["ema50"]),
            "ema200": safe_value(row["ema200"]),
            "sma200": safe_value(row["sma200"]),
            "bb_upper": safe_value(row["bb_upper"]),
            "bb_middle": safe_value(row["bb_middle"]),
            "bb_lower": safe_value(row["bb_lower"]),
            "rsi": safe_value(row["rsi"]),
            "macd": safe_value(row["macd"]),
            "macd_signal": safe_value(row["macd_signal"]),
            "macd_histogram": safe_value(row["macd_histogram"]),
            "atr14": safe_value(row["atr14"]),
            "momentum10": safe_value(row["momentum10"]),
        })

        volume.append({
            "date": trade_date,
            "volume": int(row["volume"]),
            "volume_average20": safe_value(row["volume_average20"]),
        })

    return {
        "symbol": result["stock"]["symbol"],
        "name": result["stock"]["name"],
        "sector": result["stock"]["sector"],
        "candles": candles,
        "indicators": indicators,
        "volume": volume,
    }
