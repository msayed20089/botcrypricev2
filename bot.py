import logging
import sqlite3
import random
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

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
    balance = get_balance(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🎰 إنشاء روليت سريع", callback_data="create_roulette")],
        [InlineKeyboardButton("⚙️ إعدادات القناة", callback_data="channel_settings")],
        [InlineKeyboardButton(f"💰 رصيدك: {balance} نقطة", callback_data="balance")],
        [InlineKeyboardButton("🔔 ذكرني إذا فُرت", callback_data="remind_me")],
        [InlineKeyboardButton("📞 الدعم الفني", callback_data="support")],
        [InlineKeyboardButton("📖 تعليمات الاستخدام", callback_data="instructions")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"شرفنى يا {user.first_name} في روليت Panda افضل بوت عمل سحوبات في التليجرام!\n\n"
        f"الإيدي بتاعك: {user_id}\n\n"
        "اختر من القائمة التالية:",
        reply_markup=reply_markup
    )

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
    elif data == "join_roulette":
        await join_roulette(query, context)
    elif data == "stop_roulette":
        await stop_roulette(query, context)
    elif data == "main_menu":
        await main_menu(query, context)

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
    
    # خصم النقطة وإنشاء الروليت
    update_balance(user_id, -1)
    
    conn = sqlite3.connect('panda_roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO roulettes (creator_id, prize) VALUES (?, ?)', (user_id, 10))
    roulette_id = cursor.lastrowid
    
    # إضافة المنشئ كأول مشارك
    cursor.execute('INSERT INTO participants (roulette_id, user_id) VALUES (?, ?)', (roulette_id, user_id))
    cursor.execute('UPDATE roulettes SET current_participants = 1 WHERE id = ?', (roulette_id,))
    
    conn.commit()
    conn.close()
    
    # رسالة الروليت
    roulette_text = f"""🎰 روليت سريع لـ 10 أشخاص!

المشاركة سنغلق بعد اكتمال العدد

المشاركون: 1/10

روليت هام Panda"""

    keyboard = [
        [InlineKeyboardButton("🎰 انضم للروليت", callback_data=f"join_{roulette_id}")],
        [InlineKeyboardButton("⏹ إيقاف الروليت", callback_data=f"stop_{roulette_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(roulette_text, reply_markup=reply_markup)

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
        cursor.execute('SELECT status, current_participants, max_participants FROM roulettes WHERE id = ?', (roulette_id,))
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
        
        conn.commit()
        
        # إرسال رسالة للفائز
        try:
            winner_user = await context.bot.get_chat(winner_id)
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
        
        cursor.execute('SELECT creator_id FROM roulettes WHERE id = ?', (roulette_id,))
        creator_id = cursor.fetchone()[0]
        
        if user_id == creator_id:
            cursor.execute('UPDATE roulettes SET status = "stopped" WHERE id = ?', (roulette_id,))
            conn.commit()
            await query.answer("تم إيقاف الروليت بنجاح!", show_alert=True)
        else:
            await query.answer("فقط منشئ الروليت يمكنه إيقافه!", show_alert=True)
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in stop_roulette: {e}")
        await query.answer("حدث خطأ أثناء الإيقاف", show_alert=True)

async def channel_settings(query, context):
    await query.edit_message_text(
        "⚙️ إعدادات القناة:\n\n"
        "لربط القناة، أرسل معرف القناة في الصيغة التالية:\n"
        "@اسم_القناة\n\n"
        "أو أرسل رابط القناة مباشرة.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ])
    )

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
        "1. إنشاء روليت: اختر 'إنشاء روليت سريع'\n"
        "2. المشاركة: انضم للروليت عبر الزر المخصص\n"
        "3. الإدارة: يمكنك إيقاف الروليت في أي وقت\n"
        "4. النقاط: تربح نقاط عند المشاركة والفوز\n\n"
        "للدعم الفني: @Roulette_Panda_Support",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ])
    )

async def main_menu(query, context):
    user_id = query.from_user.id
    balance = get_balance(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🎰 إنشاء روليت سريع", callback_data="create_roulette")],
        [InlineKeyboardButton("⚙️ إعدادات القناة", callback_data="channel_settings")],
        [InlineKeyboardButton(f"💰 رصيدك: {balance} نقطة", callback_data="balance")],
        [InlineKeyboardButton("🔔 ذكرني إذا فُرت", callback_data="remind_me")],
        [InlineKeyboardButton("📞 الدعم الفني", callback_data="support")],
        [InlineKeyboardButton("📖 تعليمات الاستخدام", callback_data="instructions")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"شرفنى يا {query.from_user.first_name} في روليت Panda افضل بوت عمل سحوبات في التليجرام!\n\n"
        f"الإيدي بتاعك: {user_id}\n\n"
        "اختر من القائمة التالية:",
        reply_markup=reply_markup
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
    
    conn.close()
    
    await update.message.reply_text(
        f"📊 إحصائيات البوت:\n\n"
        f"👥 إجمالي المستخدمين: {total_users}\n"
        f"🎰 إجمالي الروليتات: {total_roulettes}\n"
        f"🏆 الروليتات المكتملة: {completed_roulettes}"
    )

def main():
    # التحقق من التوكن
    if not BOT_TOKEN:
        print("❌ خطأ: BOT_TOKEN غير موجود!")
        return
    
    print("🎉 بدء تشغيل بوت روليت Panda...")
    
    # تهيئة قاعدة البيانات
    init_db()
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    print("✅ البوت جاهز للاستخدام!")
    
    # تشغيل البوت
    application.run_polling()

if __name__ == '__main__':
    main()
