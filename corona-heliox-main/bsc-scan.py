import json
import time
import requests
import telebot
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

# --- Config ---
API_KEYWORD = "vas/api/v1/rank/bsc"
FILTERED_FILE = Path("filtered_coins.json")
RESEARCHED_FILE = Path("researched_coins.json")

API_URL = "http://localhost:8000/api/get_chat_ids/"
chat_ids = []

try:
    # Make the API call
    response = requests.get(API_URL)

    # Raise an error if the request failed
    response.raise_for_status()

    # Parse the JSON response
    data = response.json()

    # Extract chat_ids (assuming it's a list in the response)
    chat_ids = data.get("chat_ids", [])

    print("Chat IDs:", chat_ids)

except requests.exceptions.RequestException as e:
    print("Error during API call:", e)

API_TOKEN = '8333389962:AAFfGjOmZr4bqPVfzRJUIZiP9SUVHwUq7iE'

bot = telebot.TeleBot(API_TOKEN)

for id in chat_ids:
    bot.send_message(id, "🤖 Bot is now online and monitoring new coins! [BSC]")

def format_number(value):
    # Convert to float first (handles both string and numeric input)
    num = float(value)
    # Round to nearest integer and format with commas
    return f"{round(num):,}"

def broadcast_msg(chat_ids, coin_data=None) :
    for final_data in coin_data :
        print(f'Final Data: {final_data}')
        print(f'Chat Ids: {chat_ids}')

        print(type(final_data))
        print(type(chat_ids))

        final_data = final_data[0] if isinstance(final_data, list) else final_data
        message = f"*New Token Detection (BSC)*\n\n"
        message += f"*Token Name*: `{final_data['name']}`\n"
        message += f"*Token Symbol*: ${final_data['symbol']}\n"
        message += f"*Market Cap*: ${format_number(final_data['usd_market_cap'])}\n"
        message += f"*CA*: `{final_data['address']}`\n"
        message += f"*Launched On*: {final_data['launchpad']}\n"

        if final_data.get('dexscr_ad'):
            message += f"*Dex Paid Verified*\n"

        if final_data.get('start_live_timestamp') != 0 :
            message += f"Live Stream Active\n"

        if final_data.get('dexscr_boost_fee') and final_data.get('dexscr_boost_fee') > 0:
            message += f"DexScreener Boost: {final_data.get('dexscr_boost_fee')}\n"

        message += f"```\nRESEARCH GUIDELINE:\n"
        message += f"1. Verify chart and candle structure\n"
        message += f"2. Verify team Twitter activity\n"
        message += f"3. Confirm website functionality\n"
        message += f"4. Review tokenomics and holder spread\n"
        message += f"5. Confirm liquidity is locked\n"
        message += f"6. Check if dev has renounced mint\n"
        message += f"7. Check market cap vs volume ratio\n```"

        message = message.replace('.', ' ')

        coin_logo = final_data.get('logo')
        markup = telebot.types.InlineKeyboardMarkup()
        dev_contact_url = f"https://trade.padre.gg/trade/bsc/{final_data['pool_address']}"
        markup.add(telebot.types.InlineKeyboardButton(text="View Coin in PADRE", url=dev_contact_url))
        markup.add(telebot.types.InlineKeyboardButton(
            text='🤖 Analyze Coin Using AI', 
            callback_data=f"analyze:{final_data['address']}"
        ))

        for chat_id in chat_ids :
            bot.send_photo(
                chat_id,
                coin_logo,
                caption=message,
                parse_mode='MarkdownV2',
                reply_markup=markup
            )

def save_coin(coin):
    API_URL = "http://localhost:8000/api/save_coin/"
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(API_URL, headers=headers, json={
            "ca": coin.get('address'),
            "coin_info": coin
        })
        response.raise_for_status()
        print(f"Coin {coin.get('address')} saved successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error saving coin {coin.get('address')}: {e}")

# --- Helpers ---
def is_domain_only(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    if parsed.path not in ("", "/"):
        return False
    if parsed.query or parsed.fragment:
        return False
    return True


def filter_coins(block):
    """Apply filtering criteria to a single captured API response block."""
    filtered_coins = []
    researched_coins = []
    coins_analyzed = 0

    try:
        new_creations = block['data']['data']['new_creation']
        pump = block['data']['data']['pump']
        completed = block['data']['data']['completed']
    except Exception:
        return [], [], 0  # skip malformed blocks

    for coin in new_creations + pump + completed:
        coins_analyzed += 1
        researched_coins.append(coin)  # add every coin to researched list

        if (coin.get('liquidity', 0) > 10000 
                and coin.get('twitter') 
                and coin.get('website') 
                and is_domain_only(coin['website']) 
                and coin.get('liquidity', 0) > 12500 
                and coin.get('website') 
                and coin.get('image_dup', 99) < 3
                and coin.get('twitter_rename_count', 99) < 2 
                and coin.get('twitter_del_post_token_count', 99) < 5 
                and coin.get('twitter_create_token_count', 99) < 5 
                and coin.get('twitter_is_tweet') == False 
                and coin.get('is_wash_trading') == False 
                and coin.get('creator_created_count', 99) < 5 
                and coin.get('website_dup', 99) < 3
                and coin.get('rug_ratio', 1) < 0.8
                and coin.get('entrapment_ratio', 1) < 0.9
                # and coin.get('renounced_mint') == True
                # ✅ New conditions to ensure dev hasn’t sold
                and coin.get('creator_token_status') == "creator_hold"
                and coin.get('dev_team_hold_rate', 0) > 0
                and coin.get('market_cap') > 15000
                and coin.get('bundler_trader_amount_rate') < 0.2
                and coin.get('dev_team_hold_rate') < 0.20
                and coin.get('top70_sniper_hold_rate') < 0.3
                # and coin.get('volume_1m') > 50
                and coin.get('top_10_holder_rate') < 0.4
                and coin.get('twitter_dup', 0) < 2
            ):
            filtered_coins.append(coin)

    return filtered_coins, researched_coins, coins_analyzed


# --- Main Playwright Runner ---
def run(playwright):
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # Initialize output files
    if not FILTERED_FILE.exists():
        FILTERED_FILE.write_text("[]")
    if not RESEARCHED_FILE.exists():
        RESEARCHED_FILE.write_text("[]")

    # Load existing data
    filtered_existing = json.loads(FILTERED_FILE.read_text())
    researched_existing = json.loads(RESEARCHED_FILE.read_text())

    # In-memory sets for deduplication
    seen_addresses = {coin["address"] for coin in filtered_existing}
    researched_addresses = {coin["address"] for coin in researched_existing}

    def handle_response(response):
        nonlocal seen_addresses, researched_addresses
        url = response.url
        if API_KEYWORD in url:
            try:
                # --- Parse response safely ---
                try:
                    data = response.json()
                except Exception as e:
                    print(f"[!] Failed to parse JSON: {e}")
                    try:
                        data = {"raw_text": response.text}  # .text is property, not callable
                    except Exception as e2:
                        print(f"[!] Failed to read raw text: {e2}")
                        data = {"raw_text": None}

                block = {
                    "timestamp": time.time(),
                    "url": url,
                    "status": getattr(response, "status", None),
                    "data": data
                }

                # --- Filter coins ---
                try:
                    filtered, researched, analyzed = filter_coins(block)
                except Exception as e:
                    print(f"[!] Error in filter_coins: {e}")
                    filtered, researched, analyzed = [], [], 0

                # --- Update researched list ---
                try:
                    new_researched = []
                    for coin in researched:
                        try:
                            addr = coin.get("address") if isinstance(coin, dict) else None
                            if addr and addr not in researched_addresses:
                                researched_addresses.add(addr)
                                coin["_first_seen"] = time.strftime('%Y-%m-%d %H:%M:%S')
                                new_researched.append(coin)
                        except Exception as inner_e:
                            print(f"[!] Error processing researched coin: {inner_e}")

                    if new_researched:
                        try:
                            researched_existing.extend(new_researched)
                            RESEARCHED_FILE.write_text(json.dumps(researched_existing, indent=2))
                            print(f"📘 Added {len(new_researched)} new researched coins.")
                        except Exception as file_e:
                            print(f"[!] Failed to update researched file: {file_e}")
                except Exception as e:
                    print(f"[!] Error updating researched list: {e}")

                # --- Update filtered list ---
                try:
                    new_filtered = []
                    for coin in filtered:
                        try:
                            addr = coin.get("address") if isinstance(coin, dict) else None
                            if addr and addr not in seen_addresses:
                                seen_addresses.add(addr)
                                coin["_first_seen"] = time.strftime('%Y-%m-%d %H:%M:%S')
                                new_filtered.append(coin)
                                save_coin(coin)
                        except Exception as inner_e:
                            print(f"[!] Error processing filtered coin: {inner_e}")

                    if new_filtered:
                        try:
                            filtered_existing.extend(new_filtered)
                            FILTERED_FILE.write_text(json.dumps(filtered_existing, indent=2))
                            try:
                                broadcast_msg(chat_ids, new_filtered)  # Broadcast only the latest coin
                            except Exception as bcast_e:
                                print(f"[!] Broadcast failed: {bcast_e}")
                            print(f"✅ {len(new_filtered)} NEW coins passed filter.")
                        except Exception as file_e:
                            print(f"[!] Failed to update filtered file: {file_e}")
                    else:
                        print(f"🔎 {analyzed} coins analyzed, no new filtered coins.")
                except Exception as e:
                    print(f"[!] Error updating filtered list: {e}")

            except Exception as e:
                print("Fatal error in response handling:", e)

    page.on("response", handle_response)
    page.goto("https://gmgn.ai/?chain=bsc")

    print("👀 Watching gmgn.ai for API responses... Press Ctrl+C to stop.")
    try:
        while True:
            page.wait_for_timeout(1000)
    except KeyboardInterrupt:
        print("🛑 Stopped watching.")
        print(f"📊 Total unique researched coins: {len(researched_addresses)}")
        print(f"📊 Total unique filtered coins: {len(seen_addresses)}")
        browser.close()


if __name__ == "__main__":
    with sync_playwright() as p:
        run(p)