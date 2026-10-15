import os
import json
import re
import requests

DEFAULT_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")


def algorithmic_token_evaluation(token_data: dict) -> dict:
    """
    Algorithmic scalper evaluation engine for Solana & BSC tokens.
    Analyzes metrics to produce a short-term 2x upside rating (1-10) and trading memo.
    """
    token_name = token_data.get('token_name') or token_data.get('name', 'Unknown Token')
    symbol = token_data.get('token_symbol') or token_data.get('symbol', 'COIN')
    market_cap = float(token_data.get('market_cap') or token_data.get('usd_market_cap', 0) or 0)
    top_10 = float(token_data.get('top_10_holder_rate', 0.25) or 0.25)
    creator_hold = float(token_data.get('creator_balance_rate', 0.05) or 0.05)
    bundler_rate = float(token_data.get('bundler_trader_amount_rate', 0) or 0)
    sniper_count = int(token_data.get('sniper_count', 0) or 0)
    dex_paid = bool(token_data.get('dex_paid') or token_data.get('dexscr_ad') or False)
    has_website = bool(token_data.get('token_website_content') or token_data.get('website'))
    kabal_risk = float(token_data.get('kabal_coin_percentage', 0) or 0)

    score = 7.0
    thesis_points = []
    risks = []
    catalysts = []

    # Market Cap Analysis
    if 8000 <= market_cap <= 35000:
        score += 1.2
        catalysts.append(f"Sub-$35k market cap (${market_cap:,.0f}) provides extreme velocity for 2x-5x microcap scalps.")
    elif 35000 < market_cap <= 100000:
        score += 0.5
        catalysts.append(f"Healthy early growth stage (${market_cap:,.0f} MC). Strong liquidity anchor.")
    elif market_cap > 500000:
        score -= 1.0
        thesis_points.append("Market cap is getting heavy for rapid immediate 2x upside.")
    elif market_cap < 5000 and market_cap > 0:
        score -= 0.5
        risks.append("Extremely micro liquidity; high slippage volatility.")

    # Holder Concentration Check
    if top_10 <= 0.20:
        score += 0.8
        catalysts.append(f"Excellent holder decentralization: Top 10 wallets hold only {top_10*100:.1f}%.")
    elif top_10 > 0.35:
        score -= 1.5
        risks.append(f"Concentrated top holders ({top_10*100:.1f}% in top 10). High dump hazard.")

    # Creator & Bundler Risk
    if creator_hold > 0.10:
        score -= 1.8
        risks.append(f"Dev wallet retains {creator_hold*100:.1f}% supply — high developer dump risk.")
    elif creator_hold <= 0.02:
        score += 0.5
        catalysts.append("Dev has effectively renounced/distributed initial allocation.")

    if bundler_rate > 0.20 or kabal_risk > 40:
        score -= 1.5
        risks.append(f"Suspected bundler / kabal cluster activity detected ({bundler_rate*100:.0f}% bundler rate).")

    if sniper_count > 25:
        risks.append(f"High sniper presence ({sniper_count} snipers); watch for immediate sell-offs on spikes.")
    elif sniper_count < 10:
        score += 0.3
        catalysts.append("Clean launch profile with minimal sniper congestion.")

    # Narrative & DEX presence
    if dex_paid:
        score += 0.8
        catalysts.append("DEX ads / DexScreener paid placement active — driving organic degen visibility.")

    if has_website:
        catalysts.append("Active functional web presence verified.")
    else:
        score -= 0.5
        risks.append("No independent verified website found — purely speculative meme momentum.")

    final_score = max(1.0, min(9.8, round(score, 1)))

    if final_score >= 8.0:
        verdict = "YES — High-conviction short-term scalp"
    elif final_score >= 6.5:
        verdict = "SPECULATIVE — Solid momentum setup with strict stop-losses"
    elif final_score >= 5.0:
        verdict = "NEUTRAL — Moderate risk profile, wait for volume confirmation"
    else:
        verdict = "NO — High distribution / bundle risk"

    thesis = f"[{verdict}] {symbol} is trading at ${market_cap:,.0f} MC. "
    if catalysts:
        thesis += "Key Bullish Catalysts: " + " ".join(catalysts[:2]) + " "
    if risks:
        thesis += "Risk Factors: " + " ".join(risks[:2]) + " "
    thesis += f"Scalper Guidance: Aim for quick 1.5x-2.5x exit brackets. Set tight trailing invalidation levels."

    return {
        "trading_thesis": thesis,
        "score": final_score,
        "verdict": verdict,
        "immediate_trading_thesis": verdict,
        "technology_and_narrative": "Verified on-chain telemetry and social footprint." if has_website else "Pure degen meme narrative.",
        "fundamentals_and_liquidity": f"Market Cap: ${market_cap:,.0f} | Top 10: {top_10*100:.1f}%",
        "engine": "Heliox Scalper Intelligence v2.0"
    }


def analyze_with_gemini_or_engine(final_data: dict, api_key: str = None) -> dict:
    """
    Attempts to query Gemini 2.0 Flash via REST API.
    Falls back gracefully to the algorithmic scalper engine if key is absent or invalid.
    """
    key = api_key or DEFAULT_GEMINI_KEY
    if key and len(key) > 20:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        prompt = f"""You are an elite crypto scalper and smart-contract auditor.
Analyze this newly scanned token data:
{json.dumps(final_data, indent=2)}

Determine if it has realistic potential for 2x+ upside within 30m-24h.
Assess:
1. Market cap velocity & liquidity safety.
2. Holder concentration & bundle/kabal dump hazard.
3. Narrative hype & web/social validity.

Respond ONLY with valid JSON:
{{
  "trading_thesis": "concise, decisive 2-4 sentence scalper memo",
  "score": float between 1.0 and 10.0,
  "verdict": "YES / SPECULATIVE / NO"
}}
"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "response_mime_type": "application/json"
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                result_json = resp.json()
                text_content = result_json["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text_content)
                parsed["engine"] = "Gemini 2.0 Flash AI"
                return parsed
            else:
                print(f"[Gemini REST API Warning {resp.status_code}]: {resp.text[:150]}")
        except Exception as e:
            print(f"[Gemini Call Exception]: {e}")

    # Fallback to smart heuristic scalper engine
    return algorithmic_token_evaluation(final_data)
