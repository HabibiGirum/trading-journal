from __future__ import annotations

# Common XAU / BTC setups real traders actually journal.
SCENARIOS: list[dict[str, str]] = [
    {
        "id": "fvg",
        "label": "Fair value gap",
        "win": "Fair value gap: Daily/4H bias matched. A displacement left an imbalance. I waited for price to tap the gap (not chase) and entered. Stop went beyond the candle that created the gap.",
        "loss": "Fair value gap mistake: I entered a gap against the higher-timeframe bias, or I chased after the gap was already filled.",
    },
    {
        "id": "order_block",
        "label": "Order block",
        "win": "Order block: Last opposing candle before a strong displacement. Price returned to that block, I took the reaction. Stop was on the other side of the block.",
        "loss": "Order block mistake: I bought a bullish block in premium (or sold a bearish block in discount), or the block was already used / mitigated.",
    },
    {
        "id": "liquidity",
        "label": "Liquidity sweep",
        "win": "Liquidity sweep: Equal highs/lows or a session high/low were taken. I waited for a close back inside the range, then entered. The stops that got run were the liquidity.",
        "loss": "Liquidity mistake: I faded the first spike with no shift in structure. That was continuation, not a reversal.",
    },
    {
        "id": "bos",
        "label": "Break and retest",
        "win": "Break and retest: Structure broke (BOS). I did not chase the breakout candle. I waited for the retest of the broken level and entered with the new trend.",
        "loss": "Break and retest mistake: I entered the breakout itself, or the retest failed and I stayed in anyway.",
    },
    {
        "id": "ote",
        "label": "Premium / discount",
        "win": "Premium/discount: I only bought in discount (below 50% of the dealing range) or sold in premium (above 50%). Best entries were in the 62–79% (OTE) zone.",
        "loss": "Location mistake: I entered at equilibrium — the middle of the range. No discount/premium edge.",
    },
    {
        "id": "killzone",
        "label": "London / NY killzone",
        "win": "Killzone: I waited for London or New York open. First move was manipulation. I took the second, real move after liquidity was taken.",
        "loss": "Session mistake: I traded dead hours, or I clicked the first spike at the open and got stopped.",
    },
    {
        "id": "asian",
        "label": "Asian range raid",
        "win": "Asian range: London/NY ran the Asian high or low, then displaced. I traded the raid, not inside the tight Asia box.",
        "loss": "Asian range mistake: I traded inside the Asia range. Chop and spread, no expansion.",
    },
    {
        "id": "supply_demand",
        "label": "Supply / demand",
        "win": "Supply/demand: Fresh zone from a strong impulsive move. Price came back once. I entered in the zone, stop beyond it.",
        "loss": "Zone mistake: The level was already tested (not fresh), or I used a wide zone with a tiny stop.",
    },
    {
        "id": "news",
        "label": "News spike",
        "win": "News: I stayed out of the print (CPI, NFP, FOMC, or a BTC headline). After the spike took liquidity I traded the return to value with a defined stop.",
        "loss": "News mistake: I clicked during the release. Spread, slippage, no plan.",
    },
    {
        "id": "confluence",
        "label": "HTF confluence",
        "win": "Confluence: Daily and 4H agreed. 1H gave the entry (FVG, block, or sweep). I only took the trade because the timeframes stacked.",
        "loss": "Confluence mistake: Lower timeframe looked good but daily/4H disagreed. I traded anyway.",
    },
]
