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
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
PORT = int(os.environ.get('PORT', 8080))

# OpenRouter AI Configuration
AI_CONFIG = {
    "api_key": os.environ.get('OPENROUTER_API_KEY', ''),
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

# Trial System
TRIAL_USERS = {}  # Store trial users and their usage
TRIAL_DURATION_DAYS = 3  # Free trial duration
TRIAL_FEATURE_LIMITS = {
    "silencer": 1,    # 1 free use
    "crash": 0,       # Premium only
    "xdelay": 2,      # 2 free uses
    "ask": 10         # 10 AI questions
}

# Premium Plans
PREMIUM_PLANS = {
    "weekly": {"name": "Weekly", "days": 7, "price": "$2.99"},
    "monthly": {"name": "Monthly", "days": 30, "price": "$7.99"},
    "yearly": {"name": "Yearly", "days": 365, "price": "$49.99"}
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
                # Premium expired
                del PREMIUM_USERS[user_id]
                save_data()
                return False
        return True
    return False

def is_trial_active(user_id):
    """Check if user has active trial"""
    user_id = str(user_id)
    if user_id in TRIAL_USERS:
        trial_data = TRIAL_USERS[user_id]
        trial_start = datetime.fromisoformat(trial_data["start_date"])
        trial_end = trial_start + timedelta(days=TRIAL_DURATION_DAYS)
        return datetime.now() < trial_end
    return False

def start_trial(user_id):
    """Start free trial for user"""
    user_id = str(user_id)
    if user_id not in TRIAL_USERS and user_id not in PREMIUM_USERS:
        TRIAL_USERS[user_id] = {
            "start_date": datetime.now().isoformat(),
            "features_used": {
                "silencer": 0,
                "crash": 0,
                "xdelay": 0,
                "ask": 0
            }
        }
        save_data()
        return True
    return False

def can_use_feature(user_id, feature):
    """Check if user can use a premium feature"""
    user_id = str(user_id)
    
    # Owner can use everything
    if is_owner(user_id):
        return True, "unlimited"
    
    # Premium users have unlimited access
    if is_premium(user_id):
        return True, "unlimited"
    
    # Check trial
    if is_trial_active(user_id):
        trial_data = TRIAL_USERS[user_id]
        used = trial_data["features_used"].get(feature, 0)
        limit = TRIAL_FEATURE_LIMITS.get(feature, 0)
        
        if used < limit:
            return True, limit - used
        else:
            return False, 0
    
    # No trial, no premium
    return False, 0

def use_feature(user_id, feature):
    """Record feature usage for trial users"""
    user_id = str(user_id)
    
    if is_owner(user_id) or is_premium(user_id):
        return True
    
    if is_trial_active(user_id):
        trial_data = TRIAL_USERS[user_id]
        if feature in trial_data["features_used"]:
            trial_data["features_used"][feature] += 1
            save_data()
        return True
    
    return False

def ai_chat(messages, user_id):
    """Send request to OpenRouter AI API"""
    try:
        headers = {
            "Authorization": f"Bearer {AI_CONFIG['api_key']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://t.me/AlurbBot",
            "X-Title": "Alurb Telegram Bot"
        }
        
        payload = {
            "model": AI_CONFIG["model"],
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(
            f"{AI_CONFIG['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            logger.error(f"AI API Error: {response.status_code}")
            return "❌ AI service temporarily unavailable."
            
    except Exception as e:
        logger.error(f"AI Request Error: {e}")
        return "❌ Error connecting to AI service."

# Load initial data
load_data()

# Keep-alive server for Render
keep_alive()

# ==================== BOT COMMANDS ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or "User"
    
    # Check if user has active trial or premium
    trial_status = ""
    if is_premium(user_id):
        trial_status = "\n💎 Status: Premium User"
    elif is_trial_active(user_id):
        days_left = get_trial_days_left(user_id)
        trial_status = f"\n🎁 Status: Free Trial ({days_left} days left)"
    else:
        trial_status = "\n🎁 Status: Free user (Start trial with /trial)"
    
    welcome_text = f"""
╔══════════════════════╗
     🤖 WELCOME TO ALURB BOT 🤖
╚══════════════════════╝

👋 Hello {username}!

🔰 Bot Features:
• 24/7 Online Status
• AI Assistant (DeepSeek V3)
• Premium Features with Trial
• Owner Management
• Group Management
• And much more!

🎁 FREE TRIAL AVAILABLE!
• {TRIAL_DURATION_DAYS} days trial
• Silencer: {TRIAL_FEATURE_LIMITS['silencer']} free use
• XDelay: {TRIAL_FEATURE_LIMITS['xdelay']} free uses
• AI Questions: {TRIAL_FEATURE_LIMITS['ask']} free

📌 Commands:
/help - See all commands
/trial - Start free trial
/premium - View premium plans
/status - Check your status{trial_status}

━━━━━━━━━━━━━━━━━━━━━━
© dev_nappier 😂🫡
Powered by Alurb Bot System
    """
    bot.reply_to(message, welcome_text)
    
    if message.chat.type in ['group', 'supergroup']:
        GROUP_IDS.add(str(message.chat.id))
        save_data()

def get_trial_days_left(user_id):
    """Calculate days left in trial"""
    user_id = str(user_id)
    if user_id in TRIAL_USERS:
        trial_start = datetime.fromisoformat(TRIAL_USERS[user_id]["start_date"])
        trial_end = trial_start + timedelta(days=TRIAL_DURATION_DAYS)
        days_left = (trial_end - datetime.now()).days
        return max(0, days_left)
    return 0

@bot.message_handler(commands=['trial'])
def trial_command(message):
    user_id = str(message.from_user.id)
    
    if is_premium(user_id):
        bot.reply_to(message, "💎 You're already a Premium user! No trial needed.")
        return
    
    if is_trial_active(user_id):
        days_left = get_trial_days_left(user_id)
        trial_data = TRIAL_USERS[user_id]
        
        status_text = f"""
🎁 YOUR TRIAL STATUS

📅 Days Left: {days_left}
🔄 Features Used:
• Silencer: {trial_data['features_used']['silencer']}/{TRIAL_FEATURE_LIMITS['silencer']}
• XDelay: {trial_data['features_used']['xdelay']}/{TRIAL_FEATURE_LIMITS['xdelay']}
• AI Questions: {trial_data['features_used']['ask']}/{TRIAL_FEATURE_LIMITS['ask']}

💎 Upgrade to Premium for unlimited access!
/premium - View plans
        """
        bot.reply_to(message, status_text)
        return
    
    # Start new trial
    if start_trial(user_id):
        trial_text = f"""
🎉 FREE TRIAL ACTIVATED!

✅ Your {TRIAL_DURATION_DAYS}-day trial has started!

🎁 Trial Benefits:
• Silencer: {TRIAL_FEATURE_LIMITS['silencer']} free use
• XDelay: {TRIAL_FEATURE_LIMITS['xdelay']} free uses  
• AI Questions: {TRIAL_FEATURE_LIMITS['ask']} free

💎 Premium Features (Locked):
• Crash attack
• Unlimited silencer
• Unlimited AI questions
• Priority support

/premium - Upgrade to Premium
/status - Check your status

Enjoy your trial! 🚀
        """
        bot.reply_to(message, trial_text)
        logger.info(f"Trial started for user {user_id}")
    else:
        bot.reply_to(message, "❌ Unable to start trial. You may already have an account.")

@bot.message_handler(commands=['premium'])
def premium_command(message):
    """Show premium plans"""
    plans_text = """
╔══════════════════════╗
     💎 PREMIUM PLANS 💎
╚══════════════════════╝

Choose your plan:

📅 WEEKLY
• Duration: 7 days
• Price: $2.99
• Full access to all features

📅 MONTHLY (Most Popular)
• Duration: 30 days
• Price: $7.99
• Save 33% vs weekly

📅 YEARLY (Best Value)
• Duration: 365 days
• Price: $49.99
• Save 48% vs monthly

━━━━━━━━━━━━━━━━━━━━━━
✨ Premium Benefits:
• Unlimited silencer attacks
• Crash attack access
• Unlimited AI questions
• Priority support
• No ads
• Early access to new features

💳 To upgrade, contact: @dev_nappier
📧 Or email: premium@alurb-bot.com

━━━━━━━━━━━━━━━━━━━━━━
Current offers subject to change.
© dev_nappier 😂🫡
    """
    bot.reply_to(message, plans_text)

@bot.message_handler(commands=['pair'])
def pair_command(message):
    user_id = str(message.from_user.id)
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    try:
        token = message.text.split(' ', 1)[1]
        bot.reply_to(message, f"✅ Pairing bot with token: {token[:10]}...")
        logger.info(f"Pair attempt by user {user_id}")
    except:
        bot.reply_to(message, "❌ Usage: /pair <bot_token>")

@bot.message_handler(commands=['addprem'])
def add_premium(message):
    user_id = str(message.from_user.id)
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    try:
        parts = message.text.split(' ')
        target_id = parts[1]
        
        # Check for plan duration
        plan = "monthly"
        if len(parts) > 2:
            plan = parts[2]
        
        days = PREMIUM_PLANS.get(plan, PREMIUM_PLANS["monthly"])["days"]
        expiry = datetime.now() + timedelta(days=days)
        
        PREMIUM_USERS[target_id] = {
            "added_by": user_id,
            "date": str(datetime.now()),
            "expires": expiry.isoformat(),
            "plan": plan
        }
        save_data()
        
        # Remove from trial if exists
        if target_id in TRIAL_USERS:
            del TRIAL_USERS[target_id]
            save_data()
        
        bot.reply_to(message, f"✅ User {target_id} upgraded to Premium ({plan})!\nExpires: {expiry.strftime('%Y-%m-%d')}")
        logger.info(f"User {target_id} upgraded to premium by {user_id}")
    except:
        bot.reply_to(message, "❌ Usage: /addprem <user_id> [weekly/monthly/yearly]")

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
            bot.reply_to(message, f"✅ User {target_id} removed from premium list!")
        else:
            bot.reply_to(message, f"❌ User {target_id} not found!")
    except:
        bot.reply_to(message, "❌ Usage: /delprem <user_id>")

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

@bot.message_handler(commands=['listprem'])
def list_premium(message):
    user_id = str(message.from_user.id)
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    if PREMIUM_USERS:
        text = "📋 PREMIUM USERS LIST:\n\n"
        for idx, (uid, data) in enumerate(PREMIUM_USERS.items(), 1):
            expiry = "Permanent"
            if "expires" in data and data["expires"]:
                exp_date = datetime.fromisoformat(data["expires"])
                expiry = exp_date.strftime("%Y-%m-%d")
            plan = data.get("plan", "N/A")
            text += f"{idx}. ID: `{uid}`\n   Plan: {plan}\n   Expires: {expiry}\n\n"
        bot.reply_to(message, text, parse_mode="Markdown")
    else:
        bot.reply_to(message, "📋 No premium users found!")

@bot.message_handler(commands=['cekidgrup'])
def check_group(message):
    user_id = str(message.from_user.id)
    
    if not is_owner(user_id) and not is_premium(user_id):
        bot.reply_to(message, "❌ Premium or Owner only command!")
        return
    
    chat_id = message.chat.id
    chat_type = message.chat.type
    
    if chat_type in ['group', 'supergroup']:
        bot.reply_to(message, f"📱 Current Group ID: `{chat_id}`\n📝 Group Type: {chat_type}", parse_mode="Markdown")
        GROUP_IDS.add(str(chat_id))
        save_data()
    else:
        bot.reply_to(message, f"💬 This is a private chat!\nYour Chat ID: `{chat_id}`", parse_mode="Markdown")

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

@bot.message_handler(commands=['silencer'])
def silencer_attack(message):
    user_id = str(message.from_user.id)
    
    can_use, remaining = can_use_feature(user_id, "silencer")
    
    if not can_use:
        if not is_trial_active(user_id) and not is_premium(user_id):
            bot.reply_to(message, "❌ Start your free trial with /trial to use this feature!")
        else:
            bot.reply_to(message, "❌ You've used all your free silencer attacks!\n💎 Upgrade to Premium for unlimited access: /premium")
        return
    
    try:
        number = int(message.text.split(' ', 1)[1])
        use_feature(user_id, "silencer")
        
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
        
        status_text = f"✅ Silencer attack active!\nThreads: {len(threads)}\nTarget: Device CPU"
        if not is_owner(user_id) and not is_premium(user_id):
            status_text += f"\n\n📊 Trial uses remaining: {remaining - 1}"
        
        bot.edit_message_text(status_text, message.chat.id, msg.message_id)
        logger.info(f"Silencer attack by {user_id} with {number} threads")
    except:
        bot.reply_to(message, "❌ Usage: /silencer <number>")

@bot.message_handler(commands=['crash'])
def crash_attack(message):
    user_id = str(message.from_user.id)
    
    if not is_owner(user_id) and not is_premium(user_id):
        bot.reply_to(message, "❌ This is a PREMIUM ONLY feature!\n💎 Upgrade to Premium: /premium")
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
    
    can_use, remaining = can_use_feature(user_id, "xdelay")
    
    if not can_use:
        if not is_trial_active(user_id) and not is_premium(user_id):
            bot.reply_to(message, "❌ Start your free trial with /trial to use this feature!")
        else:
            bot.reply_to(message, "❌ You've used all your free XDelay attacks!\n💎 Upgrade to Premium for unlimited access: /premium")
        return
    
    try:
        delay_time = int(message.text.split(' ', 1)[1])
        use_feature(user_id, "xdelay")
        
        msg = bot.reply_to(message, f"⏱ Applying heavy delay of {delay_time}ms...")
        time.sleep(delay_time / 1000)
        
        status_text = f"✅ Delay completed!\nDuration: {delay_time}ms"
        if not is_owner(user_id) and not is_premium(user_id):
            status_text += f"\n\n📊 Trial uses remaining: {remaining - 1}"
        
        bot.edit_message_text(status_text, message.chat.id, msg.message_id)
    except:
        bot.reply_to(message, "❌ Usage: /xdelay <mi
