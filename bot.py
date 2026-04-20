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

bot = telebot.TeleBot(BOT_TOKEN)

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
TRIAL_HOURS = 2  # 2 hours free trial

# Premium Plans
PREMIUM_PLANS = {
    "2hours": {"name": "2 Hours Trial", "hours": 2, "price": "FREE (Auto-activated)"},
    "daily": {"name": "Daily", "days": 1, "price": "$0.99"},
    "weekly": {"name": "Weekly", "days": 7, "price": "$2.99"},
    "monthly": {"name": "Monthly", "days": 30, "price": "$7.99"},
    "lifetime": {"name": "Lifetime", "days": 36500, "price": "$49.99"}
}

def load_data():
    """Load all data from JSON files"""
    global PREMIUM_USERS, OWNERS, GROUP_IDS, TRIAL_USERS
    try:
        with open(f"{DATA_DIR}/premium.json", "r") as f:
            PREMIUM_USERS = json.load(f)
        logger.info(f"Loaded {len(PREMIUM_USERS)} premium users")
    except:
        PREMIUM_USERS = {}
    
    try:
        with open(f"{DATA_DIR}/owners.json", "r") as f:
            OWNERS = json.load(f)
        logger.info(f"Loaded {len(OWNERS)} owners")
    except:
        OWNERS = []
    
    try:
        with open(f"{DATA_DIR}/groups.json", "r") as f:
            GROUP_IDS = set(json.load(f))
        logger.info(f"Loaded {len(GROUP_IDS)} groups")
    except:
        GROUP_IDS = set()
    
    try:
        with open(f"{DATA_DIR}/trials.json", "r") as f:
            TRIAL_USERS = json.load(f)
        logger.info(f"Loaded {len(TRIAL_USERS)} trial users")
    except:
        TRIAL_USERS = {}

def save_data():
    """Save all data to JSON files"""
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
    """Check if user has active 2-hour trial"""
    user_id = str(user_id)
    if user_id in TRIAL_USERS:
        trial_data = TRIAL_USERS[user_id]
        trial_start = datetime.fromisoformat(trial_data["start_time"])
        trial_end = trial_start + timedelta(hours=TRIAL_HOURS)
        if datetime.now() < trial_end:
            return True
        else:
            # Trial expired - remove it
            del TRIAL_USERS[user_id]
            save_data()
            return False
    return False

def start_trial(user_id):
    """Start 2-hour free trial for user"""
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
    """Get remaining trial time"""
    user_id = str(user_id)
    if user_id in TRIAL_USERS:
        trial_start = datetime.fromisoformat(TRIAL_USERS[user_id]["start_time"])
        trial_end = trial_start + timedelta(hours=TRIAL_HOURS)
        time_left = trial_end - datetime.now()
        
        if time_left.total_seconds() > 0:
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            return f"{hours}h {minutes}m"
        else:
            return "Expired"
    return None

def get_premium_expiry(user_id):
    """Get premium expiry date for user"""
    user_id = str(user_id)
    if user_id in PREMIUM_USERS:
        premium_data = PREMIUM_USERS[user_id]
        if "expires" in premium_data and premium_data["expires"]:
            return datetime.fromisoformat(premium_data["expires"])
    return None

def ai_chat(messages, user_id):
    """Send request to OpenRouter AI API - WORKING VERSION"""
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
        
        logger.info(f"Sending AI request for user {user_id}")
        
        response = requests.post(
            f"{AI_CONFIG['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=45
        )
        
        logger.info(f"AI Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
            else:
                logger.error(f"Unexpected API response: {data}")
                return "❌ AI returned an unexpected response."
        else:
            logger.error(f"AI API Error {response.status_code}: {response.text}")
            return f"❌ AI service error (Status: {response.status_code})"
            
    except requests.exceptions.Timeout:
        logger.error("AI Request Timeout")
        return "❌ AI service timeout. Please try again."
    except requests.exceptions.ConnectionError:
        logger.error("AI Connection Error")
        return "❌ Cannot connect to AI service. Check internet."
    except Exception as e:
        logger.error(f"AI Request Error: {str(e)}")
        return f"❌ Error: {str(e)[:50]}"

# Load initial data
load_data()

# Keep-alive server for Render
keep_alive()

# ==================== BOT COMMANDS ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or "User"
    
    # Auto-start 2-hour trial for new users
    trial_started = False
    if not is_owner(user_id) and not is_premium(user_id) and not is_trial_active(user_id):
        trial_started = start_trial(user_id)
    
    # Check user status
    if is_owner(user_id):
        status_text = "\n👑 Status: Owner (Full Access)"
    elif is_premium(user_id):
        expiry = get_premium_expiry(user_id)
        if expiry:
            days_left = (expiry - datetime.now()).days
            status_text = f"\n💎 Status: Premium User ({days_left} days left)"
        else:
            status_text = "\n💎 Status: Premium User (Lifetime)"
    elif is_trial_active(user_id):
        time_left = get_trial_time_left(user_id)
        status_text = f"\n🎁 Status: Free Trial Active ({time_left} left)"
    else:
        status_text = "\n🔒 Status: Free User\n/trial - Start 2-hour free trial"
    
    trial_msg = ""
    if trial_started:
        trial_msg = f"\n\n🎉 **2-HOUR FREE TRIAL ACTIVATED!**\nEnjoy full premium access for {TRIAL_HOURS} hours!"
    
    welcome_text = f"""
╔══════════════════════╗
     🤖 WELCOME TO ALURB BOT 🤖
╚══════════════════════╝

👋 Hello {username}!

🔰 Bot Features:
• 24/7 Online Status
• AI Assistant (DeepSeek V3)
• Premium Attack Tools
• Group Management
• And much more!{status_text}{trial_msg}

🎁 **FREE TRIAL INCLUDES:**
• {TRIAL_HOURS} hours full premium access
• Silencer attacks
• XDelay attacks
• Crash attacks
• Unlimited AI questions

📌 Commands:
/help - See all commands
/status - Check your status
/trial - Start free trial
/premium - Upgrade options
/ask <query> - Ask AI

━━━━━━━━━━━━━━━━━━━━━━
© dev_nappier 😂🫡
Powered by Alurb Bot System
    """
    bot.reply_to(message, welcome_text, parse_mode="Markdown")
    
    if message.chat.type in ['group', 'supergroup']:
        GROUP_IDS.add(str(message.chat.id))
        save_data()

@bot.message_handler(commands=['trial'])
def trial_command(message):
    user_id = str(message.from_user.id)
    
    if is_owner(user_id):
        bot.reply_to(message, "👑 Owners have permanent premium access!")
        return
    
    if is_premium(user_id):
        bot.reply_to(message, "💎 You're already a Premium user! No trial needed.")
        return
    
    if is_trial_active(user_id):
        time_left = get_trial_time_left(user_id)
        bot.reply_to(message, f"""
🎁 YOUR TRIAL IS ACTIVE

⏰ Time Remaining: {time_left}
✅ Full Premium Access: ENABLED

Commands available:
• /silencer - Device silencer
• /xdelay - Heavy delay
• /crash - System crash
• /ask - AI Assistant

💎 Want more? /premium
        """)
        return
    
    # Start 2-hour trial
    if start_trial(user_id):
        trial_text = f"""
🎉 FREE TRIAL ACTIVATED!

⏰ Duration: {TRIAL_HOURS} HOURS
✅ Full Premium Access: ENABLED

🎁 You now have access to:
• /silencer - Device silencer
• /xdelay - Heavy delay  
• /crash - System crash
• /ask - Unlimited AI questions

⏰ Trial expires in {TRIAL_HOURS} hours
💎 Upgrade to Premium for permanent access: /premium

Enjoy! 🚀
        """
        bot.reply_to(message, trial_text)
        logger.info(f"Trial started for user {user_id}")
    else:
        bot.reply_to(message, "❌ Unable to start trial. Contact support.")

@bot.message_handler(commands=['premium'])
def premium_command(message):
    """Show premium information"""
    user_id = str(message.from_user.id)
    
    if is_owner(user_id):
        bot.reply_to(message, "👑 You are an Owner - Permanent premium access!")
        return
    
    if is_premium(user_id):
        expiry = get_premium_expiry(user_id)
        if expiry:
            days_left = (expiry - datetime.now()).days
            info = f"""
💎 YOUR PREMIUM STATUS

✅ Status: ACTIVE
📅 Days Remaining: {days_left}
🔓 All Premium Features: UNLOCKED

Enjoy your premium access! 🚀
            """
        else:
            info = """
💎 YOUR PREMIUM STATUS

✅ Status: ACTIVE (LIFETIME)
🔓 All Premium Features: UNLOCKED

Enjoy your lifetime access! 🚀
            """
        bot.reply_to(message, info)
        return
    
    if is_trial_active(user_id):
        time_left = get_trial_time_left(user_id)
        trial_status = f"\n🎁 Trial Active: {time_left} remaining"
    else:
        trial_status = "\n🎁 Trial: /trial (2 hours free)"
    
    plans_text = f"""
╔══════════════════════╗
     💎 PREMIUM PLANS 💎
╚══════════════════════╝{trial_status}

━━━━━━━━━━━━━━━━━━━━━━
📅 DAILY
• Duration: 24 hours
• Price: $0.99
• Full premium access

📅 WEEKLY
• Duration: 7 days
• Price: $2.99
• Save 57% vs daily

📅 MONTHLY (Most Popular)
• Duration: 30 days
• Price: $7.99
• Save 73% vs daily

📅 LIFETIME (Best Value)
• Duration: Forever
• Price: $49.99
• One-time payment

━━━━━━━━━━━━━━━━━━━━━━
✨ Premium Benefits:
• Unlimited silencer attacks
• Unlimited XDelay attacks
• Crash attack access
• Unlimited AI questions
• Group management tools
• Priority support

📩 To Upgrade:
━━━━━━━━━━━━━━━━━━━━━━
👤 Contact: @dev_nappier
📧 Email: premium@alurb-bot.com

💳 Payment Methods:
• Cryptocurrency (BTC, ETH, USDT)
• PayPal • Bank Transfer

━━━━━━━━━━━━━━━━━━━━━━
© dev_nappier 😂🫡
    """
    bot.reply_to(message, plans_text)

@bot.message_handler(commands=['status'])
def bot_status(message):
    user_id = str(message.from_user.id)
    
    uptime = time.time() - BOT_START_TIME
    days = int(uptime // 86400)
    hours = int((uptime % 86400) // 3600)
    minutes = int((uptime % 3600) // 60)
    
    # Get user status
    if is_owner(user_id):
        user_status = "👑 Owner (Permanent Access)"
    elif is_premium(user_id):
        expiry = get_premium_expiry(user_id)
        if expiry:
            days_left = (expiry - datetime.now()).days
            user_status = f"💎 Premium ({days_left} days left)"
        else:
            user_status = "💎 Premium (Lifetime)"
    elif is_trial_active(user_id):
        time_left = get_trial_time_left(user_id)
        user_status = f"🎁 Trial Active ({time_left} left)"
    else:
        user_status = "🔒 Free (Start trial: /trial)"
    
    status_text = f"""
╔══════════════════════╗
       🤖 BOT STATUS 🤖
╚══════════════════════╝

📊 System Statistics:
━━━━━━━━━━━━━━━━━━━━━━
✅ Bot Status: 24/7 Active
⏰ Uptime: {days}d {hours}h {minutes}m
👑 Total Owners: {len(OWNERS)}
💎 Premium Users: {len(PREMIUM_USERS)}
🎁 Active Trials: {len([t for t in TRIAL_USERS if is_trial_active(t)])}
📱 Groups Joined: {len(GROUP_IDS)}

👤 Your Status:
━━━━━━━━━━━━━━━━━━━━━━
{user_status}

🛠 System Info:
━━━━━━━━━━━━━━━━━━━━━━
🤖 AI Model: DeepSeek Chat V3
🌐 Language: {AI_CONFIG['language']}
📡 Response Time: Optimal

━━━━━━━━━━━━━━━━━━━━━━
Powered by Alurb Bot System
© dev_nappier 😂🫡
    """
    bot.reply_to(message, status_text)

@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = str(message.from_user.id)
    
    if is_owner(user_id):
        user_level = "👑 Owner"
    elif is_premium(user_id):
        user_level = "💎 Premium"
    elif is_trial_active(user_id):
        user_level = f"🎁 Trial ({get_trial_time_left(user_id)} left)"
    else:
        user_level = "🔒 Free"
    
    help_text = f"""
╔══════════════════════╗
     📚 COMMAND MENU 📚
╚══════════════════════╝

𖤊───⪩ FREE COMMANDS ⪨───𖤊
✦ /start - Welcome message
✦ /help - Show this menu
✦ /status - Check your status
✦ /trial - Start 2-hour free trial
✦ /premium - View premium plans
✦ /ask <query> - Ask AI Assistant
✦ /clearai - Clear AI history

𖤊───⪩ PREMIUM COMMANDS ⪨───𖤊
🔒 Requires Premium/Trial:
✦ /silencer <num> - Silencer attack
✦ /xdelay <num> - Heavy delay
✦ /crash <num> - System crash
✦ /cekidgrup - Get group ID

𖤊───⪩ OWNER COMMANDS ⪨───𖤊
👑 Owner Only:
✦ /addprem <id> <plan> - Add premium
✦ /delprem <id> - Remove premium
✦ /addowner <id> - Add owner
✦ /delowner <id> - Remove owner
✦ /listprem - List premium users
✦ /listidgrup - List all groups

━━━━━━━━━━━━━━━━━━━━━━
🤖 AI Model: DeepSeek Chat V3
👤 Your Level: {user_level}
🎁 Free Trial: /trial ({TRIAL_HOURS} hours)
© dev_nappier 😂🫡
    """
    bot.reply_to(message, help_text)

# ==================== OWNER COMMANDS ====================

@bot.message_handler(commands=['addprem'])
def add_premium(message):
    user_id = str(message.from_user.id)
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    try:
        parts = message.text.split(' ')
        target_id = parts[1]
        
        plan = "monthly"
        if len(parts) > 2:
            plan = parts[2]
        
        plan_info = PREMIUM_PLANS.get(plan, PREMIUM_PLANS["monthly"])
        
        if "hours" in plan_info:
            expiry = datetime.now() + timedelta(hours=plan_info["hours"])
        else:
            days = plan_info.get("days", 30)
            expiry = datetime.now() + timedelta(days=days)
        
        PREMIUM_USERS[target_id] = {
            "added_by": user_id,
            "date": datetime.now().isoformat(),
            "expires": expiry.isoformat() if plan != "lifetime" else None,
            "plan": plan
        }
        
        # Remove from trial if exists
        if target_id in TRIAL_USERS:
            del TRIAL_USERS[target_id]
        
        save_data()
        
        expiry_text = expiry.strftime('%Y-%m-%d %H:%M') if plan != "lifetime" else "Lifetime"
        
        bot.reply_to(message, f"""
✅ PREMIUM ACCESS GRANTED

👤 User ID: `{target_id}`
📅 Plan: {plan_info['name']}
⏰ Expires: {expiry_text}
👑 Added by: Owner

User can now use all premium features!
        """, parse_mode="Markdown")
        
        logger.info(f"Premium added for {target_id} by {user_id} - Plan: {plan}")
        
    except IndexError:
        plans_list = ", ".join([f"{k}" for k in PREMIUM_PLANS.keys()])
        bot.reply_to(message, f"❌ Usage: /addprem <user_id> [plan]\n\nAvailable plans: {plans_list}")

@bot.message_handler(commands=['delprem'])
def del_premium(message):
    user_id = str(message.from_user.id)
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    try:
        target_id = message.text.split(' ', 1)[1]
        if target_id in PREMIUM_USERS:
            del PREMIUM_USERS[target_id]
            save_data()
            bot.reply_to(message, f"✅ User {target_id} removed from premium!")
            logger.info(f"Premium removed for {target_id} by {user_id}")
        else:
            bot.reply_to(message, f"❌ User {target_id} not found!")
    except:
        bot.reply_to(message, "❌ Usage: /delprem <user_id>")

@bot.message_handler(commands=['listprem'])
def list_premium(message):
    user_id = str(message.from_user.id)
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    if PREMIUM_USERS:
        text = "📋 PREMIUM USERS LIST:\n\n"
        for idx, (uid, data) in enumerate(PREMIUM_USERS.items(), 1):
            plan = data.get("plan", "unknown")
            plan_name = PREMIUM_PLANS.get(plan, {}).get("name", plan)
            
            if data.get("expires"):
                exp_date = datetime.fromisoformat(data["expires"])
                days_left = (exp_date - datetime.now()).days
                hours_left = int((exp_date - datetime.now()).total_seconds() // 3600)
                if hours_left < 24:
                    expiry = f"{exp_date.strftime('%Y-%m-%d %H:%M')} ({hours_left}h left)"
                else:
                    expiry = f"{exp_date.strftime('%Y-%m-%d')} ({days_left}d left)"
            else:
                expiry = "Lifetime"
            
            text += f"{idx}. ID: `{uid}`\n   Plan: {plan_name}\n   Expires: {expiry}\n\n"
        
        bot.reply_to(message, text, parse_mode="Markdown")
    else:
        bot.reply_to(message, "📋 No premium users found!")

@bot.message_handler(commands=['addowner'])
def add_owner(message):
    user_id = str(message.from_user.id)
    
    if not is_owner(user_id) and len(OWNERS) > 0:
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    try:
        target_id = message.text.split(' ', 1)[1]
        if target_id not in OWNERS:
            OWNERS.append(target_id)
            save_data()
            bot.reply_to(message, f"✅ User {target_id} added as owner!")
            logger.info(f"New owner added: {target_id}")
        else:
            bot.reply_to(message, f"⚠️ User {target_id} is already an owner!")
    except:
        bot.reply_to(message, "❌ Usage: /addowner <user_id>")

@bot.message_handler(commands=['delowner'])
def del_owner(message):
    user_id = str(message.from_user.id)
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    try:
        target_id = message.text.split(' ', 1)[1]
        if target_id in OWNERS:
            OWNERS.remove(target_id)
            save_data()
            bot.reply_to(message, f"✅ User {target_id} removed from owners!")
        else:
            bot.reply_to(message, f"❌ User {target_id} not found!")
    except:
        bot.reply_to(message, "❌ Usage: /delowner <user_id>")

@bot.message_handler(commands=['listidgrup'])
def list_groups(message):
    user_id = str(message.from_user.id)
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    if GROUP_IDS:
        text = "📋 ALL GROUP IDs:\n\n"
        for idx, gid in enumerate(GROUP_IDS, 1):
            text += f"{idx}. `{gid}`\n"
        bot.reply_to(message, text, parse_mode="Markdown")
    else:
        bot.reply_to(message, "📋 No groups recorded yet!")

# ==================== PREMIUM COMMANDS ====================

def check_premium_access(user_id):
    """Check if user has premium or trial access"""
    if is_owner(user_id):
        return True
    if is_premium(user_id):
        return True
    if is_trial_active(user_id):
        return True
    return False

@bot.message_handler(commands=['silencer'])
def silencer_attack(message):
    user_id = str(message.from_user.id)
    
    if not check_premium_access(user_id):
        bot.reply_to(message, "❌ Premium required!\n🎁 Start 2-hour free trial: /trial")
        return
    
    try:
        number = int(message.text.split(' ', 1)[1])
        msg = bot.reply_to(message, f"🔇 Starting silencer attack with {number} threads...")
        
        def cpu_stress():
            while True:
                _ = [x**2 for x in range(10000)]
        
        threads = []
        for _ in range(min(number, 10)):
            t = threading.Thread(target=cpu_stress)
            t.daemon = True
            t.start()
            threads.append(t)
        
        bot.edit_message_text(f"✅ Silencer attack active!\nThreads: {len(threads)}\nTarget: Device CPU", 
                            message.chat.id, msg.message_id)
        logger.info(f"Silencer attack by {user_id}")
    except:
        bot.reply_to(message, "❌ Usage: /silencer <number>")

@bot.message_handler(commands=['crash'])
def crash_attack(message):
    user_id = str(message.from_user.id)
    
    if not check_premium_access(user_id):
        bot.reply_to(message, "❌ Premium required!\n🎁 Start 2-hour free trial: /trial")
        return
    
    try:
        number = int(message.text.split(' ', 1)[1])
        bot.reply_to(message, f"💥 Initiating crash attack...\nForce: {number}")
        
        def memory_eater():
            data = []
            while True:
                data.append("X" * 1024 * 1024)
                
        for _ in range(min(number, 5)):
            t = threading.Thread(target=memory_eater)
            t.daemon = True
            t.start()
            
        bot.reply_to(message, f"✅ Crash attack initiated with {number} threads!")
    except:
        bot.reply_to(message, "❌ Usage: /crash <number>")

@bot.message_handler(commands=['xdelay'])
def xdelay_attack(message):
    user_id = str(message.from_user.id)
    
    if not check_premium_access(user_id):
        bot.reply_to(message, "❌ Premium required!\n🎁 Start 2-hour free trial: /trial")
        return
    
    try:
        delay_time = int(message.text.split(' ', 1)[1])
        msg = bot.reply_to(message, f"⏱ Applying heavy delay of {delay_time}ms...")
        time.sleep(delay_time / 1000)
        bot.edit_message_text(f"✅ Delay completed!\nDuration: {delay_time}ms", message.chat.id, msg.message_id)
    except:
        bot.reply_to(message, "❌ Usage: /xdelay <milliseconds>")

@bot.message_handler(commands=['cekidgrup'])
def check_group(message):
    user_id = str(message.from_user.id)
    
    if not check_premium_access(user_id):
        bot.reply_to(message, "❌ Premium required!\n🎁 Start 2-hour free trial: /trial")
        return
    
    chat_id = message.chat.id
    chat_type = message.chat.type
    
    if chat_type in ['group', 'supergroup']:
        bot.reply_to(message, f"📱 Group ID: `{chat_id}`\n📝 Type: {chat_type}", parse_mode="Markdown")
        GROUP_IDS.add(str(chat_id))
        save_data()
    else:
        bot.reply_to(message, f"💬 Chat ID: `{chat_id}`", parse_mode="Markdown")

# ==================== AI COMMANDS ====================

@bot.message_handler(commands=['ask'])
def ask_ai(message):
    user_id = str(message.from_user.id)
    
    try:
        query = message.text.split(' ', 1)[1]
        
        if not query or len(query) < 2:
            bot.reply_to(message, "❌ Please ask a valid question!")
            return
        
        # Send typing indicator
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Let user know AI is thinking
        thinking_msg = bot.reply_to(message, "🤖 **AI is thinking...**", parse_mode="Markdown")
        
        # Initialize conversation for user if not exists
        if user_id not in USER_CONVERSATIONS:
            USER_CONVERSATIONS[user_id] = [
                {"role": "system", "content": f"You are Alurb Bot's AI assistant. Be helpful, friendly, and concise. Respond in {AI_CONFIG['language']}. © dev_nappier"}
            ]
        
        # Add user message to conversation
        USER_CONVERSATIONS[user_id].append({"role": "user", "content": query})
        
        # Keep conversation history limited (last 8 messages)
        if len(USER_CONVERSATIONS[user_id]) > 9:
            USER_CONVERSATIONS[user_id] = [USER_CONVERSATIONS[user_id][0]] + USER_CONVERSATIONS[user_id][-8:]
        
        # Get AI response
        ai_response = ai_chat(USER_CONVERSATIONS[user_id], user_id)
        
        # Add AI response to conversation
        USER_CONVERSATIONS[user_id].append({"role": "assistant", "content": ai_response})
        
        # Delete thinking message
        bot.delete_message(message.chat.id, thinking_msg.message_id)
        
        # Send response
        response_text = f"""
🤖 **AI Assistant Response**

💭 **Question:** _{query[:100]}{'...' if len(query) > 100 else ''}_

📝 **Answer:**
{ai_response}

━━━━━━━━━━━━━━━━━━━━━━
🤖 Model: DeepSeek Chat V3
© dev_nappier 😂🫡
        """
        
        bot.reply_to(message, response_text, parse_mode="Markdown")
        logger.info(f"AI query from {user_id}: {query[:30]}...")
        
    except IndexError:
        bot.reply_to(message, "❌ Usage: /ask <your question>")
    except Exception as e:
        logger.error(f"AI command error: {e}")
        bot.reply_to(message, "❌ Error processing your request. Please try again.")

@bot.message_handler(commands=['clearai'])
def clear_ai_history(message):
    user_id = str(message.from_user.id)
    
    if user_id in USER_CONVERSATIONS:
        del USER_CONVERSATIONS[user_id]
        bot.reply_to(message, "✅ AI conversation history cleared!")
    else:
        bot.reply_to(message, "ℹ️ No conversation history found.")

@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
def track_groups(message):
    GROUP_IDS.add(str(message.chat.id))
    if len(GROUP_IDS) % 10 == 0:
        save_data()

# ==================== MAIN RUNNER ====================

def run_bot():
    """Run bot with automatic restart on failure"""
    logger.info("🚀 Starting Alurb Bot - 24/7 Mode with 2-Hour Free Trial")
    logger.info(f"🤖 AI Model: {AI_CONFIG['model']}")
    logger.info(f"📊 Loaded {len(OWNERS)} owners, {len(PREMIUM_USERS)} premium users")
    
    if len(OWNERS) == 0:
        logger.warning("⚠️ No owners set! First user to run /addowner will become owner.")
    
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Network connection error: {e}")
            time.sleep(10)
        except requests.exceptions.ReadTimeout as e:
            logger.error(f"Read timeout error: {e}")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Bot crashed with error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run_bot()
