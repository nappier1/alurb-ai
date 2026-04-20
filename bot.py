import telebot
import time
import os
import json
import threading
import logging
from datetime import datetime, timedelta
import requests
from keep_alive import keep_alive

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8341823550:AAFDfFvU14oJ2qy8gT0CDnO7O9L4aJRhOHU')
PORT = int(os.environ.get('PORT', 8080))

# OpenRouter AI Configuration
AI_CONFIG = {
    "api_key": "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",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "deepseek/deepseek-chat-v3-0324:free",
    "language": "English"
}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Data storage
DATA_DIR = "bot_data"
os.makedirs(DATA_DIR, exist_ok=True)

PREMIUM_USERS = {}
OWNERS = []
BOT_START_TIME = time.time()
GROUP_IDS = set()
USER_CONVERSATIONS = {}

# Trial System - 2 Hours Free Trial
TRIAL_USERS = {}
TRIAL_HOURS = 2

# Premium Plans
PREMIUM_PLANS = {
    "2hours": {"name": "2 Hours Trial", "hours": 2, "price": "FREE (Auto-activated)"},
    "daily": {"name": "Daily", "days": 1, "price": "$0.99"},
    "weekly": {"name": "Weekly", "days": 7, "price": "$2.99"},
    "monthly": {"name": "Monthly", "days": 30, "price": "$7.99"},
    "lifetime": {"name": "Lifetime", "days": 36500, "price": "$49.99"}
}

def load_data():
    global PREMIUM_USERS, OWNERS, GROUP_IDS, TRIAL_USERS
    try:
        with open(f"{DATA_DIR}/premium.json", "r") as f:
            PREMIUM_USERS = json.load(f)
    except:
        PREMIUM_USERS = {}
    try:
        with open(f"{DATA_DIR}/owners.json", "r") as f:
            OWNERS = json.load(f)
    except:
        OWNERS = []
    try:
        with open(f"{DATA_DIR}/groups.json", "r") as f:
            GROUP_IDS = set(json.load(f))
    except:
        GROUP_IDS = set()
    try:
        with open(f"{DATA_DIR}/trials.json", "r") as f:
            TRIAL_USERS = json.load(f)
    except:
        TRIAL_USERS = {}

def save_data():
    with open(f"{DATA_DIR}/premium.json", "w") as f:
        json.dump(PREMIUM_USERS, f)
    with open(f"{DATA_DIR}/owners.json", "w") as f:
        json.dump(OWNERS, f)
    with open(f"{DATA_DIR}/groups.json", "w") as f:
        json.dump(list(GROUP_IDS), f)
    with open(f"{DATA_DIR}/trials.json", "w") as f:
        json.dump(TRIAL_USERS, f)

def is_owner(user_id):
    return str(user_id) in OWNERS

def is_premium(user_id):
    user_id = str(user_id)
    if user_id in PREMIUM_USERS:
        premium_data = PREMIUM_USERS[user_id]
        if "expires" in premium_data and premium_data["expires"]:
            expiry = datetime.fromisoformat(premium_data["expires"])
            if expiry > datetime.now():
                return True
            else:
                del PREMIUM_USERS[user_id]
                save_data()
                return False
        return True
    return False

def is_trial_active(user_id):
    user_id = str(user_id)
    if user_id in TRIAL_USERS:
        trial_data = TRIAL_USERS[user_id]
        trial_start = datetime.fromisoformat(trial_data["start_time"])
        trial_end = trial_start + timedelta(hours=TRIAL_HOURS)
        if datetime.now() < trial_end:
            return True
        else:
            del TRIAL_USERS[user_id]
            save_data()
            return False
    return False

def start_trial(user_id):
    user_id = str(user_id)
    if user_id not in TRIAL_USERS and not is_premium(user_id):
        TRIAL_USERS[user_id] = {
            "start_time": datetime.now().isoformat(),
            "trial_type": "2hours"
        }
        save_data()
        return True
    return False

def get_trial_time_left(user_id):
    user_id = str(user_id)
    if user_id in TRIAL_USERS:
        trial_start = datetime.fromisoformat(TRIAL_USERS[user_id]["start_time"])
        trial_end = trial_start + timedelta(hours=TRIAL_HOURS)
        time_left = trial_end - datetime.now()
        if time_left.total_seconds() > 0:
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            return f"{hours}h {minutes}m"
    return None

def get_premium_expiry(user_id):
    user_id = str(user_id)
    if user_id in PREMIUM_USERS:
        premium_data = PREMIUM_USERS[user_id]
        if "expires" in premium_data and premium_data["expires"]:
            return datetime.fromisoformat(premium_data["expires"])
    return None

def check_premium_access(user_id):
    if is_owner(user_id):
        return True
    if is_premium(user_id):
        return True
    if is_trial_active(user_id):
        return True
    return False

def ai_chat(messages, user_id):
    try:
        headers = {
            "Authorization": f"Bearer {AI_CONFIG['api_key']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://t.me/alurb_bot",
            "X-Title": "Alurb Telegram Bot"
        }
        payload = {
            "model": AI_CONFIG["model"],
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 500
        }
        response = requests.post(
            f"{AI_CONFIG['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=45
        )
        if response.status_code == 200:
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
        return "❌ AI service temporarily unavailable."
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return "❌ Error connecting to AI service."

load_data()
keep_alive()

# ==================== START COMMAND ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name or "User"
    
    # Auto-start trial for new users
    trial_started = False
    if not is_owner(user_id) and not is_premium(user_id) and not is_trial_active(user_id):
        trial_started = start_trial(user_id)
    
    # Build status line
    if is_owner(user_id):
        status_line = "👑 <b>Owner</b> (Full Access)"
    elif is_premium(user_id):
        expiry = get_premium_expiry(user_id)
        if expiry:
            days_left = (expiry - datetime.now()).days
            status_line = f"💎 <b>Premium</b> ({days_left} days left)"
        else:
            status_line = "💎 <b>Premium</b> (Lifetime)"
    elif is_trial_active(user_id):
        time_left = get_trial_time_left(user_id)
        status_line = f"🎁 <b>Free Trial</b> ({time_left} left)"
    else:
        status_line = "🔒 <b>Free User</b>"
    
    # Trial activation message
    trial_msg = ""
    if trial_started:
        trial_msg = "\n\n🎉 <b>2-HOUR FREE TRIAL ACTIVATED!</b>\nEnjoy full premium access!"

    welcome_text = f"""
╔══════════════════════╗
     🤖 <b>WELCOME TO ALURB BOT</b> 🤖
╚══════════════════════╝

👋 Hello <b>{first_name}</b>!

📊 <b>Your Status:</b> {status_line}{trial_msg}

🔰 <b>Bot Features:</b>
• 24/7 Online Status
• AI Assistant (DeepSeek V3)
• Premium Attack Tools
• Group Management

🎁 <b>FREE TRIAL INCLUDES:</b>
• {TRIAL_HOURS} hours full premium access
• /silencer - Device silencer
• /xdelay - Heavy delay
• /crash - System crash
• /ask - AI questions

📌 <b>Commands:</b>
/help - All commands
/status - Your status
/trial - Free trial
/premium - Upgrade
/ask - Ask AI

━━━━━━━━━━━━━━━━━━━━━━
© dev_nappier 😂🫡
    """
    bot.reply_to(message, welcome_text, parse_mode="HTML")
    
    if message.chat.type in ['group', 'supergroup']:
        GROUP_IDS.add(str(message.chat.id))
        save_data()

# ==================== TRIAL COMMAND ====================

@bot.message_handler(commands=['trial'])
def trial_command(message):
    user_id = str(message.from_user.id)
    
    if is_owner(user_id):
        bot.reply_to(message, "👑 You're an Owner - permanent access!", parse_mode="HTML")
        return
    
    if is_premium(user_id):
        bot.reply_to(message, "💎 You're already a Premium user!", parse_mode="HTML")
        return
    
    if is_trial_active(user_id):
        time_left = get_trial_time_left(user_id)
        bot.reply_to(message, f"""
🎁 <b>YOUR TRIAL IS ACTIVE</b>

⏰ Time Remaining: <b>{time_left}</b>
✅ Full Premium Access: <b>ENABLED</b>

Commands:
• /silencer - Device silencer
• /xdelay - Heavy delay
• /crash - System crash
• /ask - AI Assistant

💎 Upgrade: /premium
        """, parse_mode="HTML")
        return
    
    if start_trial(user_id):
        bot.reply_to(message, f"""
🎉 <b>FREE TRIAL ACTIVATED!</b>

⏰ Duration: <b>{TRIAL_HOURS} HOURS</b>
✅ Full Premium Access: <b>ENABLED</b>

🎁 You now have access to:
• /silencer - Device silencer
• /xdelay - Heavy delay  
• /crash - System crash
• /ask - Unlimited AI

⏰ Trial expires in {TRIAL_HOURS} hours
💎 /premium - Upgrade options

Enjoy! 🚀
        """, parse_mode="HTML")
    else:
        bot.reply_to(message, "❌ Unable to start trial. Contact @dev_nappier")

# ==================== PREMIUM COMMAND ====================

@bot.message_handler(commands=['premium'])
def premium_command(message):
    user_id = str(message.from_user.id)
    
    if is_owner(user_id):
        bot.reply_to(message, "👑 <b>Owner Status:</b> Permanent premium access!", parse_mode="HTML")
        return
    
    if is_premium(user_id):
        expiry = get_premium_expiry(user_id)
        if expiry:
            days_left = (expiry - datetime.now()).days
            bot.reply_to(message, f"""
💎 <b>PREMIUM STATUS: ACTIVE</b>

📅 Days Remaining: <b>{days_left}</b>
🔓 All Features: <b>UNLOCKED</b>
            """, parse_mode="HTML")
        else:
            bot.reply_to(message, """
💎 <b>PREMIUM STATUS: LIFETIME</b>

🔓 All Features: <b>UNLOCKED</b>
            """, parse_mode="HTML")
        return
    
    trial_status = ""
    if is_trial_active(user_id):
        time_left = get_trial_time_left(user_id)
        trial_status = f"\n🎁 Trial Active: {time_left} remaining"
    else:
        trial_status = "\n🎁 Free Trial: /trial (2 hours)"
    
    bot.reply_to(message, f"""
╔══════════════════════╗
     💎 <b>PREMIUM PLANS</b> 💎
╚══════════════════════╝{trial_status}

━━━━━━━━━━━━━━━━━━━━━━
📅 <b>DAILY</b> - $0.99
📅 <b>WEEKLY</b> - $2.99
📅 <b>MONTHLY</b> - $7.99
📅 <b>LIFETIME</b> - $49.99

━━━━━━━━━━━━━━━━━━━━━━
✨ <b>Premium Benefits:</b>
• Unlimited silencer attacks
• Unlimited XDelay attacks
• Crash attack access
• Unlimited AI questions
• Priority support

📩 <b>To Upgrade:</b>
👤 Contact: @dev_nappier
📧 premium@alurb-bot.com

💳 Crypto • PayPal • Bank Transfer

━━━━━━━━━━━━━━━━━━━━━━
© dev_nappier 😂🫡
    """, parse_mode="HTML")

# ==================== STATUS COMMAND ====================

@bot.message_handler(commands=['status'])
def status_command(message):
    user_id = str(message.from_user.id)
    
    uptime = time.time() - BOT_START_TIME
    days = int(uptime // 86400)
    hours = int((uptime % 86400) // 3600)
    minutes = int((uptime % 3600) // 60)
    
    if is_owner(user_id):
        user_status = "👑 Owner (Permanent)"
    elif is_premium(user_id):
        expiry = get_premium_expiry(user_id)
        if expiry:
            days_left = (expiry - datetime.now()).days
            user_status = f"💎 Premium ({days_left}d left)"
        else:
            user_status = "💎 Premium (Lifetime)"
    elif is_trial_active(user_id):
        time_left = get_trial_time_left(user_id)
        user_status = f"🎁 Trial ({time_left} left)"
    else:
        user_status = "🔒 Free"
    
    bot.reply_to(message, f"""
╔══════════════════════╗
       🤖 <b>BOT STATUS</b> 🤖
╚══════════════════════╝

📊 <b>System:</b>
━━━━━━━━━━━━━━━━━━━━━━
✅ Status: 24/7 Active
⏰ Uptime: {days}d {hours}h {minutes}m
👑 Owners: {len(OWNERS)}
💎 Premium: {len(PREMIUM_USERS)}
🎁 Trials: {len([t for t in TRIAL_USERS if is_trial_active(t)])}

👤 <b>Your Status:</b>
━━━━━━━━━━━━━━━━━━━━━━
{user_status}

🛠 <b>Info:</b>
━━━━━━━━━━━━━━━━━━━━━━
🤖 AI: DeepSeek Chat V3
🌐 Language: {AI_CONFIG['language']}

━━━━━━━━━━━━━━━━━━━━━━
© dev_nappier 😂🫡
    """, parse_mode="HTML")

# ==================== HELP COMMAND ====================

@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = str(message.from_user.id)
    
    if is_owner(user_id):
        user_level = "👑 Owner"
    elif is_premium(user_id):
        user_level = "💎 Premium"
    elif is_trial_active(user_id):
        user_level = f"🎁 Trial ({get_trial_time_left(user_id)})"
    else:
        user_level = "🔒 Free"
    
    bot.reply_to(message, f"""
╔══════════════════════╗
     📚 <b>COMMAND MENU</b> 📚
╚══════════════════════╝

𖤊───⪩ <b>FREE COMMANDS</b> ⪨───𖤊
✦ /start - Welcome message
✦ /help - This menu
✦ /status - Your status
✦ /trial - 2-hour free trial
✦ /premium - Premium plans
✦ /ask - AI Assistant
✦ /clearai - Clear AI history

𖤊───⪩ <b>PREMIUM COMMANDS</b> ⪨───𖤊
🔒 Requires Premium/Trial:
✦ /silencer - Device silencer
✦ /xdelay - Heavy delay
✦ /crash - System crash
✦ /cekidgrup - Get group ID

𖤊───⪩ <b>OWNER COMMANDS</b> ⪨───𖤊
👑 Owner Only:
✦ /addprem - Add premium
✦ /delprem - Remove premium
✦ /addowner - Add owner
✦ /delowner - Remove owner
✦ /listprem - Premium list
✦ /listidgrup - Group list

━━━━━━━━━━━━━━━━━━━━━━
👤 Your Level: <b>{user_level}</b>
🎁 Free Trial: /trial ({TRIAL_HOURS}h)
© dev_nappier 😂🫡
    """, parse_mode="HTML")

# ==================== OWNER COMMANDS ====================

@bot.message_handler(commands=['addprem'])
def add_premium(message):
    user_id = str(message.from_user.id)
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only!")
        return
    try:
        parts = message.text.split(' ')
        target_id = parts[1]
        plan = parts[2] if len(parts) > 2 else "monthly"
        plan_info = PREMIUM_PLANS.get(plan, PREMIUM_PLANS["monthly"])
        
        if "hours" in plan_info:
            expiry = datetime.now() + timedelta(hours=plan_info["hours"])
        else:
            expiry = datetime.now() + timedelta(days=plan_info.get("days", 30))
        
        PREMIUM_USERS[target_id] = {
            "added_by": user_id,
            "date": datetime.now().isoformat(),
            "expires": expiry.isoformat() if plan != "lifetime" else None,
            "plan": plan
        }
        if target_id in TRIAL_USERS:
            del TRIAL_USERS[target_id]
        save_data()
        
        expiry_text = expiry.strftime('%Y-%m-%d %H:%M') if plan != "lifetime" else "Lifetime"
        bot.reply_to(message, f"✅ Premium granted!\n👤 {target_id}\n📅 {plan_info['name']}\n⏰ {expiry_text}")
    except:
        bot.reply_to(message, "❌ Usage: /addprem <id> [2hours/daily/weekly/monthly/lifetime]")

@bot.message_handler(commands=['delprem'])
def del_premium(message):
    user_id = str(message.from_user.id)
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only!")
        return
    try:
        target_id = message.text.split(' ', 1)[1]
        if target_id in PREMIUM_USERS:
            del PREMIUM_USERS[target_id]
            save_data()
            bot.reply_to(message, f"✅ User {target_id} removed from premium!")
        else:
            bot.reply_to(message, f"❌ User {target_id} not found!")
    except:
        bot.reply_to(message, "❌ Usage: /delprem <user_id>")

@bot.message_handler(commands=['listprem'])
def list_premium(message):
    user_id = str(message.from_user.id)
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only!")
        return
    if PREMIUM_USERS:
        text = "<b>📋 PREMIUM USERS:</b>\n\n"
        for uid, data in PREMIUM_USERS.items():
            plan = data.get("plan", "unknown")
            if data.get("expires"):
                exp = datetime.fromisoformat(data["expires"])
                days = (exp - datetime.now()).days
                text += f"• <code>{uid}</code> - {plan} ({days}d left)\n"
            else:
                text += f"• <code>{uid}</code> - lifetime\n"
        bot.reply_to(message, text, parse_mode="HTML")
    else:
        bot.reply_to(message, "📋 No premium users!")

@bot.message_handler(commands=['addowner'])
def add_owner(message):
    user_id = str(message.from_user.id)
    if not is_owner(user_id) and len(OWNERS) > 0:
        bot.reply_to(message, "❌ Owner only!")
        return
    try:
        target_id = message.text.split(' ', 1)[1]
        if target_id not in OWNERS:
            OWNERS.append(target_id)
            save_data()
            bot.reply_to(message, f"✅ Owner added: {target_id}")
    except:
        bot.reply_to(message, "❌ Usage: /addowner <user_id>")

@bot.message_handler(commands=['delowner'])
def del_owner(message):
    user_id = str(message.from_user.id)
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only!")
        return
    try:
        target_id = message.text.split(' ', 1)[1]
        if target_id in OWNERS:
            OWNERS.remove(target_id)
            save_data()
            bot.reply_to(message, f"✅ Owner removed: {target_id}")
    except:
        bot.reply_to(message, "❌ Usage: /delowner <user_id>")

@bot.message_handler(commands=['listidgrup'])
def list_groups(message):
    if not is_owner(str(message.from_user.id)):
        bot.reply_to(message, "❌ Owner only!")
        return
    if GROUP_IDS:
        text = "<b>📋 GROUP IDs:</b>\n\n"
        for gid in GROUP_IDS:
            text += f"• <code>{gid}</code>\n"
        bot.reply_to(message, text, parse_mode="HTML")
    else:
        bot.reply_to(message, "📋 No groups!")

# ==================== PREMIUM COMMANDS ====================

@bot.message_handler(commands=['silencer'])
def silencer_attack(message):
    user_id = str(message.from_user.id)
    if not check_premium_access(user_id):
        bot.reply_to(message, "❌ Premium required!\n🎁 /trial - 2 hours free")
        return
    try:
        number = int(message.text.split(' ', 1)[1])
        msg = bot.reply_to(message, f"🔇 Silencer attack with {number} threads...")
        def cpu_stress():
            while True:
                _ = [x**2 for x in range(10000)]
        for _ in range(min(number, 10)):
            t = threading.Thread(target=cpu_stress, daemon=True)
            t.start()
        bot.edit_message_text(f"✅ Silencer active!\nThreads: {min(number, 10)}", message.chat.id, msg.message_id)
    except:
        bot.reply_to(message, "❌ Usage: /silencer <number>")

@bot.message_handler(commands=['crash'])
def crash_attack(message):
    if not check_premium_access(str(message.from_user.id)):
        bot.reply_to(message, "❌ Premium required!\n🎁 /trial - 2 hours free")
        return
    try:
        number = int(message.text.split(' ', 1)[1])
        def memory_eater():
            data = []
            while True:
                data.append("X" * 1024 * 1024)
        for _ in range(min(number, 5)):
            t = threading.Thread(target=memory_eater, daemon=True)
            t.start()
        bot.reply_to(message, f"✅ Crash attack with {min(number, 5)} threads!")
    except:
        bot.reply_to(message, "❌ Usage: /crash <number>")

@bot.message_handler(commands=['xdelay'])
def xdelay_attack(message):
    if not check_premium_access(str(message.from_user.id)):
        bot.reply_to(message, "❌ Premium required!\n🎁 /trial - 2 hours free")
        return
    try:
        delay_time = int(message.text.split(' ', 1)[1])
        msg = bot.reply_to(message, f"⏱ Delay of {delay_time}ms...")
        time.sleep(delay_time / 1000)
        bot.edit_message_text(f"✅ Delay completed!\n{delay_time}ms", message.chat.id, msg.message_id)
    except:
        bot.reply_to(message, "❌ Usage: /xdelay <milliseconds>")

@bot.message_handler(commands=['cekidgrup'])
def check_group(message):
    if not check_premium_access(str(message.from_user.id)):
        bot.reply_to(message, "❌ Premium required!\n🎁 /trial - 2 hours free")
        return
    chat_id = message.chat.id
    if message.chat.type in ['group', 'supergroup']:
        GROUP_IDS.add(str(chat_id))
        save_data()
        bot.reply_to(message, f"📱 Group ID: <code>{chat_id}</code>", parse_mode="HTML")
    else:
        bot.reply_to(message, f"💬 Chat ID: <code>{chat_id}</code>", parse_mode="HTML")

# ==================== AI COMMANDS ====================

@bot.message_handler(commands=['ask'])
def ask_ai(message):
    user_id = str(message.from_user.id)
    try:
        query = message.text.split(' ', 1)[1]
        if not query or len(query) < 2:
            bot.reply_to(message, "❌ Please ask a valid question!")
            return
        
        bot.send_chat_action(message.chat.id, 'typing')
        thinking_msg = bot.reply_to(message, "🤖 <b>AI is thinking...</b>", parse_mode="HTML")
        
        if user_id not in USER_CONVERSATIONS:
            USER_CONVERSATIONS[user_id] = [
                {"role": "system", "content": f"You are Alurb Bot's AI assistant. Be helpful and concise. © dev_nappier"}
            ]
        
        USER_CONVERSATIONS[user_id].append({"role": "user", "content": query})
        
        if len(USER_CONVERSATIONS[user_id]) > 9:
            USER_CONVERSATIONS[user_id] = [USER_CONVERSATIONS[user_id][0]] + USER_CONVERSATIONS[user_id][-8:]
        
        ai_response = ai_chat(USER_CONVERSATIONS[user_id], user_id)
        USER_CONVERSATIONS[user_id].append({"role": "assistant", "content": ai_response})
        
        bot.delete_message(message.chat.id, thinking_msg.message_id)
        
        response_text = f"""
🤖 <b>AI Response</b>

💭 <b>Question:</b> {query[:100]}{'...' if len(query) > 100 else ''}

📝 <b>Answer:</b>
{ai_response}

━━━━━━━━━━━━━━━━━━━━━━
🤖 DeepSeek Chat V3
© dev_nappier 😂🫡
        """
        bot.reply_to(message, response_text, parse_mode="HTML")
    except IndexError:
        bot.reply_to(message, "❌ Usage: /ask <your question>")
    except Exception as e:
        logger.error(f"AI error: {e}")
        bot.reply_to(message, "❌ Error processing request.")

@bot.message_handler(commands=['clearai'])
def clear_ai_history(message):
    user_id = str(message.from_user.id)
    if user_id in USER_CONVERSATIONS:
        del USER_CONVERSATIONS[user_id]
        bot.reply_to(message, "✅ AI history cleared!")
    else:
        bot.reply_to(message, "ℹ️ No history found.")

@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
def track_groups(message):
    GROUP_IDS.add(str(message.chat.id))
    if len(GROUP_IDS) % 10 == 0:
        save_data()

# ==================== MAIN ====================

def run_bot():
    logger.info("🚀 Alurb Bot starting...")
    logger.info(f"📊 Owners: {len(OWNERS)}, Premium: {len(PREMIUM_USERS)}")
    if len(OWNERS) == 0:
        logger.warning("⚠️ No owners! First /addowner will become owner.")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"Crash: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_bot()
