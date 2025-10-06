import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# إعدادات البوت
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
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
    
    conn.commit()
    conn.close()

# === دوال البوت الرئيسي ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    args = context.args
    
    invited_by = 0
    if args and args[0].startswith('ref_'):
        try:
            invited_by = int(args[0].split('_')[1])
            # إضافة نقطة للداعي
            conn = sqlite3.connect('roulette.db', check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET balance = balance + 1, invitation_count = invitation_count + 1, total_invitations = total_invitations + 1 WHERE user_id = ?', (invited_by,))
            cursor.execute('INSERT INTO invitations (inviter_id, invited_id) VALUES (?, ?)', (invited_by, user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error in referral: {e}")
    
    # إضافة/تحديث المستخدم
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

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    if data == "create_quick_roulette":
        await create_roulette(query, context)
    elif data == "my_stats":
        await my_stats(query, context)
    elif data == "invite_link":
        await invite_link(query, context)
    elif data == "balance":
        await show_balance(query, context)
    elif data == "gifts":
        await gifts_info(query, context)
    elif data == "settings":
        await settings_menu(query, context)
    elif data == "support":
        await support(query, context)
    elif data == "main_menu":
        await main_menu_callback(query, context)

# === دوال الأدمن ===
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ غير مصرح لك بالوصول!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="bot_stats")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="manage_users")],
        [InlineKeyboardButton("💰 إدارة النقاط", callback_data="manage_points")],
        [InlineKeyboardButton("🎰 إدارة الروليت", callback_data="manage_roulettes")],
        [InlineKeyboardButton("📈 تقارير مفصلة", callback_data="detailed_reports")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🛠 *لوحة تحكم أدمن روليت MS* 🛠\n\n"
        "اختر الإدارة المناسبة:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ غير مصرح لك بالوصول!")
        return
    
    data = query.data
    
    if data == "bot_stats":
        await bot_stats(query, context)
    elif data == "manage_users":
        await manage_users(query, context)
    elif data == "manage_points":
        await manage_points(query, context)
    elif data == "manage_roulettes":
        await manage_roulettes(query, context)
    elif data == "detailed_reports":
        await detailed_reports(query, context)
    elif data == "admin_main":
        await admin_start_callback(query, context)

# === دوال إضافية (يجب إضافتها) ===
async def create_roulette(query, context):
    user_id = query.from_user.id
    await query.edit_message_text("🎰 إنشاء روليت سريع قريباً...")

async def my_stats(query, context):
    user_id = query.from_user.id
    await query.edit_message_text("📊 جاري تحميل إحصائياتك...")

async def invite_link(query, context):
    user_id = query.from_user.id
    invite_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    await query.edit_message_text(f"🔗 رابط دعوتك:\n`{invite_link}`", parse_mode='Markdown')

# ... باقي الدوال الأساسية

async def bot_stats(query, context):
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    conn.close()
    
    await query.edit_message_text(f"📊 إجمالي المستخدمين: {total_users}")

# ... باقي دوال الأدمن

def main():
    # تحقق من التوكن
    if not BOT_TOKEN:
        print("❌ خطأ: BOT_TOKEN غير موجود!")
        return
    
    print(f"✅ بدء تشغيل بوت روليت MS بالتوكن: {BOT_TOKEN[:10]}...")
    
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers للبوت الرئيسي
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # إضافة handlers للأدمن
    application.add_handler(CommandHandler("admin", admin_start))
    application.add_handler(CommandHandler("add_points", add_points_command))
    
    print("✅ البوت جاهز للاستخدام!")
    print("🔹 للأعضاء: /start")
    print(f"🔹 للأدمن: /admin (ID: {ADMIN_ID})")
    
    application.run_polling()

# دوال الأوامر الإدارية
async def add_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ usage: /add_points user_id amount")
        return
    
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        
        conn = sqlite3.connect('roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        
        cursor.execute('SELECT first_name, balance FROM users WHERE user_id = ?', (user_id,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            name, new_balance = user_data
            await update.message.reply_text(f"✅ تم إضافة {amount} نقطة للمستخدم {name}\n💰 الرصيد الجديد: {new_balance}")
        else:
            await update.message.reply_text("❌ المستخدم غير موجود")
            
    except ValueError:
        await update.message.reply_text("❌ رقم المستخدم أو الكمية غير صحيحة")

if __name__ == '__main__':
    main()
