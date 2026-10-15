import os
import telebot
import requests

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8333389962:AAFfGjOmZr4bqPVfzRJUIZiP9SUVHwUq7iE")
BASE_API_URL = os.getenv("HELIOX_API_URL", "http://127.0.0.1:8000/api").rstrip('/')

bot = telebot.TeleBot(API_TOKEN)


def analyze_coin(chat_id, address):
    url = f"{BASE_API_URL}/scan/"
    payload = {
        "ca": address,
        "chat_id": chat_id
    }
    try:
        resp = requests.post(url, json=payload, timeout=60)
        if resp.ok:
            return resp.json()
        else:
            bot.send_message(chat_id, f"Error: Scan returned status {resp.status_code}")
    except Exception as e:
        bot.send_message(chat_id, f"Could not connect to Heliox API ({e})")


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    chat_id = message.chat.id
    display = f"@{user.username}" if user and user.username else "Trader"

    # Register chat ID with API
    try:
        requests.post(f"{BASE_API_URL}/register/", json={
            "username": user.username or user.first_name,
            "chat_id": str(chat_id)
        }, timeout=5)
    except Exception as e:
        print(f"[Register error]: {e}")

    text = (
        f"HELIOX AI Screener & Alerts\n\n"
        f"Welcome, {display}!\n"
        f"Your Chat ID: {chat_id}\n\n"
        f"Commands:\n"
        f"/sync <6-digit-code> - Link with your Web SaaS account\n"
        f"/scan <address> - Scan any Solana or BSC contract address\n"
        f"/help - View documentation"
    )

    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("Open Web Screener", url="http://127.0.0.1:8000/"),
        telebot.types.InlineKeyboardButton("Community", url="https://t.me/heliox_group")
    )

    bot.send_message(chat_id, text, reply_markup=markup)


@bot.message_handler(commands=['sync'])
def sync_account(message):
    chat_id = message.chat.id
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /sync <6-digit-code>\nFind your code on your Heliox Web profile.")
        return

    code = parts[1].strip()
    try:
        resp = requests.post(f"{BASE_API_URL}/sync_tg/", json={
            "code": code,
            "chat_id": str(chat_id),
            "username": message.from_user.username
        }, timeout=10)

        if resp.ok:
            data = resp.json()
            bot.reply_to(message, f"Success: {data.get('message', 'Linked successfully!')}")
        else:
            bot.reply_to(message, f"Failed: {resp.json().get('error', 'Invalid sync code')}")
    except Exception as e:
        bot.reply_to(message, f"Error contacting Heliox API: {e}")


@bot.message_handler(commands=['scan'])
def scan_command(message):
    chat_id = message.chat.id
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /scan <token_contract_address>")
        return

    ca = parts[1].strip()
    bot.send_message(chat_id, f"Scanning {ca[:8]}... Please wait.")
    analyze_coin(chat_id, ca)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data.startswith("analyze:"):
        _, addr = call.data.split(":", 1)
        analyze_coin(call.message.chat.id, addr)


if __name__ == '__main__':
    print("Heliox Telegram Bot is running...")
    bot.polling(non_stop=True)