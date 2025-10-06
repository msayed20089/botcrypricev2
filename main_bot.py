import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# إعدادات البوت
BOT_TOKEN = os.getenv("BOT_TOKEN", "8399150202:AAEvr37r05xzbjhwinnGZQIWAuoylpsNflg")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6096879850"))
BOT_USERNAME = "lllllllofdkokbot"  # يوزر البوت الجديد

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
    
    conn.commit()
    conn.close()

def check_balance(user_id, cost=1):
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0] >= cost:
        return True, result[0]
    return False, result[0] if result else 0

def deduct_points(user_id, points=1):
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (points, user_id))
    conn.commit()
    conn.close()

def add_points(user_id, points=1):
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (points, user_id))
    conn.commit()
    conn.close()

def generate_invite_link(user_id):
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    args = context.args
    
    invited_by = 0
    if args and args[0].startswith('ref_'):
        try:
            invited_by = int(args[0].split('_')[1])
            add_points(invited_by, 1)
            
            conn = sqlite3.connect('roulette.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET invitation_count = invitation_count + 1, total_invitations = total_invitations + 1 WHERE user_id = ?', (invited_by,))
            cursor.execute('INSERT INTO invitations (inviter_id, invited_id) VALUES (?, ?)', (invited_by, user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error in referral: {e}")
    
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, invited_by) 
        VALUES (?, ?, ?, ?)
    ''', (user_id, user.username, user.first_name, invited_by))
    
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance_result = cursor.fetchone()
    balance = balance_result[0] if balance_result else 5
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🎰 إنشاء روليت سريع (-1 نقطة)", callback_data="create_quick_roulette")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
        [InlineKeyboardButton("📤 رابط الدعوة", callback_data="invite_link")],
        [InlineKeyboardButton("💰 رصيدك", callback_data="balance"), InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
        [InlineKeyboardButton("🎁 هدايا ونقاط", callback_data="gifts"), InlineKeyboardButton("📞 الدعم", callback_data="support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""🎉 أهلاً بك {user.first_name} في روليت MS! 🎰

🆔 الإيدي: {user_id}
💰 رصيدك: {balance} نقطة

🎰 يمكنك إنشاء روليت سريع بكلفة نقطة واحدة
📤 ادعِ أصدقائك واكسب نقطة عن كل دعوة ناجحة"""

    update.message.reply_text(welcome_text, reply_markup=reply_markup)

def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "create_quick_roulette":
        create_roulette(query, context)
    elif data == "my_stats":
        my_stats(query, context)
    elif data == "invite_link":
        invite_link(query, context)
    elif data == "balance":
        show_balance(query, context)
    elif data == "gifts":
        gifts_info(query, context)
    elif data == "settings":
        settings_menu(query, context)
    elif data == "support":
        support(query, context)
    elif data == "main_menu":
        main_menu_callback(query, context)
    elif data.startswith("join_roulette_"):
        join_roulette(query, context)
    elif data.startswith("stop_roulette_"):
        stop_roulette(query, context)

def create_roulette(query, context):
    user_id = query.from_user.id
    
    has_balance, current_balance = check_balance(user_id)
    
    if not has_balance:
        query.edit_message_text(
            f"❌ رصيدك غير كافي!\n\n💰 رصيدك الحالي: {current_balance} نقطة\n💡 تحتاج إلى نقطة واحدة لإنشاء روليت\n\n📤 ادعِ أصدقائك لزيادة رصيدك!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 رابط الدعوة", callback_data="invite_link")],
                [InlineKeyboardButton("💰 شحن الرصيد", callback_data="gifts")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
            ])
        )
        return
    
    deduct_points(user_id, 1)
    
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
        [InlineKeyboardButton("📊 مشاهدة المشاركين", callback_data=f"view_participants_{roulette_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        "🎰 *روليت سريع لـ 10 أشخاص!*\n\n"
        "📊 المشاركة ستغلق بعد اكتمال العدد\n\n"
        "👥 المشاركون: 1/10\n\n"
        "💰 كلفة الروليت: 1 نقطة\n"
        "🎁 الجائزة: توزيع النقاط على الفائزين",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def my_stats(query, context):
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
        [InlineKeyboardButton("🎰 إنشاء روليت", callback_data="create_quick_roulette")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')

def invite_link(query, context):
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
    
    query.edit_message_text(invite_text, reply_markup=reply_markup, parse_mode='Markdown')

def show_balance(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    balance = result[0] if result else 5
    conn.close()
    
    query.edit_message_text(f"💰 رصيدك الحالي: {balance} نقطة")

def gifts_info(query, context):
    user_id = query.from_user.id
    
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    balance = result[0] if result else 5
    conn.close()
    
    gifts_text = f"""🎁 *نظام النقاط والهدايا*

💰 رصيدك الحالي: *{balance} نقطة*

🎯 *طرق كسب النقاط:*
✅ انضمامك الأول: 5 نقاط هدية
📤 كل دعوة ناجحة: +1 نقطة
🎰 كل فوز في روليت: +2 نقطة
📈 كل 10 دعوات ناجحة: +5 نقاط مكافأة

💸 *استخدام النقاط:*
🎪 إنشاء روليت: -1 نقطة
🎁 تحويل النقاط للأصدقاء

🚀 *مستويات المستخدمين:*
🟢 مبتدئ (0-10 نقاط)
🟡 محترف (11-50 نقطة) 
🔴 خبير (51+ نقطة)"""

    keyboard = [
        [InlineKeyboardButton("📤 كسب النقاط بالدعوات", callback_data="invite_link")],
        [InlineKeyboardButton("🎰 إنشاء روليت", callback_data="create_quick_roulette")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(gifts_text, reply_markup=reply_markup, parse_mode='Markdown')

def settings_menu(query, context):
    settings_text = """⚙️ *إعدادات البوت*

🔔 *الإشعارات:*
✅ تفعيل الإشعارات
❌ إيقاف الإشعارات

🌐 *اللغة:*
🇸🇦 العربية

🔒 *الخصوصية:*
👤 إظهار اسمي في الروليت
👻 المشاركة بشكل مجهول"""

    keyboard = [
        [InlineKeyboardButton("🔔 إدارة الإشعارات", callback_data="notifications")],
        [InlineKeyboardButton("🔒 إعدادات الخصوصية", callback_data="privacy")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(settings_text, reply_markup=reply_markup, parse_mode='Markdown')

def support(query, context):
    support_text = """📞 *الدعم الفني*

للاستفسارات والدعم الفني:

👨‍💻 الدعم الفني: @M_N_ET

⏰ أوقات الدعم:
من الساعة 9:00 صباحاً حتى 12:00 منتصف الليل

🔧 *الأمور الفنية المدعومة:*
- مشاكل في إنشاء الروليت
- مشاكل في النقاط
- مشاكل في الدعوات
- اقتراحات وتحسينات"""

    keyboard = [
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")],
        [InlineKeyboardButton("📖 التعليمات", callback_data="instructions")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(support_text, reply_markup=reply_markup, parse_mode='Markdown')

def join_roulette(query, context):
    try:
        roulette_id = int(query.data.split('_')[2])
        user_id = query.from_user.id
        
        conn = sqlite3.connect('roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM participants WHERE roulette_id = ? AND user_id = ?', (roulette_id, user_id))
        if cursor.fetchone():
            query.answer("أنت مشترك بالفعل في هذا الروليت!", show_alert=True)
            conn.close()
            return
        
        cursor.execute('INSERT INTO participants (roulette_id, user_id) VALUES (?, ?)', (roulette_id, user_id))
        cursor.execute('UPDATE roulettes SET participants_count = participants_count + 1 WHERE id = ?', (roulette_id,))
        
        cursor.execute('SELECT participants_count, max_participants FROM roulettes WHERE id = ?', (roulette_id,))
        result = cursor.fetchone()
        current_participants, max_participants = result
        
        conn.commit()
        conn.close()
        
        query.answer(f"تم انضمامك للروليت! ({current_participants}/{max_participants})", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error in join_roulette: {e}")
        query.answer("حدث خطأ أثناء الانضمام للروليت", show_alert=True)

def stop_roulette(query, context):
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
            query.answer("تم إيقاف الروليت بنجاح!", show_alert=True)
        else:
            query.answer("只有创建者可以停止这个轮盘!", show_alert=True)
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in stop_roulette: {e}")
        query.answer("حدث خطأ أثناء إيقاف الروليت", show_alert=True)

def main_menu_callback(query, context):
    user_id = query.from_user.id
    
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    balance = result[0] if result else 5
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🎰 إنشاء روليت سريع (-1 نقطة)", callback_data="create_quick_roulette")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
        [InlineKeyboardButton("📤 رابط الدعوة", callback_data="invite_link")],
        [InlineKeyboardButton("💰 رصيدك", callback_data="balance"), InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
        [InlineKeyboardButton("🎁 هدايا ونقاط", callback_data="gifts"), InlineKeyboardButton("📞 الدعم", callback_data="support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        f"🎰 *مرحباً بك في روليت MS* 🎰\n\n💰 رصيدك: {balance} نقطة\nاختر من القائمة:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def menu_command(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = user.id
    
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    balance = result[0] if result else 5
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🎰 إنشاء روليت سريع (-1 نقطة)", callback_data="create_quick_roulette")],
        [InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats")],
        [InlineKeyboardButton("📤 رابط الدعوة", callback_data="invite_link")],
        [InlineKeyboardButton("💰 رصيدك", callback_data="balance"), InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
        [InlineKeyboardButton("🎁 هدايا ونقاط", callback_data="gifts"), InlineKeyboardButton("📞 الدعم", callback_data="support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"🎰 *مرحباً بك في روليت MS* 🎰\n\n💰 رصيدك: {balance} نقطة\nاختر من القائمة:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def main():
    init_db()
    
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("menu", menu_command))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    
    # استخدم Polling بدلاً من Webhook للبساطة
    PORT = int(os.environ.get('PORT', 8443))
    updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"https://your-app-name.railway.app/{BOT_TOKEN}"
    )
    updater.idle()

if __name__ == '__main__':
    main()
