import telebot

chat_ids = ['8424303757', '1819978020', '7604597447']

API_TOKEN = '8333389962:AAFfGjOmZr4bqPVfzRJUIZiP9SUVHwUq7iE'

bot = telebot.TeleBot(API_TOKEN)

img = "https://github.com/Phantom-whine/static/blob/main/Gemini_Generated_Image_8k2t618k2t618k2t.png?raw=true"

message = """We didn't find any good coin yesterday. Not placing a trade can be a good trade - staying patient and preserving capital is a win ✅"""

for id in chat_ids :
    bot.send_photo(id, img, caption=message)