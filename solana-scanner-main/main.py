import json
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
import telebot
import requests

COINS_FILE = "coins.json"

import os

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", '8333389962:AAFfGjOmZr4bqPVfzRJUIZiP9SUVHwUq7iE')
BASE_API_URL = os.getenv("HELIOX_API_URL", "http://127.0.0.1:8000/api").rstrip('/')
API_URL = f"{BASE_API_URL}/get_chat_ids/"

bot = telebot.TeleBot(API_TOKEN)

def format_number(value):
    num = float(value)
    return f"{round(num):,}"

def broadcast_msg(chat_ids, coin_data=None):
    for final_data in coin_data:
        final_data = final_data[0] if isinstance(final_data, list) else final_data
        message = f"*New Token Detection (Solana)*\n\n"
        message += f"*Token Name*: `{final_data['name']}`\n"
        message += f"*Token Symbol*: ${final_data['symbol']}\n"
        message += f"*Market Cap*: ${format_number(final_data['usd_market_cap'])}\n"
        message += f"*CA*: `{final_data['address']}`\n"
        message += f"\n*Launched On*: {final_data['launchpad']}\n"

        if final_data.get('dex_paid'):
            message += f"\n*Dex Paid Verified*\n"

        message += f"```\nRESEARCH GUIDELINE:\n"
        message += f"1. Verify liquidity lock status\n"
        message += f"2. Check developer wallet distribution\n"
        message += f"3. Confirm mint authority is renounced\n"
        message += f"4. Review Twitter and website presence\n```"

        message = message.replace('.', ' ')

        coin_logo = final_data.get('logo')
        markup = telebot.types.InlineKeyboardMarkup()
        dev_contact_url = f"https://trade.padre.gg/trade/solana/{final_data['pool_address']}"
        btn1 = telebot.types.InlineKeyboardButton(text="View Coin in PADRE", url=dev_contact_url)
        btn2 = telebot.types.InlineKeyboardButton(text='Rug Check', url=f"https://rugcheck.xyz/tokens/{final_data['address']}")

        # markup.add(telebot.types.InlineKeyboardButton(
        #     text='🤖 Analyze Coin Using AI',
        #     callback_data=f"analyze:{final_data['address']}"
        # ))
        markup.row(btn1, btn2)

        for chat_id in chat_ids:
            bot.send_photo(
                chat_id,
                coin_logo,
                caption=message,
                parse_mode='MarkdownV2',
                reply_markup=markup
            )


def is_domain_only(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in ("http", "https")
        and parsed.netloc
        and parsed.path in ("", "/")
        and not parsed.query
        and not parsed.fragment
    )


def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)


def load_json(filename):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def passes_filters(coin):
    try:
        base_info = coin.get("baseTokenInfo", {})
        social = base_info.get("social", {})
        if (
            15000 < float(coin.get("marketCap", 0)) < 40000
            and float(coin.get("liquidUsd", 0)) > 12000
            and float(base_info.get("top10HoldersPercent", 0)) < 30
            and 0 < float(base_info.get("devHoldPercent", 0)) < 20
            and float(base_info.get("sniperHoldPercent", 0)) < 40
            and float(base_info.get("insiderHoldPercent", 0)) < 30
            and float(base_info.get("devBundleHoldPercent", 0)) < 20
            and float(base_info.get("phishingHoldPercent", 0)) < 10
            and float(base_info.get("bundleHoldPercent", 0)) < 20
            and float(coin.get('report').get('sellCount') > 300)
        ):
            if social and social.get("twitter") and social.get("website") and is_domain_only(social.get("website")):
                return True
        return False
    except Exception:
        return False


def run():
    # Reset JSON file at the start
    # save_json(COINS_FILE, [])

    stored_addresses = load_json(COINS_FILE)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        def handle_response(response):
            if "api.mevx.io/api/v1/flash/pools?chain=sol" in response.url:
                try:
                    data = response.json()
                    for pools in data:
                        for coin in data[pools]:
                            base_token = coin.get("baseToken")
                            coin_name = coin.get("baseTokenInfo", {}).get("name", "Unknown")
                            coin_address = coin.get("poolAddress")

                            # ✅ Only store addresses of coins that pass filters
                            if passes_filters(coin) and base_token not in stored_addresses:
                                stored_addresses.append(base_token)
                                save_json(COINS_FILE, stored_addresses)

                                print(f"Filtered coin: {coin_name} ({coin_address})")

                                # Fetch chat IDs
                                try:
                                    response = requests.get(API_URL)
                                    response.raise_for_status()
                                    chat_ids = response.json().get("chat_ids", [])
                                except requests.exceptions.RequestException as e:
                                    print("Error fetching chat IDs:", e)
                                    chat_ids = []

                                # Prepare coin data for broadcast
                                coin_data = {
                                    "name": coin.get("baseTokenInfo", {}).get("name"),
                                    "symbol": coin.get("baseTokenInfo", {}).get("symbol"),
                                    "usd_market_cap": coin.get("marketCap"),
                                    "address": coin.get("baseToken"),
                                    "pool_address": coin.get("poolAddress"),
                                    "logo": coin.get("baseTokenInfo", {}).get("logoUri"),
                                    "launchpad": coin.get("factory"),
                                    "dex_paid": coin.get("baseTokenInfo").get("dexPaid")
                                }

                                # Save into unified Heliox system
                                try:
                                    requests.post(f"{BASE_API_URL}/save_coin/", json={"ca": base_token, "coin_info": coin_data}, timeout=5)
                                except Exception as e:
                                    print(f"Error saving to Heliox API: {e}")

                                broadcast_msg(chat_ids, [coin_data])

                except Exception as e:
                    print(f"Error processing response: {e}")

        page.on("response", handle_response)
        page.goto("https://mevx.io/", timeout=500000)

        print("Watching for new coins... Press Ctrl+C to stop")
        try:
            while True:
                page.wait_for_timeout(30000)
        except KeyboardInterrupt:
            print("Stopping...")
            browser.close()


if __name__ == "__main__":
    run()
