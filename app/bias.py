from __future__ import annotations


def _num(value: str | float | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def analyze_setup(
    daily: str,
    h4: str,
    h1: str,
    structure: str,
    location: str,
    liquidity: str,
    current_price: str | float | None = None,
    swing_low: str | float | None = None,
    swing_high: str | float | None = None,
) -> dict:
    daily = (daily or "").lower()
    h4 = (h4 or "").lower()
    h1 = (h1 or "").lower()
    structure = (structure or "").lower()
    location = (location or "").lower()
    liquidity = (liquidity or "").lower()
    price = _num(current_price)
    low = _num(swing_low)
    high = _num(swing_high)

    reasons: list[str] = []
    emotion = "Follow the daily. If this says no trade, close the chart."

    htf_buy = daily == "bullish" and h4 == "bullish"
    htf_sell = daily == "bearish" and h4 == "bearish"
    conflict = (daily == "bullish" and h4 == "bearish") or (daily == "bearish" and h4 == "bullish")
    ranging = daily == "range" or (daily != "range" and h4 == "range" and h1 == "range")

    if conflict:
        return {
            "direction": "NO TRADE",
            "action": "wait",
            "strength": "Conflict",
            "stop_loss": None,
            "stop_rule": "No stop. There is no trade.",
            "target_rule": "Do not hunt a target against the higher timeframe.",
            "reasons": [
                f"Daily is {daily} and 4H is {h4}. They disagree.",
                "A conflict is how revenge trades start. Sit out.",
            ],
            "emotion": "Do not pick a side. Wait until daily and 4H agree.",
        }

    if ranging and not htf_buy and not htf_sell:
        return {
            "direction": "NO TRADE",
            "action": "wait",
            "strength": "Range",
            "stop_loss": None,
            "stop_rule": "No stop. There is no trade.",
            "target_rule": "Wait for a daily or 4H break and close.",
            "reasons": [
                "The higher timeframes are ranging or mixed.",
                "Chop is where emotions overtrade.",
            ],
            "emotion": "No direction, no trade. Protect the account.",
        }

    if htf_buy:
        direction = "BUY"
        action = "buy"
        reasons.append("Daily bullish and 4H bullish. Buy is the only allowed direction.")
        stop_rule = "Stop loss below the last 4H swing low."
        stop_loss = low
        if stop_loss is not None:
            stop_rule = f"Stop loss below {stop_loss:g} (your 4H swing low)."
        target_rule = "First target at the next 4H high or 1:2 from the stop. Do not flip to sell."

        if h1 == "bearish":
            strength = "Wait for pullback"
            reasons.append("1H is still bearish. That is a pullback inside a buy market. Do not sell it.")
            emotion = "Let 1H turn bullish again. Chasing or shorting here is emotion."
        elif h1 == "bullish":
            strength = "Strong"
            reasons.append("1H is also bullish. Alignment is complete.")
            emotion = "Take the buy or skip it. Do not invent a short."
        else:
            strength = "Valid"
            reasons.append("1H is mixed. Still only look for buys.")
            emotion = "If you feel like selling, that feeling is the thing to ignore."

        if location == "premium":
            reasons.append("Price is in premium. Buy only a pullback, do not chase highs.")
            if strength == "Strong":
                strength = "Wait for pullback"
        elif location == "discount":
            reasons.append("Price is in discount. This is the better buy zone.")
        elif location == "equilibrium":
            reasons.append("Price is around equilibrium. Fine for a planned buy, not a late chase.")

        if liquidity == "swept_lows":
            reasons.append("Liquidity below was taken. That supports a buy if daily stays bullish.")
        elif liquidity == "swept_highs":
            reasons.append("Highs were swept. Do not buy a blow-off high. Wait for a discount.")
            if strength == "Strong":
                strength = "Wait for pullback"

        if structure == "down":
            reasons.append("Internal structure is still down. Wait for a higher low before entry.")
            strength = "Wait for pullback"
        elif structure == "up":
            reasons.append("Structure is making higher highs / higher lows.")

        if price is not None and low is not None and price <= low:
            direction = "NO TRADE"
            action = "wait"
            strength = "Invalid"
            stop_loss = None
            stop_rule = "No trade. Price is already through the swing low."
            reasons.append("Price is at or below the stop level. The long idea is already wrong.")
            emotion = "Do not move the stop. The setup failed. Wait for a new one."

        return {
            "direction": direction,
            "action": action,
            "strength": strength,
            "stop_loss": stop_loss,
            "stop_rule": stop_rule,
            "target_rule": target_rule,
            "reasons": reasons,
            "emotion": emotion,
        }

    if htf_sell:
        direction = "SELL"
        action = "sell"
        reasons.append("Daily bearish and 4H bearish. Sell is the only allowed direction.")
        stop_rule = "Stop loss above the last 4H swing high."
        stop_loss = high
        if stop_loss is not None:
            stop_rule = f"Stop loss above {stop_loss:g} (your 4H swing high)."
        target_rule = "First target at the next 4H low or 1:2 from the stop. Do not flip to buy."

        if h1 == "bullish":
            strength = "Wait for pullback"
            reasons.append("1H is still bullish. That is a pullback inside a sell market. Do not buy it.")
            emotion = "Let 1H turn bearish again. Buying the bounce is emotion."
        elif h1 == "bearish":
            strength = "Strong"
            reasons.append("1H is also bearish. Alignment is complete.")
            emotion = "Take the sell or skip it. Do not invent a long."
        else:
            strength = "Valid"
            reasons.append("1H is mixed. Still only look for sells.")
            emotion = "If you feel like buying, that feeling is the thing to ignore."

        if location == "discount":
            reasons.append("Price is in discount. Sell only a pullback into premium, do not chase lows.")
            if strength == "Strong":
                strength = "Wait for pullback"
        elif location == "premium":
            reasons.append("Price is in premium. This is the better sell zone.")
        elif location == "equilibrium":
            reasons.append("Price is around equilibrium. Fine for a planned sell, not a late chase.")

        if liquidity == "swept_highs":
            reasons.append("Liquidity above was taken. That supports a sell if daily stays bearish.")
        elif liquidity == "swept_lows":
            reasons.append("Lows were swept. Do not sell a panic low. Wait for a premium.")
            if strength == "Strong":
                strength = "Wait for pullback"

        if structure == "up":
            reasons.append("Internal structure is still up. Wait for a lower high before entry.")
            strength = "Wait for pullback"
        elif structure == "down":
            reasons.append("Structure is making lower highs / lower lows.")

        if price is not None and high is not None and price >= high:
            direction = "NO TRADE"
            action = "wait"
            strength = "Invalid"
            stop_loss = None
            stop_rule = "No trade. Price is already through the swing high."
            reasons.append("Price is at or above the stop level. The short idea is already wrong.")
            emotion = "Do not move the stop. The setup failed. Wait for a new one."

        return {
            "direction": direction,
            "action": action,
            "strength": strength,
            "stop_loss": stop_loss,
            "stop_rule": stop_rule,
            "target_rule": target_rule,
            "reasons": reasons,
            "emotion": emotion,
        }

    return {
        "direction": "NO TRADE",
        "action": "wait",
        "strength": "Unclear",
        "stop_loss": None,
        "stop_rule": "No stop. There is no trade.",
        "target_rule": "Mark the levels and wait.",
        "reasons": ["Daily and 4H are not both bullish or both bearish."],
        "emotion": "No clear map, no trade.",
    }
