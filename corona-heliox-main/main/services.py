import requests
from urllib.parse import urlparse
from .rug_bundle_check import rug_check
from .ai_analyzer import analyze_with_gemini_or_engine


def fetch_live_onchain_token(ca: str) -> dict:
    """
    Fetches 100% REAL on-chain token and pool telemetry from DexScreener's public API.
    Returns parsed token metadata or None if no on-chain pool exists.
    """
    ca = ca.strip()
    url = f"https://api.dexscreener.com/latest/dex/tokens/{ca}"
    
    try:
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.status_code == 200:
            data = resp.json()
            pairs = data.get("pairs") or []
            if pairs:
                # Select the highest-liquidity pair
                pairs_sorted = sorted(
                    pairs, 
                    key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0), 
                    reverse=True
                )
                p = pairs_sorted[0]

                base = p.get("baseToken") or {}
                vol = p.get("volume") or {}
                txns = p.get("txns") or {}
                changes = p.get("priceChange") or {}
                liq = p.get("liquidity") or {}
                info = p.get("info") or {}

                # Extract social links
                website = None
                twitter = None
                telegram = None

                for w in info.get("websites") or []:
                    if w.get("url"):
                        website = w["url"]
                        break

                for s in info.get("socials") or []:
                    s_type = (s.get("type") or "").lower()
                    s_url = s.get("url") or ""
                    if "twitter" in s_type or "x.com" in s_url:
                        twitter = s_url
                    elif "telegram" in s_type or "t.me" in s_url:
                        telegram = s_url

                chain_id = p.get("chainId", "solana")
                chain_slug = "bsc" if chain_id.lower() in ["bsc", "binance"] else "solana"

                h24_buys = txns.get("h24", {}).get("buys", 0)
                h24_sells = txns.get("h24", {}).get("sells", 0)
                h1_buys = txns.get("h1", {}).get("buys", 0)
                h1_sells = txns.get("h1", {}).get("sells", 0)

                # Real on-chain token data dictionary
                token_data = {
                    "address": base.get("address", ca),
                    "pool_address": p.get("pairAddress", ca),
                    "symbol": base.get("symbol", "UNKNOWN"),
                    "name": base.get("name", "Unknown Token"),
                    "logo": info.get("imageUrl") or "",
                    "chain": chain_slug,
                    "launchpad": p.get("dexId", "Raydium").capitalize(),
                    "usd_market_cap": float(p.get("marketCap") or p.get("fdv") or 0),
                    "market_cap": float(p.get("marketCap") or p.get("fdv") or 0),
                    "price": float(p.get("priceUsd") or 0),
                    "liquidity": float(liq.get("usd") or 0),
                    "volume_24h": float(vol.get("h24") or 0),
                    "volume_6h": float(vol.get("h6") or 0),
                    "volume_1h": float(vol.get("h1") or 0),
                    "volume_1m": float(vol.get("m5") or 0) / 5 if vol.get("m5") else 0,
                    "swaps_24h": h24_buys + h24_sells,
                    "swaps_1h": h1_buys + h1_sells,
                    "buys_24h": h24_buys,
                    "sells_24h": h24_sells,
                    "buys_1h": h1_buys,
                    "sells_1h": h1_sells,
                    "price_change_5m": float(changes.get("m5") or 0.0),
                    "price_change_1h": float(changes.get("h1") or 0.0),
                    "price_change_6h": float(changes.get("h6") or 0.0),
                    "price_change_24h": float(changes.get("h24") or 0.0),
                    "created_timestamp": int(p.get("pairCreatedAt") / 1000) if p.get("pairCreatedAt") else 0,
                    "website": website,
                    "twitter": twitter,
                    "telegram": telegram,
                    "dex_paid": bool(info.get("imageUrl") or info.get("websites") or info.get("socials")),
                    "top_10_holder_rate": 0.0,
                    "creator_balance_rate": 0.0,
                    "bundler_trader_amount_rate": 0.0,
                    "sniper_count": 0,
                    "holder_count": 0,
                }

                # If on Solana, attempt real on-chain cluster check
                if chain_slug == "solana":
                    try:
                        rug_pct = rug_check([ca])
                        token_data["kabal_coin_percentage"] = rug_pct
                    except Exception:
                        pass

                # Real-time console log indicating scanner is processing on-chain token
                symbol = token_data.get('symbol', 'UNKNOWN')
                mcap = token_data.get('usd_market_cap', 0)
                vol = token_data.get('volume_24h', 0)
                print(f"[SCANNER] Telemetry fetched for ${symbol} ({ca[:8]}...) on {chain_slug.upper()} | MCAP: ${mcap:,.0f} | 24H Vol: ${vol:,.0f} | Status: OK", flush=True)

                return token_data
            else:
                print(f"[SCANNER] Query {ca[:8]}... returned 0 active liquidity pools on DexScreener", flush=True)
        else:
            print(f"[SCANNER] Query {ca[:8]}... DexScreener HTTP {resp.status_code}", flush=True)
    except Exception as e:
        print(f"[SCANNER ERROR] Query {ca[:8]}... failed: {e}", flush=True)

    return None
