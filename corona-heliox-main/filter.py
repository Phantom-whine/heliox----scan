def advanced_token_filter(token_data, min_market_cap=10000, max_age_seconds=200000):
    """
    Advanced Python filter to catch tokens early (market cap >= 10k USD) 
    and filter out potential scams based on provided data fields.
    
    Parameters:
        token_data (dict): Token data as provided in the input.
        min_market_cap (float): Minimum market cap for early catch (default 10k USD).
        max_age_seconds (int): Maximum token age in seconds for early detection (default 200,000 seconds, ~2.3 days).
    
    Evaluation Criteria:
    - Early detection: Market cap >= 10k, recent creation (within max_age_seconds),
      and not fully launched/live if on Pump.fun (progress < 1.0).
    - Scam filtering: Checks for red flags like high holder concentration, creator/dev holds,
      unrenounced authorities, lack of socials, high bot/sniper activity, rug indicators,
      wash trading, etc. Uses weighted scoring for nuanced decisions.
    
    Returns:
        tuple: (bool, str) - (True if passes filter, reason/explanation string)
    """
    import time
    
    # Thresholds and weights (adjustable for tuning)
    MIN_MARKET_CAP = min_market_cap  # USD, minimum for early catch
    MAX_TOP_10_HOLD_RATE = 0.30  # 30% max for top 10 holders
    MAX_CREATOR_HOLD_RATE = 0.05  # 5% max creator hold
    MAX_DEV_TEAM_HOLD_RATE = 0.05  # 5% max dev/team hold
    MAX_SUSPECTED_INSIDER_HOLD = 0.01  # Low insider hold
    MAX_BOT_DEGEN_RATE = 50  # High bot/degen activity red flag
    MAX_SNIPER_COUNT = 5  # Too many snipers indicate pump/dump
    MIN_HOLDER_COUNT = 20  # At least some distribution
    MIN_LIQUIDITY = 10000  # USD, reasonable liquidity for early token
    MAX_RUG_RATIO = 0.01  # Any rug history is bad
    MAX_BUNDLER_TRADER_RATE = 0.10  # Bundler traders often indicate manipulation
    MAX_FRESH_WALLET_RATE = 0.20  # High fresh wallets might be bots
    
    # Scoring system: Start at 100, deduct points for issues. Threshold: >= 70 to pass.
    score = 100
    reasons = []
    
    # Early detection checks (mandatory)
    current_time = int(time.time())
    age_seconds = current_time - token_data.get('created_timestamp', 0)
    market_cap = token_data.get('usd_market_cap', 0)
    progress = token_data.get('progress', 1.0)
    is_live = token_data.get('is_token_live', True)
    
    if market_cap < MIN_MARKET_CAP:
        reasons.append(f"Market cap {market_cap:.2f} is below {MIN_MARKET_CAP} threshold for early catch.")
        return False, " ".join(reasons)
    
    if age_seconds > max_age_seconds:
        reasons.append(f"Token age {age_seconds} seconds exceeds {max_age_seconds} for early detection.")
        return False, " ".join(reasons)
    
    if progress >= 1.0 and is_live:
        reasons.append("Token is fully launched and live; not early enough.")
        return False, " ".join(reasons)
    
    # Scam filtering with scoring
    # Holder distribution (critical: high concentration = scam risk)
    top_10_rate = token_data.get('top_10_holder_rate', 1.0)
    if top_10_rate > MAX_TOP_10_HOLD_RATE:
        score -= 40
        reasons.append(f"High top 10 holder rate: {top_10_rate*100:.2f}% (deduct 40 points)")
    
    # Creator/Dev holds (high hold = potential rug)
    creator_hold = token_data.get('creator_balance_rate', 1.0)
    dev_hold = token_data.get('dev_team_hold_rate', 1.0)
    insider_hold = token_data.get('suspected_insider_hold_rate', 1.0)
    if creator_hold > MAX_CREATOR_HOLD_RATE:
        score -= 30
        reasons.append(f"High creator hold: {creator_hold*100:.2f}% (deduct 30 points)")
    if dev_hold > MAX_DEV_TEAM_HOLD_RATE:
        score -= 20
        reasons.append(f"High dev/team hold: {dev_hold*100:.2f}% (deduct 20 points)")
    if insider_hold > MAX_SUSPECTED_INSIDER_HOLD:
        score -= 15
        reasons.append(f"Suspected insider hold: {insider_hold*100:.2f}% (deduct 15 points)")
    
    # Authority and burn status (non-renounced = instant fail)
    if not token_data.get('renounced_mint', False):
        reasons.append("Mint authority not renounced.")
        return False, " ".join(reasons)
    if not token_data.get('renounced_freeze_account', False):
        reasons.append("Freeze authority not renounced.")
        return False, " ".join(reasons)
    if token_data.get('burn_status', '') != 'burn':
        reasons.append("Liquidity not burned.")
        return False, " ".join(reasons)
    
    # Social presence (lack of socials = scam risk)
    has_social = token_data.get('has_at_least_one_social', False)
    if not has_social:
        score -= 25
        reasons.append("No social presence (deduct 25 points)")
    
    # Bot/Sniper/Degen activity (high = manipulation risk)
    bot_degen_rate = token_data.get('bot_degen_rate', 0)
    sniper_count = token_data.get('sniper_count', 0)
    bot_degen_count = token_data.get('bot_degen_count', 0)
    if bot_degen_rate > MAX_BOT_DEGEN_RATE or bot_degen_count > MAX_BOT_DEGEN_RATE:
        score -= 25
        reasons.append(f"High bot/degen activity: rate {bot_degen_rate}, count {bot_degen_count} (deduct 25 points)")
    if sniper_count > MAX_SNIPER_COUNT:
        score -= 20
        reasons.append(f"High sniper count: {sniper_count} (deduct 20 points)")
    
    # Other red flags
    rug_ratio = token_data.get('rug_ratio', 1.0)
    if rug_ratio > MAX_RUG_RATIO:
        reasons.append(f"Rug ratio {rug_ratio} indicates high rug risk.")
        return False, " ".join(reasons)
    
    if token_data.get('is_wash_trading', False):
        reasons.append("Wash trading detected.")
        return False, " ".join(reasons)
    
    if token_data.get('cto_flag', False):
        score -= 15
        reasons.append("CTO flag set (deduct 15 points)")
    
    bundler_rate = token_data.get('bundler_trader_amount_rate', 0)
    if bundler_rate > MAX_BUNDLER_TRADER_RATE:
        score -= 15
        reasons.append(f"High bundler trader rate: {bundler_rate*100:.2f}% (deduct 15 points)")
    
    fresh_wallet_rate = token_data.get('fresh_wallet_rate', 0)
    if fresh_wallet_rate > MAX_FRESH_WALLET_RATE:
        score -= 10
        reasons.append(f"High fresh wallet rate: {fresh_wallet_rate*100:.2f}% (deduct 10 points)")
    
    # Holder and liquidity checks
    holder_count = token_data.get('holder_count', 0)
    if holder_count < MIN_HOLDER_COUNT:
        score -= 10
        reasons.append(f"Low holder count: {holder_count} (deduct 10 points)")
    
    liquidity = token_data.get('liquidity', 0)
    if liquidity < MIN_LIQUIDITY:
        score -= 10
        reasons.append(f"Low liquidity: {liquidity:.2f} (deduct 10 points)")
    
    # Creator history
    creator_created_count = token_data.get('creator_created_count', 0)
    if creator_created_count > 5:  # Too many creations = serial scammer
        score -= 20
        reasons.append(f"Creator has created {creator_created_count} tokens (deduct 20 points)")
    
    # Final decision
    if score >= 70:
        return True, f"Passed with score {score}/100. Reasons: {' '.join(reasons) if reasons else 'No issues.'}"
    else:
        return False, f"Failed with score {score}/100. Reasons: {' '.join(reasons)}"

# Example usage with provided data
token_data = {
    "address": "7nL5XBuaggZ5vs3Wq49fE7rJqqxTu5hdMWNNiBRnpump",
    "pool_address": "FmBdi8KtGFiivRVAbLC7J5CEujxjd6KC8LaZ14S1Pd1W",
    "quote_address": "So11111111111111111111111111111111111111112",
    "logo": "https://gmgn.ai/external-res/51f2a389219f83c23a9dade0353be900.webp",
    "symbol": "ZTHYX",
    "name": "Zenthyx",
    "trans_symbol": "",
    "trans_name": "",
    "launchpad": "Pump.fun",
    "launchpad_platform": "Pump.fun",
    "creation_tool": "",
    "exchange": "pump",
    "creator_token_status": "creator_hold",
    "dev_token_burn_amount": 0,
    "dev_token_burn_ratio": 0,
    "progress": 0.3882409520360572,
    "total_supply": 1000000000,
    "usd_market_cap": 11691.279,
    "market_cap": 11691.279,
    "swaps_1h": 79,
    "volume_1h": 7139.8625227,
    "top_10_holder_rate": 0.2286,
    "creator_balance_rate": 0.034199203154141,
    "rat_trader_amount_rate": 0,
    "bundler_trader_amount_rate": 0.167,
    "renowned_count": 0,
    "bot_degen_rate": 28,
    "start_live_timestamp": 0,
    "end_live_timestamp": 0,
    "sniper_count": 5,
    "bot_degen_count": 28,
    "holder_count": 45,
    "liquidity": 17797.6800138408,
    "creator": "5QepAVinsAjbAm8uSVoCQH9xHG8KiYdQXPNnzp4J5oAf",
    "creator_created_open_count": 0,
    "creator_created_open_ratio": 0,
    "creator_created_count": 2,
    "fund_from": "FixedFloat Exchange",
    "fund_from_ts": 1760108454,
    "rug_ratio": 0,
    "buys_1h": 60,
    "sells_1h": 19,
    "swaps_1m": 79,
    "buys_1m": 60,
    "sells_1m": 19,
    "net_buy_1m": 2595.785626648,
    "net_buy_1h": 2595.785626648,
    "created_timestamp": 1760110267,
    "open_timestamp": 0,
    "buy_tips": 0,
    "total_fee": 0.277522168,
    "priority_fee": 0.041567109,
    "tip_fee": 0.11547464,
    "new_wallet_volume": 0,
    "entrapment_ratio": 0,
    "is_wash_trading": False,
    "renounced_mint": True,
    "renounced_freeze_account": True,
    "burn_status": "burn",
    "dev_team_hold_rate": 0.0342,
    "suspected_insider_hold_rate": 0,
    "is_token_live": False,
    "top70_sniper_hold_rate": 0.0342,
    "has_at_least_one_social": True,
    "twitter_is_tweet": False,
    "twitter": "Zenthyx_token",
    "website": "https://zenthyx.pro",
    "telegram": "https://t.me/Zenthyx_sol",
    "dexscr_ad": False,
    "dexscr_update_link": False,
    "dexscr_trending_bar": False,
    "dexscr_boost_fee": 0,
    "cto_flag": False,
    "offchain": False,
    "twitter_rename_count": 1,
    "twitter_del_post_token_count": 0,
    "twitter_create_token_count": 0,
    "tcid": "",
    "image_dup": 0,
    "status": 0,
    "tg_call_count": 0,
    "fresh_wallet_rate": 0.0025,
    "trade_fee": 0.120480419,
    "volume_1m": 7139.8625227,
    "twitter_dup": 1,
    "telegram_dup": 1,
    "website_dup": 1,
    "complete_timestamp": 0,
    "complete_cost_time": -1760110267,
    "_first_seen": "2025-10-10 16:31:42"
}

# Test the filter
passes, reason = advanced_token_filter(token_data, min_market_cap=10000, max_age_seconds=200000)
print(f"Passes filter: {passes}")
print(f"Reason: {reason}")