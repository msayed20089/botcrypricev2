import logging
import sqlite3
import random
import asyncio
import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# إعدادات البوت
BOT_TOKEN = os.getenv("BOT_TOKEN", "8399150202:AAEvr37r05xzbjhwinnGZQIWAuoylpsNflg").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "6096879850"))
BOT_USERNAME = "lllllllofdkokbot"

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# قاعدة البيانات
def init_db():
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 3,
            invited_by INTEGER DEFAULT 0,
            total_invites INTEGER DEFAULT 0,
            notifications BOOLEAN DEFAULT TRUE,
            language TEXT DEFAULT 'ar',
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roulettes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER,
            channel_id TEXT,
            message_id INTEGER,
            roulette_text TEXT,
            winners_count INTEGER DEFAULT 1,
            forced_channels TEXT DEFAULT '[]',
            max_participants INTEGER DEFAULT 10,
            current_participants INTEGER DEFAULT 0,
            status TEXT DEFAULT 'waiting',
            winner_id INTEGER DEFAULT NULL,
            prize INTEGER DEFAULT 0,
            is_paused BOOLEAN DEFAULT FALSE,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roulette_id INTEGER,
            user_id INTEGER,
            user_name TEXT,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_username TEXT,
            channel_id TEXT,
            is_approved BOOLEAN DEFAULT FALSE,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS forced_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_username TEXT,
            channel_id TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            added_by INTEGER DEFAULT 0,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # إضافة القناة الإجبارية الافتراضية
    cursor.execute('INSERT OR IGNORE INTO forced_channels (channel_username, channel_id, added_by) VALUES (?, ?, ?)', 
                  ("zforexms", "@zforexms", ADMIN_ID))
    
    conn.commit()
    conn.close()

# دوال المساعدة
def get_user(user_id):
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name, invited_by=0):
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, invited_by, balance) 
        VALUES (?, ?, ?, ?, 3)
    ''', (user_id, username, first_name, invited_by))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 3

def get_user_channel(user_id):
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT channel_username, channel_id FROM user_channels WHERE user_id = ? AND is_approved = TRUE', (user_id,))
    channel = cursor.fetchone()
    conn.close()
    return channel

def add_user_channel(user_id, channel_username, channel_id):
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO user_channels (user_id, channel_username, channel_id, is_approved) 
        VALUES (?, ?, ?, TRUE)
    ''', (user_id, channel_username, channel_id))
    conn.commit()
    conn.close()

def get_forced_channels():
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT channel_username, channel_id FROM forced_channels WHERE is_active = TRUE')
    channels = cursor.fetchall()
    conn.close()
    return channels

def add_forced_channel(channel_username, channel_id, added_by=0):
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO forced_channels (channel_username, channel_id, added_by) VALUES (?, ?, ?)', 
                  (channel_username, channel_id, added_by))
    conn.commit()
    conn.close()

async def check_channel_subscription(user_id, channel_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking subscription: {e}")
        return False

async def check_bot_admin(channel_id, context):
    try:
        bot_member = await context.bot.get_chat_member(chat_id=channel_id, user_id=context.bot.id)
        return bot_member.status in ['administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking bot admin: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # معالجة رابط الدعوة
    args = context.args
    invited_by = 0
    if args and args[0].startswith('ref_'):
        try:
            invited_by = int(args[0].split('_')[1])
            # إرسال إشعار للداعي
            try:
                await context.bot.send_message(
                    invited_by,
                    f"🎉 *مستخدم جديد انضم عبر رابطك!*\n\n👤 الاسم: {user.first_name}\n🆔 الإيدي: {user_id}\n\n💰 لقد ربحت نقطة واحدة!",
                    parse_mode='Markdown'
                )
            except:
                pass
            
            update_balance(invited_by, 1)
            
            conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET total_invites = total_invites + 1 WHERE user_id = ?', (invited_by,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error in referral: {e}")

    if not get_user(user_id):
        create_user(user_id, user.username, user.first_name, invited_by)

    await show_main_menu(update, user_id)

async def show_main_menu(update, user_id, message_text=None):
    balance = get_balance(user_id)
    user_channel = get_user_channel(user_id)
    
    channel_status = "❌ غير مضبوطة"
    if user_channel:
        channel_status = f"✅ @{user_channel[0]}"
    
    if message_text is None:
        user = update.effective_user if hasattr(update, 'effective_user') else update.callback_query.from_user
        message_text = f"""✨ **مرحباً بك في روليت MS** 

⚡ *أفضل بوت سحوبات على التليجرام*

🎰 **أنشئ روليت مجاني في قناتك!**

🆔 الإيدي: `{user_id}`
💰 رصيدك: *{balance} نقطة*"""

    keyboard = [
        [InlineKeyboardButton("🎰 إنشاء روليت", callback_data="create_roulette")],
        [InlineKeyboardButton("⚡ إنشاء روليت سريع", callback_data="create_quick_roulette")],
        [InlineKeyboardButton(f"📢 قناتك ({channel_status})", callback_data="channel_settings")],
        [InlineKeyboardButton("🔑 كود روليت مشترك", callback_data="shared_code")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
        [InlineKeyboardButton("📤 رابط الدعوة", callback_data="invite_link")],
        [InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "create_roulette":
        await create_roulette_handler(query, context)
    elif data == "create_quick_roulette":
        await create_quick_roulette(query, context)
    elif data == "channel_settings":
        await channel_settings(query, context)
    elif data == "shared_code":
        await shared_code_menu(query, context)
    elif data == "my_stats":
        await my_stats(query, context)
    elif data == "invite_link":
        await invite_link(query, context)
    elif data == "settings":
        await settings_menu(query, context)
    elif data.startswith("join_"):
        await join_roulette(query, context)
    elif data.startswith("start_"):
        await start_roulette(query, context)
    elif data.startswith("view_"):
        await view_participants(query, context)
    elif data.startswith("pause_"):
        await pause_roulette(query, context)
    elif data.startswith("resume_"):
        await resume_roulette(query, context)
    elif data == "main_menu":
        await show_main_menu(update, user_id)
    elif data == "add_channel":
        await add_channel_prompt(query, context)
    elif data == "remove_channel":
        await remove_channel(query, context)
    elif data.startswith("winners_"):
        winners_count = int(data.split('_')[1])
        await handle_winners_count(query, context, winners_count)
    elif data == "more_winners":
        await show_more_winners(query, context)
    elif data == "skip_conditions":
        await skip_conditions_and_create(query, context)
    elif data == "add_condition_channel":
        await add_condition_channel_prompt(query, context)
    elif data == "boost_channel":
        await boost_channel(query, context)
    elif data == "instructions":
        await show_instructions(query, context)
    elif data == "support":
        await show_support(query, context)
    elif data == "contribute":
        await show_contribute(query, context)
    elif data == "remind_me":
        await toggle_reminder(query, context)

async def create_roulette_handler(query, context):
    user_id = query.from_user.id
    
    await query.edit_message_text(
        "📝 **أرسل نص الروليت:**\n\n"
        "🎨 *يمكنك استخدام هذه البلوكات لتنسيق النص:*\n\n"
        "🔸 للتشويش:\n`<tg-spoiler>النص</tg-spoiler>`\n\n"
        "🔸 للتعريض:\n`<b>النص</b>`\n\n"
        "🔸 للنص المائل:\n`<i>النص</i>`\n\n"
        "🔸 للمقتبس:\n`<blockquote>النص</blockquote>`\n\n"
        "⚠️ **رجاءً عدم إرسال أي روابط نهائياً**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]
        ]),
        parse_mode='Markdown'
    )
    
    context.user_data['waiting_for_roulette_text'] = True
    context.user_data['creating_roulette'] = True

async def handle_roulette_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if context.user_data.get('waiting_for_roulette_text'):
        context.user_data['roulette_text'] = text
        context.user_data['waiting_for_roulette_text'] = False
        
        await update.message.reply_text(
            "🎯 **اختر عدد الفائزين:**",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("1", callback_data="winners_1"),
                    InlineKeyboardButton("2", callback_data="winners_2"),
                    InlineKeyboardButton("3", callback_data="winners_3")
                ],
                [
                    InlineKeyboardButton("4", callback_data="winners_4"),
                    InlineKeyboardButton("5", callback_data="winners_5"),
                    InlineKeyboardButton("6", callback_data="winners_6")
                ],
                [
                    InlineKeyboardButton("7", callback_data="winners_7"),
                    InlineKeyboardButton("8", callback_data="winners_8"),
                    InlineKeyboardButton("9", callback_data="winners_9")
                ],
                [InlineKeyboardButton("10", callback_data="winners_10")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="create_roulette")]
            ]),
            parse_mode='Markdown'
        )

async def handle_winners_count(query, context, winners_count):
    user_id = query.from_user.id
    context.user_data['winners_count'] = winners_count
    
    forced_channels = get_forced_channels()
    
    if forced_channels:
        channels_text = "\n".join([f"• @{channel[0]}" for channel in forced_channels])
        conditions_text = f"\n\n📋 **القنوات الإجبارية:**\n{channels_text}"
    else:
        conditions_text = ""
    
    await query.edit_message_text(
        f"🔒 **إعدادات الروليت**\n\n"
        f"🎯 عدد الفائزين: *{winners_count}*"
        f"{conditions_text}\n\n"
        "🌟 **اختر الخيار المناسب:**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ إضافة قناة شرط", callback_data="add_condition_channel")],
            [InlineKeyboardButton("✨ تعزيز القناة (مجاناً)", callback_data="boost_channel")],
            [InlineKeyboardButton("⏭ تخطي وإنشاء", callback_data="skip_conditions")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="create_roulette")]
        ]),
        parse_mode='Markdown'
    )

async def skip_conditions_and_create(query, context):
    user_id = query.from_user.id
    user_channel = get_user_channel(user_id)
    
    if not user_channel:
        await query.edit_message_text(
            "❌ **يجب عليك ربط قناة أولاً!**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 ربط القناة", callback_data="channel_settings")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    # جمع القنوات الإجبارية
    forced_channels = get_forced_channels()
    forced_channels_ids = [channel[1] for channel in forced_channels]
    
    # إنشاء الروليت
    roulette_text = context.user_data.get('roulette_text', '🎰 روليت سريع')
    winners_count = context.user_data.get('winners_count', 1)
    
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO roulettes (creator_id, channel_id, roulette_text, winners_count, forced_channels, max_participants) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, user_channel[1], roulette_text, winners_count, json.dumps(forced_channels_ids), 10))
    roulette_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # إرسال الروليت إلى القناة
    try:
        # نص القنوات الإجبارية
        forced_text = ""
        if forced_channels:
            forced_text = "\n\n📋 **شروط المشاركة:**\n"
            for channel in forced_channels:
                forced_text += f"✅ الاشتراك في @{channel[0]}\n"
        
        roulette_message = f"""🎰 **روليت MS**

{roulette_text}

👤 **المنشئ:** {query.from_user.first_name}
🎯 **عدد الفائزين:** {winners_count}
📊 **المشاركون:** 0/10
⏳ في انتظار المشاركة...
{forced_text}

[روليت MS جميع السحوبات](https://t.me/{BOT_USERNAME})"""

        keyboard = [
            [InlineKeyboardButton("🎯 انضم للروليت", callback_data=f"join_{roulette_id}")],
            [InlineKeyboardButton("👀 مشاهدة المشاركين", callback_data=f"view_{roulette_id}")],
            [InlineKeyboardButton("🚀 بدء السحب", callback_data=f"start_{roulette_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = await context.bot.send_message(
            chat_id=user_channel[1],
            text=roulette_message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE roulettes SET message_id = ? WHERE id = ?', (message.message_id, roulette_id))
        conn.commit()
        conn.close()
        
        await query.edit_message_text(
            f"✅ **تم إنشاء الروليت بنجاح!**\n\n"
            f"📢 القناة: @{user_channel[0]}\n"
            f"🎯 عدد الفائزين: {winners_count}\n\n"
            f"📤 شارك الروليت مع أصدقائك!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error sending to channel: {e}")
        await query.edit_message_text(
            f"❌ فشل إنشاء الروليت!\n\nتأكد من صلاحيات البوت في القناة.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 ضبط القناة", callback_data="channel_settings")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )

async def create_quick_roulette(query, context):
    user_id = query.from_user.id
    user_channel = get_user_channel(user_id)
    
    if not user_channel:
        await query.edit_message_text(
            "❌ **يجب عليك ربط قناة أولاً!**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 ربط القناة", callback_data="channel_settings")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]),
            parse_mode='Markdown'
        )
        return
    
    # جمع القنوات الإجبارية
    forced_channels = get_forced_channels()
    forced_channels_ids = [channel[1] for channel in forced_channels]
    
    # إنشاء روليت سريع
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO roulettes (creator_id, channel_id, roulette_text, winners_count, forced_channels, max_participants) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, user_channel[1], "🎰 روليت سريع - MS روليت", 1, json.dumps(forced_channels_ids), 10))
    roulette_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # إرسال الروليت إلى القناة
    try:
        # نص القنوات الإجبارية
        forced_text = ""
        if forced_channels:
            forced_text = "\n\n📋 **شروط المشاركة:**\n"
            for channel in forced_channels:
                forced_text += f"✅ الاشتراك في @{channel[0]}\n"
        
        roulette_message = f"""🎰 **روليت سريع - MS روليت**

👤 **المنشئ:** {query.from_user.first_name}
🎯 **عدد الفائزين:** 1
📊 **المشاركون:** 0/10
⏳ في انتظار المشاركة...
{forced_text}

[روليت MS جميع السحوبات](https://t.me/{BOT_USERNAME})"""

        keyboard = [
            [InlineKeyboardButton("🎯 انضم للروليت", callback_data=f"join_{roulette_id}")],
            [InlineKeyboardButton("👀 مشاهدة المشاركين", callback_data=f"view_{roulette_id}")],
            [InlineKeyboardButton("🚀 بدء السحب", callback_data=f"start_{roulette_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = await context.bot.send_message(
            chat_id=user_channel[1],
            text=roulette_message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE roulettes SET message_id = ? WHERE id = ?', (message.message_id, roulette_id))
        conn.commit()
        conn.close()
        
        await query.edit_message_text(
            f"✅ **تم إنشاء الروليت السريع بنجاح!**\n\n"
            f"📢 القناة: @{user_channel[0]}\n\n"
            f"📤 شارك الروليت مع أصدقائك!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error sending to channel: {e}")
        await query.edit_message_text(
            f"❌ فشل إنشاء الروليت!\n\nتأكد من صلاحيات البوت في القناة.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 ضبط القناة", callback_data="channel_settings")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )

async def join_roulette(query, context):
    try:
        roulette_id = int(query.data.split('_')[1])
        user_id = query.from_user.id
        user_name = query.from_user.first_name
        
        conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # التحقق من المشاركة السابقة
        cursor.execute('SELECT * FROM participants WHERE roulette_id = ? AND user_id = ?', (roulette_id, user_id))
        if cursor.fetchone():
            await query.answer("✅ أنت مشترك بالفعل في هذا الروليت!", show_alert=True)
            conn.close()
            return
        
        # التحقق من حالة الروليت
        cursor.execute('SELECT status, current_participants, max_participants, channel_id, message_id, creator_id, forced_channels FROM roulettes WHERE id = ?', (roulette_id,))
        roulette = cursor.fetchone()
        
        if not roulette or roulette[0] != 'waiting':
            await query.answer("❌ الروليت غير متاح للانضمام!", show_alert=True)
            conn.close()
            return
        
        # التحقق من الاشتراك في القنوات الإجبارية
        forced_channels = json.loads(roulette[6]) if roulette[6] else []
        missing_channels = []
        
        for channel_id in forced_channels:
            is_subscribed = await check_channel_subscription(user_id, channel_id, context)
            if not is_subscribed:
                channel_username = channel_id.replace('@', '')
                missing_channels.append(f"@{channel_username}")
        
        if missing_channels:
            channels_text = "\n".join(missing_channels)
            await query.answer(f"❌ يجب الاشتراك في:\n{channels_text}", show_alert=True)
            conn.close()
            return
        
        # إضافة المشارك
        cursor.execute('INSERT INTO participants (roulette_id, user_id, user_name) VALUES (?, ?, ?)', (roulette_id, user_id, user_name))
        cursor.execute('UPDATE roulettes SET current_participants = current_participants + 1 WHERE id = ?', (roulette_id,))
        
        cursor.execute('SELECT current_participants FROM roulettes WHERE id = ?', (roulette_id,))
        current = cursor.fetchone()[0]
        
        conn.commit()
        
        # تحديث الرسالة في القناة
        try:
            cursor.execute('SELECT creator_id, roulette_text, winners_count FROM roulettes WHERE id = ?', (roulette_id,))
            roulette_info = cursor.fetchone()
            creator_id = roulette_info[0]
            roulette_text = roulette_info[1]
            winners_count = roulette_info[2]
            
            forced_text = ""
            if forced_channels:
                forced_text = "\n\n📋 **شروط المشاركة:**\n"
                for channel in forced_channels:
                    channel_name = channel.replace('@', '')
                    forced_text += f"✅ الاشتراك في @{channel_name}\n"
            
            roulette_message = f"""🎰 **روليت MS**

{roulette_text}

👤 **المنشئ:** {query.from_user.first_name}
🎯 **عدد الفائزين:** {winners_count}
📊 **المشاركون:** {current}/10
⏳ في انتظار المشاركة...
{forced_text}

[روليت MS جميع السحوبات](https://t.me/{BOT_USERNAME})"""

            keyboard = [
                [InlineKeyboardButton("🎯 انضم للروليت", callback_data=f"join_{roulette_id}")],
                [InlineKeyboardButton("👀 مشاهدة المشاركين", callback_data=f"view_{roulette_id}")],
                [InlineKeyboardButton("🚀 بدء السحب", callback_data=f"start_{roulette_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.edit_message_text(
                chat_id=roulette[3],
                message_id=roulette[4],
                text=roulette_message,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Error updating channel message: {e}")
        
        # إرسال إشعار للمنشئ
        try:
            await context.bot.send_message(
                creator_id,
                f"🎉 **مشاركة جديدة في سحبتك!**\n\n👤 المستخدم: {user_name}\n🆔 المعرف: {user_id}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👀 عرض الملف الشخصي", url=f"tg://user?id={user_id}")],
                    [InlineKeyboardButton("🚫 استبعاد", callback_data=f"exclude_{roulette_id}_{user_id}")]
                ]),
                parse_mode='Markdown'
            )
        except:
            pass
        
        conn.close()
        
        await query.answer(f"🎉 تم انضمامك للروليت بنجاح! ({current}/10)", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in join_roulette: {e}")
        await query.answer("⚠️ حدث خطأ أثناء الانضمام", show_alert=True)

async def start_roulette(query, context):
    try:
        roulette_id = int(query.data.split('_')[1])
        user_id = query.from_user.id
        
        conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT creator_id, current_participants, channel_id, message_id, winners_count, roulette_text FROM roulettes WHERE id = ?', (roulette_id,))
        roulette = cursor.fetchone()
        
        if not roulette or user_id != roulette[0]:
            await query.answer("❌ فقط منشئ الروليت يمكنه بدء السحب!", show_alert=True)
            conn.close()
            return
        
        if roulette[1] < 2:
            await query.answer("👥 يجب أن يكون هناك مشاركين على الأقل!", show_alert=True)
            conn.close()
            return
        
        # بدء الروليت واختيار الفائزين
        cursor.execute('SELECT user_id, user_name FROM participants WHERE roulette_id = ?', (roulette_id,))
        participants = cursor.fetchall()
        
        winners_count = roulette[4]
        winners = random.sample(participants, min(winners_count, len(participants)))
        
        cursor.execute('UPDATE roulettes SET status = "completed" WHERE id = ?', (roulette_id,))
        
        # تحديث الرسالة في القناة
        try:
            winners_text = "🎉 **الفائزون:**\n"
            for i, (winner_id, winner_name) in enumerate(winners, 1):
                winners_text += f"{i}. {winner_name}\n"
                update_balance(winner_id, 10)  # مكافأة الفائز
            
            participants_text = "👥 **المشاركون:**\n"
            for i, (pid, pname) in enumerate(participants, 1):
                participants_text += f"{i}. {pname}\n"
            
            roulette_text = f"""🎰 **روليت MS - مكتمل**

{roulette[5]}

{winners_text}

{participants_text}

🎁 **الجائزة:** 10 نقاط لكل فائز
✅ **السحب مكتمل**

[روليت MS جميع السحوبات](https://t.me/{BOT_USERNAME})"""

            await context.bot.edit_message_text(
                chat_id=roulette[2],
                message_id=roulette[3],
                text=roulette_text,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Error updating winner message: {e}")
        
        # إرسال رسالة للفائزين
        for winner_id, winner_name in winners:
            try:
                await context.bot.send_message(
                    winner_id,
                    f"🎉 **مبروك! فزت في الروليت** #{roulette_id}\n\n💰 ربحت 10 نقاط!\n\nرصيدك الجديد: {get_balance(winner_id)} نقطة 🎁",
                    parse_mode='Markdown'
                )
            except:
                pass
        
        conn.close()
        
        await query.answer("🎊 تم بدء السحب واختيار الفائزين!", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in start_roulette: {e}")
        await query.answer("⚠️ حدث خطأ أثناء بدء السحب", show_alert=True)

# باقي الدوال بنفس النمط مع التحديثات...

async def view_participants(query, context):
    try:
        roulette_id = int(query.data.split('_')[1])
        
        conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_name FROM participants WHERE roulette_id = ?', (roulette_id,))
        participants = cursor.fetchall()
        
        conn.close()
        
        if participants:
            participants_text = "👥 **المشاركون في الروليت:**\n\n"
            for i, (name,) in enumerate(participants, 1):
                participants_text += f"{i}. {name}\n"
            
            participants_text += f"\n📊 الإجمالي: {len(participants)} مشارك"
            await query.answer(participants_text, show_alert=True)
        else:
            await query.answer("❌ لا يوجد مشاركين بعد!", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in view_participants: {e}")
        await query.answer("⚠️ حدث خطأ", show_alert=True)

async def channel_settings(query, context):
    user_id = query.from_user.id
    user_channel = get_user_channel(user_id)
    
    if user_channel:
        text = f"📢 **إعدادات القناة**\n\nالقناة الحالية: @{user_channel[0]}\n\nيمكنك تغيير القناة أو فصلها:"
        keyboard = [
            [InlineKeyboardButton("🔄 تغيير القناة", callback_data="add_channel")],
            [InlineKeyboardButton("❌ فصل القناة", callback_data="remove_channel")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]
    else:
        text = "📢 **إعدادات القناة**\n\nلم تقم بربط قناة بعد.\n\nلإنشاء روليت، تحتاج إلى ربط قناة وإضافة البوت كأدمن فيها."
        keyboard = [
            [InlineKeyboardButton("➕ ربط القناة", callback_data="add_channel")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]
    
    await query.edit_message_text(
        text + "\n\n⚠️ **تأكد من إضافة البوت كأدمن في القناة**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def add_channel_prompt(query, context):
    await query.edit_message_text(
        "📥 **أرسل معرف القناة:**\n\nمثال: `@channel_username`\n\nيجب أن يكون البوت مشرفاً في القناة.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="channel_settings")]
        ]),
        parse_mode='Markdown'
    )

async def remove_channel(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_channels WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    await query.edit_message_text(
        "✅ **تم فصل القناة بنجاح!**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]),
        parse_mode='Markdown'
    )

async def handle_channel_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_roulette_text'):
        await handle_roulette_text(update, context)
        return
    
    channel_username = None
    channel_id = None
    
    if text.startswith('@'):
        channel_username = text[1:]
        channel_id = f"@{channel_username}"
    elif 't.me/' in text:
        parts = text.split('t.me/')
        if len(parts) > 1:
            channel_username = parts[1].split('/')[0].replace('@', '')
            channel_id = f"@{channel_username}"
    
    if channel_username:
        try:
            # اختبار إرسال رسالة إلى القناة
            test_message = await context.bot.send_message(
                chat_id=channel_id,
                text="🔧 اختبار اتصال البوت بالقناة..."
            )
            
            await context.bot.delete_message(chat_id=channel_id, message_id=test_message.message_id)
            
            add_user_channel(user_id, channel_username, channel_id)
            
            await update.message.reply_text(
                f"✅ **تم ربط القناة بنجاح!**\n\n📢 القناة: @{channel_username}\n\nيمكنك الآن إنشاء روليتات في قناتك. 🎰",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎰 إنشاء روليت", callback_data="create_roulette")],
                    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
                ]),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error testing channel: {e}")
            await update.message.reply_text(
                f"❌ **فشل ربط القناة!**\n\nتأكد من:\n• إضافة البوت كأدمن في القناة\n• صلاحية إرسال رسائل\n• أن المعرف صحيح\n\nالقناة: `{channel_id}`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 حاول مرة أخرى", callback_data="add_channel")],
                    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
                ]),
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(
            "❌ **صيغة غير صحيحة!**\n\nأرسل معرف القناة مثل:\n`@channel_username`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 حاول مرة أخرى", callback_data="add_channel")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ]),
            parse_mode='Markdown'
        )

async def shared_code_menu(query, context):
    await query.edit_message_text(
        "🔑 **كود الروليت المشترك**\n\n"
        "هذه الميزة تتيح لك مشاركة روليت مع أصدقائك باستخدام كود مشترك.\n\n"
        "🚧 **قيد التطوير...**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]),
        parse_mode='Markdown'
    )

async def my_stats(query, context):
    user_id = query.from_user.id
    balance = get_balance(user_id)
    
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT total_invites FROM users WHERE user_id = ?', (user_id,))
    invites = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM roulettes WHERE creator_id = ?', (user_id,))
    created = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM participants WHERE user_id = ?', (user_id,))
    joined = cursor.fetchone()[0]
    
    conn.close()
    
    stats_text = f"""📊 **إحصائياتك الشخصية**

💰 الرصيد: *{balance} نقطة*
📤 الدعوات: *{invites} دعوة*
🎰 الروليتات المنشأة: *{created}*
🎯 الروليتات المشتركة: *{joined}*

📈 استمر في الدعوة لكسب المزيد! 🚀"""
    
    await query.edit_message_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 رابط الدعوة", callback_data="invite_link")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]),
        parse_mode='Markdown'
    )

async def invite_link(query, context):
    user_id = query.from_user.id
    invite_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT total_invites FROM users WHERE user_id = ?', (user_id,))
    invites = cursor.fetchone()[0]
    conn.close()
    
    invite_text = f"""📤 **نظام الدعوات**

🔗 رابط دعوتك الخاص:
`{invite_link}`

🎯 **مكافآت الدعوات:**
✅ لكل صديق يدخل عبر رابطك: *+1 نقطة*
💰 صديقك يحصل على: *3 نقاط هدية*

📊 **إحصائيات دعواتك:**
📨 عدد الدعوات الناجحة: *{invites}*
💰 نقاط ربحتها: *{invites} نقطة*"""

    keyboard = [
        [InlineKeyboardButton("🔗 مشاركة الرابط", url=f"https://t.me/share/url?url={invite_link}&text=🎰%20انضم%20إلى%20MS%20روليت%20-%20أفضل%20بوت%20سحوبات%20على%20تيليجرام!%20💰%20احصل%20على%203%20نقاط%20مجانية%20عند%20الانضمام!")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(invite_text, reply_markup=reply_markup, parse_mode='Markdown')

async def settings_menu(query, context):
    user_id = query.from_user.id
    
    settings_text = """⚙️ **إعدادات MS روليت**

🌟 **الميزات الإضافية:**
• ذكرني إذا فزت
• التبرع لنستمر  
• الدعم الفني
• تعليمات الاستخدام"""

    keyboard = [
        [InlineKeyboardButton("🔔 ذكرني إذا فزت", callback_data="remind_me")],
        [InlineKeyboardButton("💎 تبرع لنستمر", callback_data="contribute")],
        [InlineKeyboardButton("🛠 الدعم الفني", callback_data="support")],
        [InlineKeyboardButton("📖 تعليمات الاستخدام", callback_data="instructions")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_instructions(query, context):
    instructions_text = """📖 **تعليمات الاستخدام**

أولاً: يجب وضع البوت مشرف في قناتك وإعطائه الصلاحيات اللازمة.

**خطوات إنشاء روليت عادي:**
1. اضغط على \"إنشاء الروليت\"
2. اكتب النص الذي تريده يظهر في رسالة السحب
3. يمكنك استخدام بلوكات جاهزة لتغيير شكل النص
4. اختر عدد الفائزين
5. اختر إضافة قنوات شرط أو تخطي
6. يتم نشر السحب في قناتك

**ملاحظات هامة:**
- لا ترسل أي روابط في نص الروليت
- تأكد من صلاحيات البوت في القناة
- يمكنك إدارة السحب من الرسالة التي تصللك"""

    await query.edit_message_text(
        instructions_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="settings")]
        ]),
        parse_mode='Markdown'
    )

async def show_support(query, context):
    support_text = """🛠 **الدعم الفني**

للدعم الفني أو الإبلاغ عن مشاكل:

👤 تواصل مع المطور
📧 أو عبر البوت الإداري

🕒 متاح 24/7 للإجابة على استفساراتك"""

    await query.edit_message_text(
        support_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="settings")]
        ]),
        parse_mode='Markdown'
    )

async def show_contribute(query, context):
    contribute_text = """💎 **تبرع لنستمر**

دعمك يساعدنا على الاستمرار في تطوير البوت وإضافة ميزات جديدة.

💰 **طرق الدعم:**
- تحويل نقدي
- نقاط البوت  
- دعم تقني

للتبرع أو الدعم، تواصل مع المطور"""

    await query.edit_message_text(
        contribute_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="settings")]
        ]),
        parse_mode='Markdown'
    )

async def toggle_reminder(query, context):
    await query.answer("✅ تم تفعيل خدمة التذكير عند الفوز!", show_alert=True)

async def add_condition_channel_prompt(query, context):
    await query.edit_message_text(
        "📥 **أرسل معرف القناة الإضافية:**\n\nمثال: `@channel_username`\n\nسيتم إضافتها كشرط إضافي للمشاركة.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="create_roulette")]
        ]),
        parse_mode='Markdown'
    )

async def boost_channel(query, context):
    await query.answer("✨ تم تعزيز قناتك في الروليت!", show_alert=True)

async def show_more_winners(query, context):
    await query.edit_message_text(
        "🎯 **اختر عدد الفائزين:**",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("11", callback_data="winners_11"),
                InlineKeyboardButton("12", callback_data="winners_12"),
                InlineKeyboardButton("13", callback_data="winners_13")
            ],
            [
                InlineKeyboardButton("14", callback_data="winners_14"),
                InlineKeyboardButton("15", callback_data="winners_15"),
                InlineKeyboardButton("16", callback_data="winners_16")
            ],
            [
                InlineKeyboardButton("17", callback_data="winners_17"),
                InlineKeyboardButton("18", callback_data="winners_18"),
                InlineKeyboardButton("19", callback_data="winners_19")
            ],
            [InlineKeyboardButton("20", callback_data="winners_20")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="create_roulette")]
        ]),
        parse_mode='Markdown'
    )

async def pause_roulette(query, context):
    roulette_id = int(query.data.split('_')[1])
    await query.answer("⏸ تم إيقاف الروليت مؤقتاً!", show_alert=True)

async def resume_roulette(query, context):
    roulette_id = int(query.data.split('_')[1])
    await query.answer("▶ تم استئناف الروليت!", show_alert=True)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"حدث خطأ: {context.error}")

def main():
    if not BOT_TOKEN:
        print("❌ خطأ: BOT_TOKEN غير موجود!")
        return
    
    print("🎉 بدء تشغيل بوت MS روليت...")
    print(f"🔹 اسم البوت: {BOT_USERNAME}")
    print(f"🔹 الأدمن: {ADMIN_ID}")
    
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # المعالجات الأساسية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_channel_message))
    application.add_error_handler(error_handler)
    
    print("✅ البوت جاهز للاستخدام!")
    print("🔹 ابدأ باستخدام: /start")
    
    application.run_polling()

if __name__ == '__main__':
    main()
💰 **طرق الد
