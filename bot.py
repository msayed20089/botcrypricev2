import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

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
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance INTEGER DEFAULT 5,
            invited_by INTEGER DEFAULT 0,
            invitation_count INTEGER DEFAULT 0,
            total_invitations INTEGER DEFAULT 0,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roulettes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creator_id INTEGER,
            title TEXT,
            participants_count INTEGER DEFAULT 0,
            max_participants INTEGER DEFAULT 10,
            status TEXT DEFAULT 'active',
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roulette_id INTEGER,
            user_id INTEGER,
            joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER,
            invited_id INTEGER,
            invited_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # إضافة مستخدمين نموذجيين للاختبار
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)', 
                  (ADMIN_ID, 'admin', 'Admin'))
    
    conn.commit()
    conn.close()

# ========== دوال المساعدة ==========
def get_user_balance(user_id):
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 5

def update_user_balance(user_id, new_balance):
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
    conn.commit()
    conn.close()

def generate_invite_link(user_id):
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

# ========== البوت الرئيسي ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # معالجة رابط الدعوة
    args = context.args
    invited_by = 0
    if args and args[0].startswith('ref_'):
        try:
            invited_by = int(args[0].split('_')[1])
            # زيادة رصيد الداعي
            inviter_balance = get_user_balance(invited_by)
            update_user_balance(invited_by, inviter_balance + 1)
            
            # تحديث إحصائيات الدعوات
            conn = sqlite3.connect('roulette.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET invitation_count = invitation_count + 1, total_invitations = total_invitations + 1 WHERE user_id = ?', (invited_by,))
            cursor.execute('INSERT OR IGNORE INTO invitations (inviter_id, invited_id) VALUES (?, ?)', (invited_by, user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"خطأ في رابط الدعوة: {e}")

    # إضافة/تحديث المستخدم
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, invited_by) 
        VALUES (?, ?, ?, ?)
    ''', (user_id, user.username, user.first_name, invited_by))
    conn.commit()
    conn.close()
    
    # عرض القائمة الرئيسية
    await show_main_menu(update, user_id, "🎉 أهلاً بك في روليت MS! 🎰\n\nاختر من القائمة:")

async def show_main_menu(update, user_id, message_text=""):
    balance = get_user_balance(user_id)
    
    keyboard = [
        [InlineKeyboardButton(f"🎰 إنشاء روليت سريع (-1 نقطة)", callback_data="create_roulette")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
        [InlineKeyboardButton("📤 رابط الدعوة", callback_data="invite_link")],
        [
            InlineKeyboardButton(f"💰 رصيدك: {balance}", callback_data="show_balance"),
            InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")
        ],
        [
            InlineKeyboardButton("🎁 هدايا ونقاط", callback_data="gifts"),
            InlineKeyboardButton("📞 الدعم", callback_data="support")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.edit_message_text(
            message_text or f"🎰 روليت MS\n\n💰 رصيدك: {balance} نقطة\nاختر من القائمة:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message_text or f"🎰 روليت MS\n\n💰 رصيدك: {balance} نقطة\nاختر من القائمة:",
            reply_markup=reply_markup
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    logger.info(f"زر مضغوط: {data} من المستخدم: {user_id}")
    
    if data == "create_roulette":
        await create_roulette_handler(query, context)
    elif data == "my_stats":
        await my_stats_handler(query, context)
    elif data == "invite_link":
        await invite_link_handler(query, context)
    elif data == "show_balance":
        await show_balance_handler(query, context)
    elif data == "gifts":
        await gifts_handler(query, context)
    elif data == "settings":
        await settings_handler(query, context)
    elif data == "support":
        await support_handler(query, context)
    elif data == "main_menu":
        await show_main_menu(update, user_id)
    elif data == "back_to_menu":
        await show_main_menu(update, user_id)
    elif data.startswith("join_roulette_"):
        await join_roulette_handler(query, context)
    elif data.startswith("stop_roulette_"):
        await stop_roulette_handler(query, context)

# ========== معالجات الأزرار ==========
async def create_roulette_handler(query, context):
    user_id = query.from_user.id
    balance = get_user_balance(user_id)
    
    if balance < 1:
        await query.edit_message_text(
            f"❌ رصيدك غير كافي!\n\n💰 رصيدك الحالي: {balance} نقطة\n💡 تحتاج إلى نقطة واحدة لإنشاء روليت\n\n📤 ادعِ أصدقائك لزيادة رصيدك!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 رابط الدعوة", callback_data="invite_link")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )
        return
    
    # خصم النقطة وإنشاء الروليت
    update_user_balance(user_id, balance - 1)
    
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO roulettes (creator_id, title, max_participants) VALUES (?, ?, ?)',
                   (user_id, "روليت سريع", 10))
    roulette_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🎰 انضم للروليت", callback_data=f"join_roulette_{roulette_id}")],
        [InlineKeyboardButton("⏹ إيقاف الروليت", callback_data=f"stop_roulette_{roulette_id}")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🎰 *تم إنشاء الروليت بنجاح!*\n\n"
        f"🔢 رقم الروليت: #{roulette_id}\n"
        f"👥 العدد المستهدف: 10 أشخاص\n"
        f"💰 تم خصم: 1 نقطة\n"
        f"💎 رصيدك الجديد: {balance - 1} نقطة\n\n"
        f"🎯 شارك الروليت مع أصدقائك!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def my_stats_handler(query, context):
    user_id = query.from_user.id
    
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT balance, invitation_count, total_invitations, joined_date FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    
    cursor.execute('SELECT COUNT(*) FROM roulettes WHERE creator_id = ?', (user_id,))
    roulettes_created = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM participants WHERE user_id = ?', (user_id,))
    roulettes_joined = cursor.fetchone()[0]
    
    conn.close()
    
    if user_data:
        balance, invites, total_invites, join_date = user_data
    else:
        balance, invites, total_invites, join_date = 5, 0, 0, "غير معروف"
    
    stats_text = f"""📊 *إحصائياتك الشخصية*

👤 الاسم: {query.from_user.first_name}
🆔 الإيدي: {user_id}
💰 الرصيد: {balance} نقطة
📅 تاريخ الانضمام: {join_date[:10] if join_date else 'غير معروف'}

📤 *نظام الدعوات*
📨 عدد الدعوات الناجحة: {invites}
👥 إجمالي المدعوين: {total_invites}
🎯 نقاط من الدعوات: {invites} نقطة

🎰 *نشاط الروليت*
🎪 روليتات أنشأتها: {roulettes_created}
🎭 روليتات اشتركت فيها: {roulettes_joined}"""

    keyboard = [
        [InlineKeyboardButton("📤 رابط الدعوة", callback_data="invite_link")],
        [InlineKeyboardButton("🎰 إنشاء روليت", callback_data="create_roulette")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')

async def invite_link_handler(query, context):
    user_id = query.from_user.id
    invite_link = generate_invite_link(user_id)
    
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT invitation_count FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    invite_count = result[0] if result else 0
    conn.close()
    
    invite_text = f"""📤 *نظام الدعوات والحوافز*

🔗 رابط دعوتك الخاص:
`{invite_link}`

🎯 *مكافآت الدعوات:*
✅ لكل صديق يدخل عبر رابطك: +1 نقطة
💰 صديقك يحصل على: 5 نقاط هدية
📈 كلما كثر المدعوين، كثرت النقاط!

📊 *إحصائيات دعواتك:*
📨 عدد الدعوات الناجحة: {invite_count}
💰 نقاط ربحتها من الدعوات: {invite_count} نقطة

🎁 *مكافأة إضافية:* عند وصولك لـ10 دعوات ناجحة، تحصل على 5 نقاط إضافية!"""

    keyboard = [
        [InlineKeyboardButton("🔗 مشاركة الرابط", url=f"https://t.me/share/url?url={invite_link}&text=انضم%20إلى%20روليت%20MS%20-%20أفضل%20بوت%20روليت%20على%20تيليجرام!%20🎰")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(invite_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_balance_handler(query, context):
    user_id = query.from_user.id
    balance = get_user_balance(user_id)
    
    await query.edit_message_text(
        f"💰 *رصيدك الحالي*\n\n💎 {balance} نقطة\n\n📈 استمر في الدعوة لكسب المزيد من النقاط!",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 كسب النقاط", callback_data="invite_link")],
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ])
    )

async def gifts_handler(query, context):
    user_id = query.from_user.id
    balance = get_user_balance(user_id)
    
    gifts_text = f"""🎁 *نظام النقاط والهدايا*

💰 رصيدك الحالي: *{balance} نقطة*

🎯 *طرق كسب النقاط:*
✅ انضمامك الأول: 5 نقاط هدية
📤 كل دعوة ناجحة: +1 نقطة
🎰 كل فوز في روليت: +3 نقاط
📈 كل 10 دعوات ناجحة: +5 نقاط مكافأة

💸 *استخدام النقاط:*
🎪 إنشاء روليت: -1 نقطة

🚀 *مستويات المستخدمين:*
🟢 مبتدئ (0-10 نقاط)
🟡 محترف (11-50 نقطة) 
🔴 خبير (51+ نقطة)"""

    keyboard = [
        [InlineKeyboardButton("📤 كسب النقاط بالدعوات", callback_data="invite_link")],
        [InlineKeyboardButton("🎰 إنشاء روليت", callback_data="create_roulette")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(gifts_text, reply_markup=reply_markup, parse_mode='Markdown')

async def settings_handler(query, context):
    settings_text = """⚙️ *إعدادات البوت*

🔔 *الإشعارات:*
✅ تفعيل الإشعارات

🌐 *اللغة:*
🇸🇦 العربية

🔒 *الخصوصية:*
👤 إظهار اسمي في الروليت"""

    keyboard = [
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')

async def support_handler(query, context):
    support_text = """📞 *الدعم الفني*

للاستفسارات والدعم الفني:

👨‍💻 الدعم الفني: @m_n_et

⏰ أوقات الدعم:
من الساعة 9:00 صباحاً حتى 12:00 منتصف الليل

🔧 *الأمور الفنية المدعومة:*
- مشاكل في إنشاء الروليت
- مشاكل في النقاط
- مشاكل في الدعوات
- اقتراحات وتحسينات"""

    keyboard = [
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(support_text, reply_markup=reply_markup, parse_mode='Markdown')

async def join_roulette_handler(query, context):
    try:
        roulette_id = int(query.data.split('_')[2])
        user_id = query.from_user.id
        
        conn = sqlite3.connect('roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # التحقق من المشاركة السابقة
        cursor.execute('SELECT * FROM participants WHERE roulette_id = ? AND user_id = ?', (roulette_id, user_id))
        if cursor.fetchone():
            await query.answer("أنت مشترك بالفعل في هذا الروليت!", show_alert=True)
            conn.close()
            return
        
        # إضافة المشارك
        cursor.execute('INSERT INTO participants (roulette_id, user_id) VALUES (?, ?)', (roulette_id, user_id))
        cursor.execute('UPDATE roulettes SET participants_count = participants_count + 1 WHERE id = ?', (roulette_id,))
        
        # الحصول على عدد المشاركين
        cursor.execute('SELECT participants_count, max_participants FROM roulettes WHERE id = ?', (roulette_id,))
        result = cursor.fetchone()
        current_participants, max_participants = result
        
        conn.commit()
        conn.close()
        
        await query.answer(f"تم انضمامك للروليت! ({current_participants}/{max_participants})", show_alert=True)
        
    except Exception as e:
        logger.error(f"خطأ في الانضمام للروليت: {e}")
        await query.answer("حدث خطأ أثناء الانضمام للروليت", show_alert=True)

async def stop_roulette_handler(query, context):
    try:
        roulette_id = int(query.data.split('_')[2])
        user_id = query.from_user.id
        
        conn = sqlite3.connect('roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT creator_id FROM roulettes WHERE id = ?', (roulette_id,))
        result = cursor.fetchone()
        
        if result and result[0] == user_id:
            cursor.execute('UPDATE roulettes SET status = "stopped" WHERE id = ?', (roulette_id,))
            conn.commit()
            await query.answer("تم إيقاف الروليت بنجاح!", show_alert=True)
        else:
            await query.answer("فقط منشئ الروليت يمكنه إيقافه!", show_alert=True)
        
        conn.close()
        
    except Exception as e:
        logger.error(f"خطأ في إيقاف الروليت: {e}")
        await query.answer("حدث خطأ أثناء إيقاف الروليت", show_alert=True)

# ========== الأوامر الإدارية ==========
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ غير مصرح لك بالوصول!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")],
        [InlineKeyboardButton("💰 إضافة نقاط", callback_data="admin_add_points")],
        [InlineKeyboardButton("🎰 إدارة الروليت", callback_data="admin_roulettes")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛠 *لوحة تحكم الأدمن* 🛠\n\nاختر الإدارة المناسبة:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def add_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ usage: /add_points user_id amount")
        return
    
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        
        current_balance = get_user_balance(user_id)
        new_balance = current_balance + amount
        update_user_balance(user_id, new_balance)
        
        await update.message.reply_text(f"✅ تم إضافة {amount} نقطة للمستخدم {user_id}\n💰 الرصيد الجديد: {new_balance}")
            
    except ValueError:
        await update.message.reply_text("❌ رقم المستخدم أو الكمية غير صحيحة")

# ========== التشغيل الرئيسي ==========
def main():
    # تحقق من التوكن
    if not BOT_TOKEN:
        print("❌ خطأ: BOT_TOKEN غير موجود!")
        return
    
    print(f"✅ بدء تشغيل بوت روليت MS...")
    print(f"🔹 التوكن: {BOT_TOKEN[:10]}...")
    print(f"🔹 أدمن ID: {ADMIN_ID}")
    
    # تهيئة قاعدة البيانات
    init_db()
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("add_points", add_points_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    print("🎉 البوت يعمل الآن!")
    print("🔹 للأعضاء: /start")
    print(f"🔹 للأدمن: /admin")
    
    # تشغيل البوت
    application.run_polling()

if __name__ == '__main__':
    main()
