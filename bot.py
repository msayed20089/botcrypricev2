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
    conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 5,
            invited_by INTEGER DEFAULT 0,
            total_invites INTEGER DEFAULT 0,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # الروليتات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roulettes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER,
            channel_id TEXT,
            message_id INTEGER,
            title TEXT DEFAULT 'روليت سريع',
            max_participants INTEGER DEFAULT 10,
            current_participants INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            winner_id INTEGER DEFAULT NULL,
            prize INTEGER DEFAULT 0,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # المشاركين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roulette_id INTEGER,
            user_id INTEGER,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # الدعوات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER,
            invited_id INTEGER,
            invited_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # قنوات المستخدمين
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
    
    conn.commit()
    conn.close()

# دوال المساعدة
def get_user(user_id):
    conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name, invited_by=0):
    conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, invited_by, balance) 
        VALUES (?, ?, ?, ?, 5)
    ''', (user_id, username, first_name, invited_by))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 5

def get_user_channel(user_id):
    conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT channel_username, channel_id FROM user_channels WHERE user_id = ? AND is_approved = TRUE', (user_id,))
    channel = cursor.fetchone()
    conn.close()
    return channel

def add_user_channel(user_id, channel_username, channel_id):
    conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO user_channels (user_id, channel_username, channel_id, is_approved) 
        VALUES (?, ?, ?, TRUE)
    ''', (user_id, channel_username, channel_id))
    conn.commit()
    conn.close()

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
            # مكافأة الداعي
            update_balance(invited_by, 1)
            
            conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET total_invites = total_invites + 1 WHERE user_id = ?', (invited_by,))
            cursor.execute('INSERT INTO invitations (inviter_id, invited_id) VALUES (?, ?)', (invited_by, user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error in referral: {e}")

    # إنشاء/تحديث المستخدم
    if not get_user(user_id):
        create_user(user_id, user.username, user.first_name, invited_by)

    # القائمة الرئيسية
    await show_main_menu(update, user_id)

async def show_main_menu(update, user_id, message_text=None):
    balance = get_balance(user_id)
    user_channel = get_user_channel(user_id)
    
    channel_status = "❌ غير مضبوطة"
    if user_channel:
        channel_status = f"✅ @{user_channel[0]}"
    
    if message_text is None:
        message_text = f"شرفنى يا {update.effective_user.first_name} في روليت Panda افضل بوت عمل سحوبات في التليجرام!\n\nالإيدي بتاعك: {user_id}\n\nاختر من القائمة التالية:"
    
    keyboard = [
        [InlineKeyboardButton("🎰 إنشاء روليت سريع", callback_data="create_roulette")],
        [InlineKeyboardButton(f"⚙️ إعدادات القناة ({channel_status})", callback_data="channel_settings")],
        [InlineKeyboardButton(f"💰 رصيدك: {balance} نقطة", callback_data="balance")],
        [InlineKeyboardButton("🔔 ذكرني إذا فُرت", callback_data="remind_me")],
        [InlineKeyboardButton("📞 الدعم الفني", callback_data="support")],
        [InlineKeyboardButton("📖 تعليمات الاستخدام", callback_data="instructions")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "create_roulette":
        await create_roulette(query, context)
    elif data == "channel_settings":
        await channel_settings(query, context)
    elif data == "balance":
        await show_balance(query, context)
    elif data == "remind_me":
        await remind_me(query, context)
    elif data == "support":
        await support(query, context)
    elif data == "instructions":
        await instructions(query, context)
    elif data.startswith("join_"):
        await join_roulette(query, context)
    elif data.startswith("stop_"):
        await stop_roulette(query, context)
    elif data == "main_menu":
        await show_main_menu(update, user_id)
    elif data == "add_channel":
        await add_channel(query, context)

async def create_roulette(query, context):
    user_id = query.from_user.id
    balance = get_balance(user_id)
    
    if balance < 1:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي!\n\n💰 رصيدك الحالي: {balance} نقطة\n💡 تحتاج إلى نقطة واحدة لإنشاء روليت\n\n📤 ادعِ أصدقائك لزيادة رصيدك!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )
        return
    
    # التحقق من وجود قناة مضبوطة
    user_channel = get_user_channel(user_id)
    if not user_channel:
        await query.edit_message_text(
            "❌ يجب عليك ضبط قناة أولاً!\n\n"
            "لإنشاء روليت، تحتاج إلى إضافة قناة واضافة البوت كأدمن فيها.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ ضبط القناة", callback_data="channel_settings")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )
        return
    
    # خصم النقطة وإنشاء الروليت
    update_balance(user_id, -1)
    
    conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO roulettes (creator_id, channel_id, prize) VALUES (?, ?, ?)', (user_id, user_channel[1], 10))
    roulette_id = cursor.lastrowid
    
    # إضافة المنشئ كأول مشارك
    cursor.execute('INSERT INTO participants (roulette_id, user_id) VALUES (?, ?)', (roulette_id, user_id))
    cursor.execute('UPDATE roulettes SET current_participants = 1 WHERE id = ?', (roulette_id,))
    
    conn.commit()
    conn.close()
    
    # إرسال الروليت إلى القناة
    try:
        roulette_text = f"""🎰 روليت سريع لـ 10 أشخاص!

المشاركة سنغلق بعد اكتمال العدد

المشاركون: 1/10

روليت هام Panda"""

        keyboard = [
            [InlineKeyboardButton("🎰 انضم للروليت", callback_data=f"join_{roulette_id}")],
            [InlineKeyboardButton("⏹ إيقاف الروليت", callback_data=f"stop_{roulette_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إرسال الرسالة إلى القناة
        message = await context.bot.send_message(
            chat_id=user_channel[1],
            text=roulette_text,
            reply_markup=reply_markup
        )
        
        # حفظ معرف الرسالة في قاعدة البيانات
        conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE roulettes SET message_id = ? WHERE id = ?', (message.message_id, roulette_id))
        conn.commit()
        conn.close()
        
        await query.edit_message_text(
            f"✅ تم إنشاء الروليت بنجاح!\n\n"
            f"🎯 تم نشر الروليت في قناتك: @{user_channel[0]}\n"
            f"💰 تم خصم 1 نقطة\n"
            f"💎 رصيدك الجديد: {balance - 1} نقطة\n\n"
            f"📤 شارك الروليت مع أصدقائك!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Error sending to channel: {e}")
        # إرجاع النقطة في حالة الخطأ
        update_balance(user_id, 1)
        await query.edit_message_text(
            f"❌ فشل إنشاء الروليت!\n\n"
            f"⚠️ تأكد من:\n"
            f"• إضافة البوت كأدمن في القناة\n"
            f"• أن البوت لديه صلاحية إرسال رسائل\n"
            f"• أن القناة صحيحة\n\n"
            f"💰 تم إرجاع النقطة إلى رصيدك",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ ضبط القناة", callback_data="channel_settings")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )

async def join_roulette(query, context):
    try:
        roulette_id = int(query.data.split('_')[1])
        user_id = query.from_user.id
        
        conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # التحقق إذا كان المستخدم منضم بالفعل
        cursor.execute('SELECT * FROM participants WHERE roulette_id = ? AND user_id = ?', (roulette_id, user_id))
        if cursor.fetchone():
            await query.answer("أنت مشترك بالفعل في هذا الروليت!", show_alert=True)
            conn.close()
            return
        
        # التحقق من حالة الروليت
        cursor.execute('SELECT status, current_participants, max_participants, channel_id, message_id FROM roulettes WHERE id = ?', (roulette_id,))
        roulette = cursor.fetchone()
        
        if not roulette or roulette[0] != 'active':
            await query.answer("هذا الروليت غير متاح!", show_alert=True)
            conn.close()
            return
            
        if roulette[1] >= roulette[2]:
            await query.answer("الروليت مكتمل!", show_alert=True)
            conn.close()
            return
        
        # إضافة المشارك
        cursor.execute('INSERT INTO participants (roulette_id, user_id) VALUES (?, ?)', (roulette_id, user_id))
        cursor.execute('UPDATE roulettes SET current_participants = current_participants + 1 WHERE id = ?', (roulette_id,))
        
        # الحصول على العدد الجديد
        cursor.execute('SELECT current_participants FROM roulettes WHERE id = ?', (roulette_id,))
        current = cursor.fetchone()[0]
        
        conn.commit()
        
        # تحديث الرسالة في القناة
        try:
            roulette_text = f"""🎰 روليت سريع لـ 10 أشخاص!

المشاركة سنغلق بعد اكتمال العدد

المشاركون: {current}/10

روليت هام Panda"""

            keyboard = [
                [InlineKeyboardButton("🎰 انضم للروليت", callback_data=f"join_{roulette_id}")],
                [InlineKeyboardButton("⏹ إيقاف الروليت", callback_data=f"stop_{roulette_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.edit_message_text(
                chat_id=roulette[3],
                message_id=roulette[4],
                text=roulette_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error updating channel message: {e}")
        
        conn.close()
        
        await query.answer(f"تم انضمامك للروليت! ({current}/10)", show_alert=True)
        
        # إذا اكتمل العدد، اختيار الفائز
        if current >= 10:
            await select_winner(roulette_id, context)
            
    except Exception as e:
        logger.error(f"Error in join_roulette: {e}")
        await query.answer("حدث خطأ أثناء الانضمام", show_alert=True)

async def select_winner(roulette_id, context):
    conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # الحصول على جميع المشاركين
    cursor.execute('SELECT user_id FROM participants WHERE roulette_id = ?', (roulette_id,))
    participants = cursor.fetchall()
    
    if participants:
        # اختيار فائز عشوائي
        winner_id = random.choice(participants)[0]
        
        # تحديث الروليت
        cursor.execute('UPDATE roulettes SET winner_id = ?, status = "completed" WHERE id = ?', (winner_id, roulette_id))
        
        # مكافأة الفائز
        update_balance(winner_id, 10)
        
        # الحصول على معلومات الروليت
        cursor.execute('SELECT channel_id, message_id FROM roulettes WHERE id = ?', (roulette_id,))
        roulette_info = cursor.fetchone()
        
        conn.commit()
        
        # تحديث الرسالة في القناة
        try:
            winner_user = await context.bot.get_chat(winner_id)
            winner_text = f"🎉 تم اختيار الفائز: {winner_user.first_name} (@{winner_user.username or 'بدون معرف'})"
            
            roulette_text = f"""🎰 روليت سريع لـ 10 أشخاص!

{winner_text}

المشاركون: 10/10 ✅

روليت هام Panda - مكتمل"""

            await context.bot.edit_message_text(
                chat_id=roulette_info[0],
                message_id=roulette_info[1],
                text=roulette_text
            )
        except Exception as e:
            logger.error(f"Error updating winner message: {e}")
        
        # إرسال رسالة للفائز
        try:
            await context.bot.send_message(
                winner_id,
                f"🎉 مبروك! فزت في الروليت #{roulette_id}\n\n💰 ربحت 10 نقاط!\n\nرصيدك الجديد: {get_balance(winner_id)} نقطة"
            )
        except:
            pass
            
    conn.close()

async def stop_roulette(query, context):
    try:
        roulette_id = int(query.data.split('_')[1])
        user_id = query.from_user.id
        
        conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT creator_id, channel_id, message_id FROM roulettes WHERE id = ?', (roulette_id,))
        roulette = cursor.fetchone()
        
        if user_id == roulette[0]:
            cursor.execute('UPDATE roulettes SET status = "stopped" WHERE id = ?', (roulette_id,))
            conn.commit()
            
            # تحديث الرسالة في القناة
            try:
                roulette_text = f"""🎰 روليت سريع لـ 10 أشخاص!

⏹ تم إيقاف الروليت من قبل المنشئ

روليت هام Panda - متوقف"""

                await context.bot.edit_message_text(
                    chat_id=roulette[1],
                    message_id=roulette[2],
                    text=roulette_text
                )
            except Exception as e:
                logger.error(f"Error updating stopped message: {e}")
            
            await query.answer("تم إيقاف الروليت بنجاح!", show_alert=True)
        else:
            await query.answer("فقط منشئ الروليت يمكنه إيقافه!", show_alert=True)
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in stop_roulette: {e}")
        await query.answer("حدث خطأ أثناء الإيقاف", show_alert=True)

async def channel_settings(query, context):
    user_id = query.from_user.id
    user_channel = get_user_channel(user_id)
    
    if user_channel:
        text = f"⚙️ إعدادات القناة:\n\nالقناة الحالية: @{user_channel[0]}\n\nيمكنك تغيير القناة بإرسال معرف قناة جديد:"
    else:
        text = "⚙️ إعدادات القناة:\n\nلم تقم بإضافة قناة بعد.\n\nلإضافة قناة، أرسل معرف القناة (مثل: @channel_username) أو رابط القناة."
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة قناة", callback_data="add_channel")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        text + "\n\n⚠️ تأكد من:\n• إضافة البوت كأدمن في القناة\n• منح البوت صلاحية إرسال رسائل",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def add_channel(query, context):
    await query.edit_message_text(
        "📥 أرسل معرف القناة أو الرابط:\n\n"
        "مثال:\n"
        "@channel_username\n"
        "أو\n"
        "https://t.me/channel_username\n\n"
        "ثم اضف البوت كأدمن في القناة مع صلاحية إرسال رسائل.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="channel_settings")]
        ])
    )

# معالجة الرسائل النصية لإضافة القنوات
async def handle_channel_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # استخراج معرف القناة من النص
    channel_username = None
    channel_id = None
    
    if text.startswith('@'):
        channel_username = text[1:]
        channel_id = f"@{channel_username}"
    elif 't.me/' in text:
        # استخراج من الرابط
        parts = text.split('t.me/')
        if len(parts) > 1:
            channel_username = parts[1].split('/')[0].replace('@', '')
            channel_id = f"@{channel_username}"
    
    if channel_username:
        # اختبار إرسال رسالة إلى القناة
        try:
            test_message = await context.bot.send_message(
                chat_id=channel_id,
                text="🔧 اختبار اتصال البوت بالقناة...\n\n✅ البوت يعمل بشكل صحيح!"
            )
            
            # حذف رسالة الاختبار
            await context.bot.delete_message(chat_id=channel_id, message_id=test_message.message_id)
            
            # حفظ القناة
            add_user_channel(user_id, channel_username, channel_id)
            
            await update.message.reply_text(
                f"✅ تم إضافة القناة بنجاح!\n\n"
                f"📢 القناة: @{channel_username}\n\n"
                f"يمكنك الآن إنشاء روليتات في قناتك.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎰 إنشاء روليت", callback_data="create_roulette")],
                    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error testing channel: {e}")
            await update.message.reply_text(
                f"❌ فشل إضافة القناة!\n\n"
                f"⚠️ تأكد من:\n"
                f"• إضافة البوت كأدمن في القناة\n"
                f"• منح البوت صلاحية إرسال رسائل\n"
                f"• أن المعرف صحيح\n\n"
                f"القناة: {channel_id}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 حاول مرة أخرى", callback_data="add_channel")],
                    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
                ])
            )
    else:
        await update.message.reply_text(
            "❌ صيغة غير صحيحة!\n\n"
            "أرسل معرف القناة مثل:\n"
            "@channel_username\n"
            "أو رابط القناة مثل:\n"
            "https://t.me/channel_username",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 حاول مرة أخرى", callback_data="add_channel")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )

# باقي الدوال تبقى كما هي (show_balance, remind_me, support, instructions, main_menu)
async def show_balance(query, context):
    user_id = query.from_user.id
    balance = get_balance(user_id)
    
    await query.edit_message_text(
        f"💰 رصيدك الحالي: {balance} نقطة",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ])
    )

async def remind_me(query, context):
    await query.edit_message_text(
        "🔔 سيتم إشعارك عندما يتوفر روليت جديد!\n\n"
        "تم تفعيل نظام التذكير لك.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ])
    )

async def support(query, context):
    await query.edit_message_text(
        "📞 الدعم الفني:\n\n"
        "للتواصل مع الدعم الفني:\n"
        "@Roulette_Panda_Support\n\n"
        "أو راسلنا على:\n"
        "support@roulettepanda.com",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ])
    )

async def instructions(query, context):
    await query.edit_message_text(
        "📖 تعليمات الاستخدام:\n\n"
        "1. إضافة قناة: اختر 'إعدادات القناة' وأضف قناتك\n"
        "2. إضافة البوت كأدمن في القناة مع صلاحية إرسال رسائل\n"
        "3. إنشاء روليت: اختر 'إنشاء روليت سريع'\n"
        "4. المشاركة: انضم للروليت عبر الزر المخصص\n"
        "5. الإدارة: يمكنك إيقاف الروليت في أي وقت\n\n"
        "للدعم الفني: @Roulette_Panda_Support",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ])
    )

# الأوامر الإدارية
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM roulettes')
    total_roulettes = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM roulettes WHERE status = "completed"')
    completed_roulettes = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM user_channels')
    total_channels = cursor.fetchone()[0]
    
    conn.close()
    
    await update.message.reply_text(
        f"📊 إحصائيات البوت:\n\n"
        f"👥 إجمالي المستخدمين: {total_users}\n"
        f"🎰 إجمالي الروليتات: {total_roulettes}\n"
        f"🏆 الروليتات المكتملة: {completed_roulettes}\n"
        f"📢 القنوات المضبوطة: {total_channels}"
    )

def main():
    # التحقق من التوكن
    if not BOT_TOKEN:
        print("❌ خطأ: BOT_TOKEN غير موجود!")
        return
    
    print("🎉 بدء تشغيل بوت روليت Panda مع نظام القنوات...")
    
    # تهيئة قاعدة البيانات
    init_db()
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_channel_message))
    
    print("✅ البوت جاهز للاستخدام!")
    print("🔹 للأعضاء: /start")
    print(f"🔹 للأدمن: /stats")
    
    # تشغيل البوت
    application.run_polling()

if __name__ == '__main__':
    main()
