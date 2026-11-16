import os
import telebot
import requests
import time
import threading
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found!")
    sys.exit(1)

# Tumhari sahi ID
OWNER_ID = 8750078925
OWNER_USERNAME = "@ahadtry17"
GROUP_JOIN_LINK = "https://t.me/"

bot = telebot.TeleBot(BOT_TOKEN)
like_tracker = {}
app = Flask(__name__)

def reset_limits():
    while True:
        try:
            now_utc = datetime.utcnow()
            next_reset = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            sleep_seconds = (next_reset - now_utc).total_seconds()
            time.sleep(sleep_seconds)
            like_tracker.clear()
            logger.info("✅ Daily limits reset")
        except Exception as e:
            logger.error(f"Error in reset: {e}")

def call_api(region, uid):
    # NOTE: Yahan asli Like API ka link chahiye, abhi demo link hai
    url = f"https://your-free-fire-like-api-domain/like?uid={uid}&server_name={region}"
    try:
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            return {"error": "Maximum likes reached for today. Try again tomorrow."}
        return response.json()
    except Exception:
        return {"error": "API Failed. Please try again later."}

def get_user_limit(user_id):
    if user_id == OWNER_ID:
        return 999999999
    return 1

threading.Thread(target=reset_limits, daemon=True).start()

@app.route('/')
def home():
    return jsonify({'status': 'Bot is running', 'bot': 'Free Fire Likes Bot', 'health': 'OK'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return '', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return '', 500

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    if user_id not in like_tracker:
        like_tracker[user_id] = {"used": 0, "last_used": datetime.now() - timedelta(days=1)}
    bot.reply_to(message, "✅ You're verified! Use /like to send likes.", parse_mode="Markdown")

@bot.message_handler(commands=['like'])
def handle_like(message):
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) != 3:
        bot.reply_to(message, "❌ Format: `/like server_name uid`", parse_mode="Markdown")
        return
    region, uid = args[1], args[2]
    if not region.isalpha() or not uid.isdigit():
        bot.reply_to(message, "⚠️ Invalid input. Use: `/like server_name uid`", parse_mode="Markdown")
        return
    threading.Thread(target=process_like, args=(message, region, uid)).start()

def process_like(message, region, uid):
    user_id = message.from_user.id
    now_utc = datetime.utcnow()
    usage = like_tracker.get(user_id, {"used": 0, "last_used": now_utc - timedelta(days=1)})
    if usage["last_used"].date() < now_utc.date():
        usage["used"] = 0
    max_limit = get_user_limit(user_id)
    if usage["used"] >= max_limit:
        bot.reply_to(message, "⚠️ You have exceeded your daily request limit!")
        return
    processing_msg = bot.reply_to(message, "⏳ Please wait... Sending likes...")
    response = call_api(region, uid)
    if "error" in response:
        bot.edit_message_text(chat_id=processing_msg.chat.id, message_id=processing_msg.message_id, text=f"⚠️ API Error: {response['error']}")
        return
    if not isinstance(response, dict) or response.get("status") != 1:
        bot.edit_message_text(chat_id=processing_msg.chat.id, message_id=processing_msg.message_id, text="❌ UID has already received its max amount of likes. Try another UID or after 24 hrs.")
        return
    try:
        player_name = response.get("PlayerNickname", "N/A")
        player_uid = str(response.get("UID", uid)).strip()
        region_out = str(response.get("Region", "N/A"))
        likes_before = str(response.get("LikesbeforeCommand", "N/A"))
        likes_after = str(response.get("LikesafterCommand", "N/A"))
        likes_given = str(response.get("LikesGivenByAPI", "N/A"))
        usage["used"] += 1
        usage["last_used"] = now_utc
        like_tracker[user_id] = usage
        response_text = f"✅ *Request Processed Successfully*\n\n👤 *Name:* `{player_name}`\n🆔 *UID:* `{player_uid}`\n🌍 *Region:* `{region_out}`\n🤡 *Likes Before:* `{likes_before}`\n📈 *Likes Added:* `{likes_given}`\n🗿 *Total Likes Now:* `{likes_after}`\n🔐 *Remaining:* `{max_limit - usage['used']}`\n👑 *Credit:* {OWNER_USERNAME}"
        bot.edit_message_text(chat_id=processing_msg.chat.id, message_id=processing_msg.message_id, text=response_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in process_like: {e}")
        bot.reply_to(message, "⚠️ Something went wrong.")

@bot.message_handler(commands=["remain"])
def owner_commands(message):
    if message.from_user.id != OWNER_ID:
        return
    lines = ["📊 *Remaining Daily Requests Per User:*"]
    if not like_tracker:
        lines.append("❌ No users have used the bot yet today.")
    else:
        for uid, usage in like_tracker.items():
            limit = get_user_limit(uid)
            used = usage.get("used", 0)
            limit_str = "Unlimited" if limit > 1000 else str(limit)
            lines.append(f"👤 `{uid}` ➜ {used}/{limit_str}")
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = f"📖 *Bot Commands:*\n\n🧑‍💻 `/like <region> <uid>` - Send likes\n🔰 `/start` - Start\n🆘 `/help` - Help\n\n📞 *Support:* {OWNER_USERNAME}"
    bot.reply_to(message, help_text, parse_mode="Markdown")

# === BOT START - Ye pehle missing tha ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()
    logger.info("🤖 Bot Starting with Polling...")
    bot.infinity_polling(skip_pending=True)