import logging
import sqlite3
import random
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# إعدادات البوت
BOT_TOKEN = os.getenv("BOT_TOKEN", "8399150202:AAEvr37r05xzbjhwinnGZQIWAuoylpsNflg").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "6096879850"))

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
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roulettes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER,
            channel_id TEXT,
            message_id INTEGER,
            max_participants INTEGER DEFAULT 10,
            current_participants INTEGER DEFAULT 0,
            status TEXT DEFAULT 'waiting',
            winner_id INTEGER DEFAULT NULL,
            prize INTEGER DEFAULT 0,
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
            cost INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # إضافة القنوات الإجبارية الافتراضية
    cursor.execute('INSERT OR IGNORE INTO forced_channels (channel_username, channel_id, cost) VALUES (?, ?, ?)', 
                  ("zforexms", "@zforexms", 5))
    
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
    cursor.execute('SELECT channel_username, channel_id, cost FROM forced_channels WHERE is_active = TRUE')
    channels = cursor.fetchall()
    conn.close()
    return channels

def add_forced_channel(channel_username, channel_id, cost=0):
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO forced_channels (channel_username, channel_id, cost) VALUES (?, ?, ?)', 
                  (channel_username, channel_id, cost))
    conn.commit()
    conn.close()

async def check_channel_subscription(user_id, channel_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

async def check_bot_admin(channel_id, context):
    try:
        bot_member = await context.bot.get_chat_member(chat_id=channel_id, user_id=context.bot.id)
        return bot_member.status in ['administrator', 'creator']
    except:
        return False

# الأوامر الرئيسية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # معالجة رابط الدعوة
    args = context.args
    invited_by = 0
    if args and args[0].startswith('ref_'):
        try:
            invited_by = int(args[0].split('_')[1])
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
        message_text = f"""🎰 *مرحباً بك في روليت MS* 

⚡ أفضل بوت سحوبات على التليجرام

🆔 الإيدي: {user_id}
💰 رصيدك: {balance} نقطة

📊 أنشئ روليت مجاني أو مدفوع في قناتك!"""

    keyboard = [
        [InlineKeyboardButton("🎰 إنشاء روليت مجاني", callback_data="create_free_roulette")],
        [InlineKeyboardButton("💎 إنشاء روليت مدفوع", callback_data="create_paid_roulette")],
        [InlineKeyboardButton(f"📢 قناتك ({channel_status})", callback_data="channel_settings")],
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
    
    if data == "create_free_roulette":
        await create_free_roulette(query, context)
    elif data == "create_paid_roulette":
        await create_paid_roulette(query, context)
    elif data == "channel_settings":
        await channel_settings(query, context)
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
    elif data.startswith("stop_"):
        await stop_roulette(query, context)
    elif data.startswith("view_"):
        await view_participants(query, context)
    elif data == "main_menu":
        await show_main_menu(update, user_id)
    elif data == "add_channel":
        await add_channel_prompt(query, context)
    elif data == "select_forced_channel":
        await select_forced_channel(query, context)

async def create_free_roulette(query, context):
    user_id = query.from_user.id
    user_channel = get_user_channel(user_id)
    
    if not user_channel:
        await query.edit_message_text(
            "❌ يجب عليك ضبط قناة أولاً!\n\n📢 أضف قناتك واضف البوت كأدمن فيها.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 ضبط القناة", callback_data="channel_settings")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )
        return
    
    # التحقق من أن البوت أدمن في القناة
    is_bot_admin = await check_bot_admin(user_channel[1], context)
    if not is_bot_admin:
        await query.edit_message_text(
            f"❌ البوت ليس أدمن في القناة!\n\n📢 قناتك: @{user_channel[0]}\n\n⚠️ أضف البوت كأدمن في القناة أولاً.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 تحقق مرة أخرى", callback_data="create_free_roulette")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )
        return
    
    # إنشاء الروليت المجاني
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO roulettes (creator_id, channel_id, status) VALUES (?, ?, "waiting")', (user_id, user_channel[1]))
    roulette_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # إرسال الروليت إلى القناة
    try:
        roulette_text = f"""🎰 *روليت سريع - مجاني*

👤 المنشئ: {query.from_user.first_name}
🔢 العدد المستهدف: 10 أشخاص

📊 المشاركون: 0/10
⏳ في انتظار بدء الروليت...

⚡ روليت MS"""

        keyboard = [
            [InlineKeyboardButton("🎯 انضم للروليت", callback_data=f"join_{roulette_id}")],
            [InlineKeyboardButton("👀 مشاهدة المشاركين", callback_data=f"view_{roulette_id}")],
            [InlineKeyboardButton("🚀 بدء الروليت", callback_data=f"start_{roulette_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = await context.bot.send_message(
            chat_id=user_channel[1],
            text=roulette_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE roulettes SET message_id = ? WHERE id = ?', (message.message_id, roulette_id))
        conn.commit()
        conn.close()
        
        await query.edit_message_text(
            f"✅ *تم إنشاء الروليت المجاني بنجاح!*\n\n"
            f"📢 القناة: @{user_channel[0]}\n"
            f"🎯 يمكنك الآن بدء الروليت عندما يكتمل العدد\n\n"
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

async def create_paid_roulette(query, context):
    user_id = query.from_user.id
    balance = get_balance(user_id)
    
    forced_channels = get_forced_channels()
    if not forced_channels:
        await query.edit_message_text(
            "❌ لا توجد قنوات مدفوعة متاحة حالياً!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )
        return
    
    keyboard = []
    for channel in forced_channels:
        channel_username, channel_id, cost = channel
        if balance >= cost:
            keyboard.append([InlineKeyboardButton(f"📢 @{channel_username} - {cost} نقطة", callback_data=f"paid_{channel_id}")])
        else:
            keyboard.append([InlineKeyboardButton(f"❌ @{channel_username} - {cost} نقطة (رصيد غير كافي)", callback_data="insufficient_balance")])
    
    keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")])
    
    await query.edit_message_text(
        f"💎 *إنشاء روليت مدفوع*\n\n💰 رصيدك الحالي: {balance} نقطة\n\nاختر القناة المطلوبة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def select_forced_channel(query, context):
    user_id = query.from_user.id
    forced_channels = get_forced_channels()
    
    keyboard = []
    for channel in forced_channels:
        channel_username, channel_id, cost = channel
        keyboard.append([InlineKeyboardButton(f"📢 @{channel_username}", callback_data=f"forced_{channel_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="channel_settings")])
    
    await query.edit_message_text(
        "📢 *اختر قناة الاشتراك الإجباري:*\n\nسيتم إضافة هذه القناة كاشتراك إجباري للروليت.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
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
            await query.answer("أنت مشترك بالفعل في هذا الروليت! ✅", show_alert=True)
            conn.close()
            return
        
        # التحقق من حالة الروليت
        cursor.execute('SELECT status, current_participants, max_participants, channel_id, message_id FROM roulettes WHERE id = ?', (roulette_id,))
        roulette = cursor.fetchone()
        
        if not roulette or roulette[0] != 'waiting':
            await query.answer("الروليت غير متاح للانضمام! ❌", show_alert=True)
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
            cursor.execute('SELECT creator_id FROM roulettes WHERE id = ?', (roulette_id,))
            creator_id = cursor.fetchone()[0]
            creator = await context.bot.get_chat(creator_id)
            
            roulette_text = f"""🎰 *روليت سريع - مجاني*

👤 المنشئ: {creator.first_name}
🔢 العدد المستهدف: 10 أشخاص

📊 المشاركون: {current}/10
⏳ في انتظار بدء الروليت...

⚡ روليت MS"""

            keyboard = [
                [InlineKeyboardButton("🎯 انضم للروليت", callback_data=f"join_{roulette_id}")],
                [InlineKeyboardButton("👀 مشاهدة المشاركين", callback_data=f"view_{roulette_id}")],
                [InlineKeyboardButton("🚀 بدء الروليت", callback_data=f"start_{roulette_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.edit_message_text(
                chat_id=roulette[3],
                message_id=roulette[4],
                text=roulette_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error updating channel message: {e}")
        
        conn.close()
        
        await query.answer(f"تم انضمامك للروليت! 🎯 ({current}/10)", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in join_roulette: {e}")
        await query.answer("حدث خطأ أثناء الانضمام ⚠️", show_alert=True)

async def start_roulette(query, context):
    try:
        roulette_id = int(query.data.split('_')[1])
        user_id = query.from_user.id
        
        conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT creator_id, current_participants, channel_id, message_id FROM roulettes WHERE id = ?', (roulette_id,))
        roulette = cursor.fetchone()
        
        if not roulette or user_id != roulette[0]:
            await query.answer("فقط منشئ الروليت يمكنه بدء الروليت! ❌", show_alert=True)
            conn.close()
            return
        
        if roulette[1] < 2:
            await query.answer("يجب أن يكون هناك مشاركين على الأقل! 👥", show_alert=True)
            conn.close()
            return
        
        # بدء الروليت واختيار الفائز
        cursor.execute('SELECT user_id, user_name FROM participants WHERE roulette_id = ?', (roulette_id,))
        participants = cursor.fetchall()
        
        winner_id, winner_name = random.choice(participants)
        
        cursor.execute('UPDATE roulettes SET status = "completed", winner_id = ? WHERE id = ?', (winner_id, roulette_id))
        update_balance(winner_id, 10)  # مكافأة الفائز
        
        conn.commit()
        
        # تحديث الرسالة في القناة
        try:
            winner_text = f"🎉 *الفائز: {winner_name}*"
            
            participants_text = "👥 *المشاركون:*\n"
            for i, (pid, pname) in enumerate(participants, 1):
                participants_text += f"{i}. {pname}\n"
            
            roulette_text = f"""🎰 *روليت سريع - مكتمل*

{winner_text}

{participants_text}

🎁 الجائزة: 10 نقاط
✅ الروليت مكتمل

⚡ روليت MS"""

            await context.bot.edit_message_text(
                chat_id=roulette[2],
                message_id=roulette[3],
                text=roulette_text,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error updating winner message: {e}")
        
        # إرسال رسالة للفائز
        try:
            await context.bot.send_message(
                winner_id,
                f"🎉 *مبروك! فزت في الروليت* #{roulette_id}\n\n💰 ربحت 10 نقاط!\n\nرصيدك الجديد: {get_balance(winner_id)} نقطة 🎁",
                parse_mode='Markdown'
            )
        except:
            pass
        
        conn.close()
        
        await query.answer("تم بدء الروليت واختيار الفائز! 🎉", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in start_roulette: {e}")
        await query.answer("حدث خطأ أثناء بدء الروليت ⚠️", show_alert=True)

async def view_participants(query, context):
    try:
        roulette_id = int(query.data.split('_')[1])
        
        conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_name FROM participants WHERE roulette_id = ?', (roulette_id,))
        participants = cursor.fetchall()
        
        conn.close()
        
        if participants:
            participants_text = "👥 *المشاركون في الروليت:*\n\n"
            for i, (name,) in enumerate(participants, 1):
                participants_text += f"{i}. {name}\n"
            
            await query.answer(participants_text, show_alert=True)
        else:
            await query.answer("لا يوجد مشاركين بعد! ❌", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in view_participants: {e}")
        await query.answer("حدث خطأ ⚠️", show_alert=True)

async def channel_settings(query, context):
    user_id = query.from_user.id
    user_channel = get_user_channel(user_id)
    
    if user_channel:
        text = f"📢 *إعدادات القناة*\n\nالقناة الحالية: @{user_channel[0]}\n\nيمكنك تغيير القناة أو إضافة قناة جديدة:"
    else:
        text = "📢 *إعدادات القناة*\n\nلم تقم بإضافة قناة بعد.\n\nلإنشاء روليت، تحتاج إلى إضافة قناة واضافة البوت كأدمن فيها."
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة قناة", callback_data="add_channel")],
        [InlineKeyboardButton("📢 قنوات الاشتراك الإجباري", callback_data="select_forced_channel")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        text + "\n\n⚠️ *تأكد من إضافة البوت كأدمن في القناة*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def add_channel_prompt(query, context):
    await query.edit_message_text(
        "📥 *أرسل معرف القناة:*\n\nمثال: @channel_username\n\nثم اضف البوت كأدمن في القناة مع صلاحية إرسال رسائل.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="channel_settings")]
        ]),
        parse_mode='Markdown'
    )

async def handle_channel_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
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
                f"✅ *تم إضافة القناة بنجاح!*\n\n📢 القناة: @{channel_username}\n\nيمكنك الآن إنشاء روليتات في قناتك. 🎰",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎰 إنشاء روليت مجاني", callback_data="create_free_roulette")],
                    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
                ]),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error testing channel: {e}")
            await update.message.reply_text(
                f"❌ *فشل إضافة القناة!*\n\nتأكد من:\n• إضافة البوت كأدمن في القناة\n• صلاحية إرسال رسائل\n• أن المعرف صحيح\n\nالقناة: {channel_id}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 حاول مرة أخرى", callback_data="add_channel")],
                    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
                ]),
                parse_mode='Markdown'
            )
    else:
        await update.message.reply_text(
            "❌ *صيغة غير صحيحة!*\n\nأرسل معرف القناة مثل:\n@channel_username",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 حاول مرة أخرى", callback_data="add_channel")],
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
    
    stats_text = f"""📊 *إحصائياتك الشخصية*

💰 الرصيد: {balance} نقطة
📤 الدعوات: {invites} دعوة
🎰 الروليتات المنشأة: {created}
🎯 الروليتات المشتركة: {joined}

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
    invite_link = f"https://t.me/lllllllofdkokbot?start=ref_{user_id}"
    
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT total_invites FROM users WHERE user_id = ?', (user_id,))
    invites = cursor.fetchone()[0]
    conn.close()
    
    invite_text = f"""📤 *نظام الدعوات*

🔗 رابط دعوتك الخاص:
`{invite_link}`

🎯 *مكافآت الدعوات:*
✅ لكل صديق يدخل عبر رابطك: +1 نقطة
💰 صديقك يحصل على: 3 نقاط هدية

📊 *إحصائيات دعواتك:*
📨 عدد الدعوات الناجحة: {invites}
💰 نقاط ربحتها: {invites} نقطة"""

    keyboard = [
        [InlineKeyboardButton("🔗 مشاركة الرابط", url=f"https://t.me/share/url?url={invite_link}&text=انضم%20إلى%20روليت%20MS%20-%20أفضل%20بوت%20سحوبات%20على%20تيليجرام!%20🎰")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(invite_text, reply_markup=reply_markup, parse_mode='Markdown')

async def settings_menu(query, context):
    settings_text = """⚙️ *إعدادات البوت*

🔔 *الإشعارات:*
✅ تفعيل الإشعارات

🌐 *اللغة:*
🇸🇦 العربية

🎰 *إعدادات الروليت:*
🔢 عدد المشاركين: 10
⏰ مدة الروليت: غير محددة"""

    keyboard = [
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')

# الأوامر الإدارية
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 إدارة القنوات الإجبارية", callback_data="admin_channels")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")],
        [InlineKeyboardButton("💰 إضافة نقاط", callback_data="admin_add_points")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛠 *لوحة تحكم الأدمن*\n\nاختر الإدارة المناسبة:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('ms_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM roulettes')
    total_roulettes = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM roulettes WHERE status = "completed"')
    completed_roulettes = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM user_channels')
    total_channels = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM forced_channels')
    total_forced = cursor.fetchone()[0]
    
    conn.close()
    
    await update.message.reply_text(
        f"📊 *إحصائيات البوت:*\n\n"
        f"👥 المستخدمين: {total_users}\n"
        f"🎰 الروليتات: {total_roulettes}\n"
        f"🏆 المكتملة: {completed_roulettes}\n"
        f"📢 القنوات: {total_channels}\n"
        f"🔒 القنوات الإجبارية: {total_forced}",
        parse_mode='Markdown'
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"حدث خطأ: {context.error}")

def main():
    if not BOT_TOKEN:
        print("❌ خطأ: BOT_TOKEN غير موجود!")
        return
    
    print("🎉 بدء تشغيل بوت روليت MS...")
    
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_channel_message))
    application.add_error_handler(error_handler)
    
    print("✅ البوت جاهز للاستخدام!")
    print("🔹 للأعضاء: /start")
    print("🔹 للأدمن: /admin")
    
    application.run_polling()

if __name__ == '__main__':
    main()
