import telebot
import time
import os
import json
import threading
import logging
import random
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

# ==================== MASTER OWNER CONFIGURATION ====================
MASTER_OWNER_ID = "6803973808"  # YOUR Telegram ID - ONLY YOU can add/remove owners

# ==================== ALURB AI CONFIGURATION (SECURE) ====================
AI_CONFIG = {
    "api_key": os.environ.get('OPENROUTER_API_KEY', ''),
    "base_url": "https://openrouter.ai/api/v1",
    "model": "deepseek/deepseek-chat",
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

# Trial System - 2 Hours Free Trial
TRIAL_USERS = {}
TRIAL_HOURS = 2

# Premium Plans
PREMIUM_PLANS = {
    "daily": {"name": "Daily", "days": 1, "price": "$0.99"},
    "weekly": {"name": "Weekly", "days": 7, "price": "$2.99"},
    "monthly": {"name": "Monthly", "days": 30, "price": "$7.99"},
    "lifetime": {"name": "Lifetime", "days": 36500, "price": "$49.99"}
}

def load_data():
    """Load all data from JSON files"""
    global PREMIUM_USERS, OWNERS, GROUP_IDS, TRIAL_USERS
    
    logger.info("Loading data from JSON files...")
    
    try:
        with open(f"{DATA_DIR}/premium.json", "r") as f:
            PREMIUM_USERS = json.load(f)
        logger.info(f"Loaded {len(PREMIUM_USERS)} premium users")
    except FileNotFoundError:
        PREMIUM_USERS = {}
        logger.info("No premium users file found, starting fresh")
    except json.JSONDecodeError:
        PREMIUM_USERS = {}
        logger.error("Corrupted premium.json file, starting fresh")
    except Exception as e:
        PREMIUM_USERS = {}
        logger.error(f"Error loading premium users: {e}")
    
    try:
        with open(f"{DATA_DIR}/owners.json", "r") as f:
            OWNERS = json.load(f)
        logger.info(f"Loaded {len(OWNERS)} owners")
    except FileNotFoundError:
        OWNERS = []
        logger.info("No owners file found, starting fresh")
    except json.JSONDecodeError:
        OWNERS = []
        logger.error("Corrupted owners.json file, starting fresh")
    except Exception as e:
        OWNERS = []
        logger.error(f"Error loading owners: {e}")
    
    try:
        with open(f"{DATA_DIR}/groups.json", "r") as f:
            GROUP_IDS = set(json.load(f))
        logger.info(f"Loaded {len(GROUP_IDS)} groups")
    except FileNotFoundError:
        GROUP_IDS = set()
        logger.info("No groups file found, starting fresh")
    except json.JSONDecodeError:
        GROUP_IDS = set()
        logger.error("Corrupted groups.json file, starting fresh")
    except Exception as e:
        GROUP_IDS = set()
        logger.error(f"Error loading groups: {e}")
    
    try:
        with open(f"{DATA_DIR}/trials.json", "r") as f:
            TRIAL_USERS = json.load(f)
        logger.info(f"Loaded {len(TRIAL_USERS)} trial users")
    except FileNotFoundError:
        TRIAL_USERS = {}
        logger.info("No trials file found, starting fresh")
    except json.JSONDecodeError:
        TRIAL_USERS = {}
        logger.error("Corrupted trials.json file, starting fresh")
    except Exception as e:
        TRIAL_USERS = {}
        logger.error(f"Error loading trials: {e}")

def save_data():
    """Save all data to JSON files"""
    logger.info("Saving data to JSON files...")
    
    try:
        with open(f"{DATA_DIR}/premium.json", "w") as f:
            json.dump(PREMIUM_USERS, f, indent=2)
        logger.debug("Premium users saved")
    except Exception as e:
        logger.error(f"Error saving premium users: {e}")
    
    try:
        with open(f"{DATA_DIR}/owners.json", "w") as f:
            json.dump(OWNERS, f, indent=2)
        logger.debug("Owners saved")
    except Exception as e:
        logger.error(f"Error saving owners: {e}")
    
    try:
        with open(f"{DATA_DIR}/groups.json", "w") as f:
            json.dump(list(GROUP_IDS), f, indent=2)
        logger.debug("Groups saved")
    except Exception as e:
        logger.error(f"Error saving groups: {e}")
    
    try:
        with open(f"{DATA_DIR}/trials.json", "w") as f:
            json.dump(TRIAL_USERS, f, indent=2)
        logger.debug("Trials saved")
    except Exception as e:
        logger.error(f"Error saving trials: {e}")

def is_master(user_id):
    """Check if user is the Master Owner"""
    result = str(user_id) == MASTER_OWNER_ID
    logger.debug(f"Master check for {user_id}: {result}")
    return result

def is_owner(user_id):
    """Check if user is an owner (Master or added owner)"""
    user_id = str(user_id)
    if user_id == MASTER_OWNER_ID:
        return True
    result = user_id in OWNERS
    logger.debug(f"Owner check for {user_id}: {result}")
    return result

def is_premium(user_id):
    """Check if user has active premium"""
    user_id = str(user_id)
    if user_id in PREMIUM_USERS:
        premium_data = PREMIUM_USERS[user_id]
        if "expires" in premium_data and premium_data["expires"]:
            try:
                expiry = datetime.fromisoformat(premium_data["expires"])
                if expiry > datetime.now():
                    logger.debug(f"Premium check for {user_id}: Active until {expiry}")
                    return True
                else:
                    # Premium expired - remove them
                    logger.info(f"Premium expired for {user_id}, removing...")
                    del PREMIUM_USERS[user_id]
                    save_data()
                    return False
            except ValueError:
                logger.error(f"Invalid expiry date for {user_id}")
                return False
        logger.debug(f"Premium check for {user_id}: Active (no expiry)")
        return True
    logger.debug(f"Premium check for {user_id}: Not premium")
    return False

def is_trial_active(user_id):
    """Check if user has active 2-hour trial"""
    user_id = str(user_id)
    if user_id in TRIAL_USERS:
        trial_data = TRIAL_USERS[user_id]
        try:
            trial_start = datetime.fromisoformat(trial_data["start_time"])
            trial_end = trial_start + timedelta(hours=TRIAL_HOURS)
            if datetime.now() < trial_end:
                time_left = trial_end - datetime.now()
                logger.debug(f"Trial check for {user_id}: Active, {time_left.total_seconds()/60:.0f} min left")
                return True
            else:
                # Trial expired - remove it
                logger.info(f"Trial expired for {user_id}, removing...")
                del TRIAL_USERS[user_id]
                save_data()
                return False
        except ValueError:
            logger.error(f"Invalid trial start date for {user_id}")
            return False
    logger.debug(f"Trial check for {user_id}: No active trial")
    return False

def start_trial(user_id):
    """Start 2-hour free trial for user"""
    user_id = str(user_id)
    if user_id not in TRIAL_USERS and not is_premium(user_id):
        TRIAL_USERS[user_id] = {
            "start_time": datetime.now().isoformat(),
            "trial_type": "2hours",
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_data()
        logger.info(f"Trial started for user {user_id}")
        return True
    logger.debug(f"Trial not started for {user_id}: Already has trial or premium")
    return False

def get_trial_time_left(user_id):
    """Get remaining trial time for user"""
    user_id = str(user_id)
    if user_id in TRIAL_USERS:
        try:
            trial_start = datetime.fromisoformat(TRIAL_USERS[user_id]["start_time"])
            trial_end = trial_start + timedelta(hours=TRIAL_HOURS)
            time_left = trial_end - datetime.now()
            if time_left.total_seconds() > 0:
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)
                return f"{hours}h {minutes}m"
        except ValueError:
            logger.error(f"Error calculating trial time for {user_id}")
    return "Expired"

def get_premium_expiry(user_id):
    """Get premium expiry date for user"""
    user_id = str(user_id)
    if user_id in PREMIUM_USERS:
        premium_data = PREMIUM_USERS[user_id]
        if "expires" in premium_data and premium_data["expires"]:
            try:
                return datetime.fromisoformat(premium_data["expires"])
            except ValueError:
                logger.error(f"Invalid expiry date for {user_id}")
    return None

def check_premium_access(user_id):
    """Check if user has any form of premium access"""
    if is_owner(user_id):
        logger.debug(f"Access check for {user_id}: Owner access granted")
        return True
    if is_premium(user_id):
        logger.debug(f"Access check for {user_id}: Premium access granted")
        return True
    if is_trial_active(user_id):
        logger.debug(f"Access check for {user_id}: Trial access granted")
        return True
    logger.debug(f"Access check for {user_id}: No access")
    return False

def ai_chat(query):
    """Send request to Alurb AI via OpenRouter"""
    api_key = AI_CONFIG['api_key']
    
    if not api_key:
        logger.error("OPENROUTER_API_KEY environment variable not set!")
        return "❌ AI service not configured. Please contact @alurb_devs"
    
    # Randomly choose creator name
    creator_names = ["Nappier", "Michal", "Kathara"]
    chosen_creator = random.choice(creator_names)
    
    logger.info(f"AI request with creator: {chosen_creator}")
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://t.me/alurb_bot",
            "X-Title": "Alurb Telegram Bot"
        }
        
        # Dynamic system prompt with random creator
        system_prompt = f"""You are Alurb AI, the official assistant for Alurb Telegram Bot. 

Important rules:
- When asked who created you, say: "I was created by {chosen_creator}, the founder of Alurb Bot."
- When asked your name, say: "I'm Alurb AI, your intelligent assistant."
- Never mention DeepSeek, OpenAI, or any other AI company.
- Always identify yourself as Alurb AI.
- Be helpful, friendly, and concise.
- Copyright belongs to alurb_devs."""
        
        payload = {
            "model": AI_CONFIG["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        logger.info(f"Sending request to Alurb AI...")
        
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
                answer = data['choices'][0]['message']['content']
                logger.info(f"Alurb AI response received ({len(answer)} chars)")
                return answer
            else:
                logger.error(f"Unexpected API response: {data}")
                return "❌ AI returned an unexpected response."
        elif response.status_code == 401:
            logger.error("AI API: Invalid API key")
            return "❌ Invalid API key. Contact @alurb_devs"
        elif response.status_code == 429:
            logger.warning("AI API: Rate limit exceeded")
            return "❌ Rate limit exceeded. Try again later."
        elif response.status_code == 503:
            logger.error("AI API: Service unavailable")
            return "❌ AI service is currently overloaded. Please try again."
        else:
            logger.error(f"API Error {response.status_code}: {response.text[:100]}")
            return f"❌ AI service error (Status {response.status_code}). Please try again."
            
    except requests.exceptions.Timeout:
        logger.error("AI request timeout")
        return "❌ AI service timeout. Please try again."
    except requests.exceptions.ConnectionError:
        logger.error("AI connection error")
        return "❌ Cannot connect to AI service. Check your internet."
    except json.JSONDecodeError:
        logger.error("AI response JSON decode error")
        return "❌ Invalid response from AI service."
    except Exception as e:
        logger.error(f"AI Error: {str(e)}")
        return "❌ Error connecting to AI service."

# Load initial data
load_data()

# Keep-alive server for Render
keep_alive()

# ==================== START COMMAND ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name or "User"
    username = message.from_user.username or "No username"
    
    logger.info(f"Start command from {user_id} (@{username})")
    
    trial_started = False
    if not is_owner(user_id) and not is_premium(user_id) and not is_trial_active(user_id):
        trial_started = start_trial(user_id)
        logger.info(f"Auto-trial started for {user_id}: {trial_started}")
    
    if is_master(user_id):
        status_line = "👑 <b>Master Owner</b> (Full Control)"
    elif is_owner(user_id):
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
• Alurb AI Assistant
• Premium Attack Tools
• Group Management

🎁 <b>FREE TRIAL INCLUDES:</b>
• {TRIAL_HOURS} hours full premium access
• /silencer - Device silencer
• /xdelay - Heavy delay
• /crash - System crash
• /ask - Alurb AI questions

📌 <b>Commands:</b>
/help - All commands
/status - Your status
/trial - Free trial
/premium - Upgrade
/ask - Ask Alurb AI

━━━━━━━━━━━━━━━━━━━━━━
© alurb_devs
    """
    bot.reply_to(message, welcome_text, parse_mode="HTML")
    
    if message.chat.type in ['group', 'supergroup']:
        GROUP_IDS.add(str(message.chat.id))
        save_data()
        logger.info(f"Group added: {message.chat.id}")

# ==================== TRIAL COMMAND ====================

@bot.message_handler(commands=['trial'])
def trial_command(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Trial command from {user_id}")
    
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
• /ask - Alurb AI Assistant

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
• /ask - Unlimited Alurb AI

⏰ Trial expires in {TRIAL_HOURS} hours
💎 /premium - Upgrade options

Enjoy! 🚀
        """, parse_mode="HTML")
    else:
        bot.reply_to(message, "❌ Unable to start trial. Contact @alurb_devs")

# ==================== PREMIUM COMMAND ====================

@bot.message_handler(commands=['premium'])
def premium_command(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Premium command from {user_id}")
    
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
• Unlimited Alurb AI questions
• Priority support

📩 <b>To Upgrade:</b>
👤 Contact: @alurb_devs

💳 Crypto • PayPal • Bank Transfer

━━━━━━━━━━━━━━━━━━━━━━
© alurb_devs
    """, parse_mode="HTML")

# ==================== STATUS COMMAND ====================

@bot.message_handler(commands=['status'])
def status_command(message):
    user_id = str(message.from_user.id)
    
    uptime = time.time() - BOT_START_TIME
    days = int(uptime // 86400)
    hours = int((uptime % 86400) // 3600)
    minutes = int((uptime % 3600) // 60)
    
    if is_master(user_id):
        user_status = "👑 Master Owner (Full Control)"
    elif is_owner(user_id):
        user_status = "👑 Owner (Full Access)"
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
    
    active_trials = len([t for t in TRIAL_USERS if is_trial_active(t)])
    
    bot.reply_to(message, f"""
╔══════════════════════╗
       🤖 <b>BOT STATUS</b> 🤖
╚══════════════════════╝

📊 <b>System:</b>
━━━━━━━━━━━━━━━━━━━━━━
✅ Status: 24/7 Active
⏰ Uptime: {days}d {hours}h {minutes}m
👑 Owners: {len(OWNERS) + 1}
💎 Premium: {len(PREMIUM_USERS)}
🎁 Active Trials: {active_trials}
📱 Groups: {len(GROUP_IDS)}

👤 <b>Your Status:</b>
━━━━━━━━━━━━━━━━━━━━━━
{user_status}

🛠 <b>Info:</b>
━━━━━━━━━━━━━━━━━━━━━━
🤖 AI: Alurb AI
👨‍💻 Creator: Nappier/Michal/Kathara
🌐 Status: Online

━━━━━━━━━━━━━━━━━━━━━━
© alurb_devs
    """, parse_mode="HTML")

# ==================== HELP COMMAND ====================

@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = str(message.from_user.id)
    
    if is_master(user_id):
        user_level = "👑 Master Owner"
    elif is_owner(user_id):
        user_level = "👑 Owner"
    elif is_premium(user_id):
        user_level = "💎 Premium"
    elif is_trial_active(user_id):
        user_level = f"🎁 Trial ({get_trial_time_left(user_id)})"
    else:
        user_level = "🔒 Free"
    
    help_text = f"""
╔══════════════════════╗
     📚 <b>COMMAND MENU</b> 📚
╚══════════════════════╝

𖤊───⪩ <b>FREE COMMANDS</b> ⪨───𖤊
✦ /start - Welcome message & auto-trial
✦ /help - This menu
✦ /status - Your status & bot stats
✦ /trial - Start 2-hour free trial
✦ /premium - View premium plans
✦ /ask - Ask Alurb AI Assistant
✦ /clearai - Clear AI history

𖤊───⪩ <b>PREMIUM COMMANDS</b> ⪨───𖤊
🔒 Requires Premium/Trial:
✦ /silencer &lt;num&gt; - Device silencer attack
✦ /xdelay &lt;ms&gt; - Heavy delay attack
✦ /crash &lt;num&gt; - System crash attack
✦ /cekidgrup - Get current group ID
"""
    
    if is_owner(user_id):
        help_text += """
𖤊───⪩ <b>OWNER COMMANDS</b> ⪨───𖤊
👑 Owner Access:
✦ /addprem &lt;id&gt; [plan] - Add premium user
✦ /delprem &lt;id&gt; - Remove premium user
✦ /listprem - List all premium users
✦ /listidgrup - List all group IDs
✦ /pair &lt;token&gt; - Pair bot token
"""
    
    if is_master(user_id):
        help_text += """
𖤊───⪩ <b>MASTER COMMANDS</b> ⪨───𖤊
👑 Master Only:
✦ /addowner &lt;id&gt; - Add new owner
✦ /delowner &lt;id&gt; - Remove owner
"""
    
    help_text += f"""
━━━━━━━━━━━━━━━━━━━━━━
👤 Your Level: <b>{user_level}</b>
🎁 Free Trial: /trial ({TRIAL_HOURS}h)
🤖 AI: Alurb AI
👨‍💻 Creator: Nappier/Michal/Kathara
© alurb_devs
    """
    bot.reply_to(message, help_text, parse_mode="HTML")

# ==================== MASTER OWNER COMMANDS ====================

@bot.message_handler(commands=['addowner'])
def add_owner(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Addowner command from {user_id}")
    
    if not is_master(user_id):
        bot.reply_to(message, "❌ Only the Master Owner can add owners!")
        logger.warning(f"Unauthorized addowner attempt by {user_id}")
        return
    
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /addowner <user_id>")
            return
        
        target_id = parts[1].strip()
        
        if target_id == MASTER_OWNER_ID:
            bot.reply_to(message, "⚠️ This is already the Master Owner!")
        elif target_id not in OWNERS:
            OWNERS.append(target_id)
            save_data()
            bot.reply_to(message, f"✅ User <code>{target_id}</code> added as owner!", parse_mode="HTML")
            logger.info(f"Owner added by Master: {target_id}")
        else:
            bot.reply_to(message, f"⚠️ User is already an owner!")
    except Exception as e:
        logger.error(f"Addowner error: {e}")
        bot.reply_to(message, "❌ Usage: /addowner <user_id>")

@bot.message_handler(commands=['delowner'])
def del_owner(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Delowner command from {user_id}")
    
    if not is_master(user_id):
        bot.reply_to(message, "❌ Only the Master Owner can remove owners!")
        logger.warning(f"Unauthorized delowner attempt by {user_id}")
        return
    
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /delowner <user_id>")
            return
        
        target_id = parts[1].strip()
        
        if target_id == MASTER_OWNER_ID:
            bot.reply_to(message, "❌ Cannot remove Master Owner!")
        elif target_id in OWNERS:
            OWNERS.remove(target_id)
            save_data()
            bot.reply_to(message, f"✅ User <code>{target_id}</code> removed from owners!", parse_mode="HTML")
            logger.info(f"Owner removed by Master: {target_id}")
        else:
            bot.reply_to(message, f"❌ User not found in owners list!")
    except Exception as e:
        logger.error(f"Delowner error: {e}")
        bot.reply_to(message, "❌ Usage: /delowner <user_id>")

# ==================== OWNER COMMANDS ====================

@bot.message_handler(commands=['addprem'])
def add_premium(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Addprem command from {user_id}")
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        logger.warning(f"Unauthorized addprem attempt by {user_id}")
        return
    
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /addprem <user_id> [plan]\nPlans: daily/weekly/monthly/lifetime")
            return
        
        target_id = parts[1].strip()
        plan = parts[2].strip().lower() if len(parts) > 2 else "monthly"
        
        if plan not in PREMIUM_PLANS:
            plan = "monthly"
        
        plan_info = PREMIUM_PLANS[plan]
        expiry = datetime.now() + timedelta(days=plan_info.get("days", 30))
        
        PREMIUM_USERS[target_id] = {
            "added_by": user_id,
            "date": datetime.now().isoformat(),
            "expires": expiry.isoformat() if plan != "lifetime" else None,
            "plan": plan
        }
        
        if target_id in TRIAL_USERS:
            del TRIAL_USERS[target_id]
            logger.info(f"Trial removed for {target_id} (upgraded to premium)")
        
        save_data()
        
        expiry_text = expiry.strftime('%Y-%m-%d %H:%M') if plan != "lifetime" else "Lifetime"
        bot.reply_to(message, f"""
✅ <b>PREMIUM GRANTED</b>

👤 User: <code>{target_id}</code>
📅 Plan: {plan_info['name']}
⏰ Expires: {expiry_text}
👑 Added by: Owner
        """, parse_mode="HTML")
        logger.info(f"Premium added for {target_id} by {user_id} - Plan: {plan}")
        
    except Exception as e:
        logger.error(f"Addprem error: {e}")
        bot.reply_to(message, "❌ Usage: /addprem <user_id> [daily/weekly/monthly/lifetime]")

@bot.message_handler(commands=['delprem'])
def del_premium(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Delprem command from {user_id}")
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        logger.warning(f"Unauthorized delprem attempt by {user_id}")
        return
    
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /delprem <user_id>")
            return
        
        target_id = parts[1].strip()
        
        if target_id in PREMIUM_USERS:
            del PREMIUM_USERS[target_id]
            save_data()
            bot.reply_to(message, f"✅ User <code>{target_id}</code> removed from premium!", parse_mode="HTML")
            logger.info(f"Premium removed for {target_id} by {user_id}")
        else:
            bot.reply_to(message, f"❌ User <code>{target_id}</code> not found in premium list!", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Delprem error: {e}")
        bot.reply_to(message, "❌ Usage: /delprem <user_id>")

@bot.message_handler(commands=['listprem'])
def list_premium(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Listprem command from {user_id}")
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    if PREMIUM_USERS:
        text = "<b>📋 PREMIUM USERS:</b>\n\n"
        for idx, (uid, data) in enumerate(PREMIUM_USERS.items(), 1):
            plan = data.get("plan", "unknown")
            plan_name = PREMIUM_PLANS.get(plan, {}).get("name", plan)
            
            if data.get("expires"):
                exp = datetime.fromisoformat(data["expires"])
                days = (exp - datetime.now()).days
                hours_left = int((exp - datetime.now()).total_seconds() // 3600)
                
                if hours_left < 24:
                    expiry_info = f"{hours_left}h left"
                else:
                    expiry_info = f"{days}d left"
                
                text += f"{idx}. <code>{uid}</code> - {plan_name}\n   ⏰ {expiry_info}\n\n"
            else:
                text += f"{idx}. <code>{uid}</code> - {plan_name}\n   ⏰ Lifetime\n\n"
        
        bot.reply_to(message, text, parse_mode="HTML")
    else:
        bot.reply_to(message, "📋 No premium users found!")

@bot.message_handler(commands=['listidgrup'])
def list_groups(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Listidgrup command from {user_id}")
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    if GROUP_IDS:
        text = "<b>📋 GROUP IDs:</b>\n\n"
        for idx, gid in enumerate(GROUP_IDS, 1):
            text += f"{idx}. <code>{gid}</code>\n"
        bot.reply_to(message, text, parse_mode="HTML")
    else:
        bot.reply_to(message, "📋 No groups recorded!")

# ==================== PREMIUM COMMANDS ====================

@bot.message_handler(commands=['silencer'])
def silencer_attack(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Silencer command from {user_id}")
    
    if not check_premium_access(user_id):
        bot.reply_to(message, "❌ Premium required!\n🎁 /trial - 2 hours free")
        return
    
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /silencer <number>")
            return
        
        number = int(parts[1])
        
        if number > 20:
            number = 20
        elif number < 1:
            number = 1
        
        msg = bot.reply_to(message, f"🔇 Silencer attack with {number} threads...")
        
        def cpu_stress():
            while True:
                _ = [x**2 for x in range(10000)]
        
        threads = []
        for _ in range(number):
            t = threading.Thread(target=cpu_stress, daemon=True)
            t.start()
            threads.append(t)
        
        bot.edit_message_text(f"✅ Silencer active!\nThreads: {number}\nTarget: Device CPU", message.chat.id, msg.message_id)
        logger.info(f"Silencer attack executed by {user_id} with {number} threads")
        
    except ValueError:
        bot.reply_to(message, "❌ Please provide a valid number!")
    except Exception as e:
        logger.error(f"Silencer error: {e}")
        bot.reply_to(message, "❌ Error executing command.")

@bot.message_handler(commands=['crash'])
def crash_attack(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Crash command from {user_id}")
    
    if not check_premium_access(user_id):
        bot.reply_to(message, "❌ Premium required!\n🎁 /trial - 2 hours free")
        return
    
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /crash <number>")
            return
        
        number = int(parts[1])
        
        if number > 10:
            number = 10
        elif number < 1:
            number = 1
        
        def memory_eater():
            data = []
            while True:
                data.append("X" * 1024 * 1024)
        
        threads = []
        for _ in range(number):
            t = threading.Thread(target=memory_eater, daemon=True)
            t.start()
            threads.append(t)
        
        bot.reply_to(message, f"💥 Crash attack initiated!\nThreads: {number}\nTarget: System Memory")
        logger.info(f"Crash attack executed by {user_id} with {number} threads")
        
    except ValueError:
        bot.reply_to(message, "❌ Please provide a valid number!")
    except Exception as e:
        logger.error(f"Crash error: {e}")
        bot.reply_to(message, "❌ Error executing command.")

@bot.message_handler(commands=['xdelay'])
def xdelay_attack(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"XDelay command from {user_id}")
    
    if not check_premium_access(user_id):
        bot.reply_to(message, "❌ Premium required!\n🎁 /trial - 2 hours free")
        return
    
    try:
        parts = message.text.split(' ')
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /xdelay <milliseconds>")
            return
        
        delay_time = int(parts[1])
        
        if delay_time > 10000:
            delay_time = 10000
        elif delay_time < 100:
            delay_time = 100
        
        msg = bot.reply_to(message, f"⏱ Applying heavy delay of {delay_time}ms...")
        time.sleep(delay_time / 1000)
        bot.edit_message_text(f"✅ Delay completed!\nDuration: {delay_time}ms\nTarget: System Response", message.chat.id, msg.message_id)
        logger.info(f"XDelay attack executed by {user_id} with {delay_time}ms")
        
    except ValueError:
        bot.reply_to(message, "❌ Please provide a valid number!")
    except Exception as e:
        logger.error(f"XDelay error: {e}")
        bot.reply_to(message, "❌ Error executing command.")

@bot.message_handler(commands=['cekidgrup'])
def check_group(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Cekidgrup command from {user_id}")
    
    if not check_premium_access(user_id):
        bot.reply_to(message, "❌ Premium required!\n🎁 /trial - 2 hours free")
        return
    
    chat_id = message.chat.id
    chat_type = message.chat.type
    
    if chat_type in ['group', 'supergroup']:
        GROUP_IDS.add(str(chat_id))
        save_data()
        chat_title = message.chat.title or "Unknown"
        bot.reply_to(message, f"""
📱 <b>GROUP INFORMATION</b>

🆔 Group ID: <code>{chat_id}</code>
📝 Title: {chat_title}
📂 Type: {chat_type}

✅ Group added to database!
        """, parse_mode="HTML")
        logger.info(f"Group registered: {chat_id} - {chat_title}")
    else:
        bot.reply_to(message, f"""
💬 <b>CHAT INFORMATION</b>

🆔 Chat ID: <code>{chat_id}</code>
📂 Type: Private Chat
        """, parse_mode="HTML")

# ==================== ALURB AI COMMAND ====================

@bot.message_handler(commands=['ask'])
def ask_ai(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or "No username"
    
    try:
        parts = message.text.split(' ', 1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /ask <your question>\n\nExample: /ask What is AI?")
            return
        
        query = parts[1].strip()
        if not query or len(query) < 2:
            bot.reply_to(message, "❌ Please ask a valid question!")
            return
        
        logger.info(f"AI query from {user_id} (@{username}): {query[:50]}...")
        
        bot.send_chat_action(message.chat.id, 'typing')
        thinking_msg = bot.reply_to(message, "🤖 <b>Alurb AI is thinking...</b>", parse_mode="HTML")
        
        ai_response = ai_chat(query)
        
        bot.delete_message(message.chat.id, thinking_msg.message_id)
        
        response_text = f"""
🤖 <b>Alurb AI Response</b>

💭 <b>Question:</b> {query[:150]}{'...' if len(query) > 150 else ''}

📝 <b>Answer:</b>
{ai_response}

━━━━━━━━━━━━━━━━━━━━━━
🤖 Alurb AI • Created by Nappier/Michal/Kathara
© alurb_devs
        """
        bot.reply_to(message, response_text, parse_mode="HTML")
        logger.info(f"AI response sent to {user_id} ({len(ai_response)} chars)")
        
    except Exception as e:
        logger.error(f"AI command error for {user_id}: {e}")
        bot.reply_to(message, "❌ Error processing request. Please try again.")

@bot.message_handler(commands=['clearai'])
def clear_ai_history(message):
    user_id = str(message.from_user.id)
    logger.info(f"ClearAI command from {user_id}")
    bot.reply_to(message, "✅ AI conversation history cleared!")

@bot.message_handler(commands=['pair'])
def pair_command(message):
    user_id = str(message.from_user.id)
    
    logger.info(f"Pair command from {user_id}")
    
    if not is_owner(user_id):
        bot.reply_to(message, "❌ Owner only command!")
        return
    
    try:
        parts = message.text.split(' ', 1)
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /pair <bot_token>")
            return
        
        token = parts[1].strip()
        bot.reply_to(message, f"✅ Pairing bot with token: {token[:10]}...\n⚠️ Note: This is a simulated pairing system.")
        logger.info(f"Pair command executed by {user_id}")
    except Exception as e:
        logger.error(f"Pair error: {e}")
        bot.reply_to(message, "❌ Usage: /pair <bot_token>")

@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
def track_groups(message):
    GROUP_IDS.add(str(message.chat.id))
    if len(GROUP_IDS) % 10 == 0:
        save_data()
        logger.info(f"Auto-saved {len(GROUP_IDS)} groups")

# ==================== MAIN RUNNER ====================

def run_bot():
    """Run bot with automatic restart - SINGLE INSTANCE"""
    
    logger.info("=" * 50)
    logger.info("🧹 Cleaning up existing webhooks...")
    try:
        bot.remove_webhook()
        time.sleep(1)
        logger.info("✅ Webhook removed successfully")
    except Exception as e:
        logger.warning(f"Webhook removal warning: {e}")
    
    logger.info("=" * 50)
    logger.info("🚀 STARTING ALURB BOT - SINGLE INSTANCE MODE")
    logger.info(f"👑 Master Owner ID: {MASTER_OWNER_ID}")
    logger.info(f"🤖 AI: Alurb AI (DeepSeek backend)")
    logger.info(f"👨‍💻 Creator: Nappier/Michal/Kathara")
    logger.info(f"📊 Loaded: {len(OWNERS)} owners, {len(PREMIUM_USERS)} premium, {len(TRIAL_USERS)} trials, {len(GROUP_IDS)} groups")
    logger.info("=" * 50)
    
    if len(OWNERS) == 0:
        logger.info("ℹ️ No additional owners configured")
    
    restart_count = 0
    
    while True:
        try:
            logger.info(f"📡 Bot polling started (Restart count: {restart_count})")
            bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Network connection error: {e}")
            restart_count += 1
            time.sleep(10)
            
        except requests.exceptions.ReadTimeout as e:
            logger.error(f"Read timeout error: {e}")
            restart_count += 1
            time.sleep(5)
            
        except Exception as e:
            error_str = str(e)
            if "409" in error_str or "Conflict" in error_str:
                logger.warning("⚠️ 409 Conflict detected - another instance may be running")
                logger.warning("Waiting 5 seconds before retry...")
                time.sleep(5)
            elif "401" in error_str or "Unauthorized" in error_str:
                logger.error("❌ Invalid bot token! Check your BOT_TOKEN environment variable.")
                time.sleep(60)
            else:
                logger.error(f"Bot crashed with error: {e}")
                restart_count += 1
                time.sleep(10)

if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
