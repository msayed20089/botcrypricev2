import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# إعدادات البوت الإداري
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "8468030434:AAFsD_w1CLVasp0wN2ce5hT3zWxNs438OLI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6096879850"))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def admin_start(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("❌ غير مصرح لك بالوصول!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="bot_stats")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="manage_users")],
        [InlineKeyboardButton("💰 إدارة النقاط", callback_data="manage_points")],
        [InlineKeyboardButton("📢 الاشتراك الإجباري", callback_data="forced_subscription")],
        [InlineKeyboardButton("🎰 إدارة الروليت", callback_data="manage_roulettes")],
        [InlineKeyboardButton("📈 تقارير مفصلة", callback_data="detailed_reports")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "🛠 *لوحة تحكم أدمن روليت MS* 🛠\n\n"
        "اختر الإدارة المناسبة:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def admin_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    if query.from_user.id != ADMIN_ID:
        query.edit_message_text("❌ غير مصرح لك بالوصول!")
        return
    
    data = query.data
    
    if data == "bot_stats":
        bot_stats(query, context)
    elif data == "manage_users":
        manage_users(query, context)
    elif data == "manage_points":
        manage_points(query, context)
    elif data == "forced_subscription":
        forced_subscription(query, context)
    elif data == "manage_roulettes":
        manage_roulettes(query, context)
    elif data == "detailed_reports":
        detailed_reports(query, context)
    elif data == "admin_main":
        admin_start_callback(query, context)

def admin_start_callback(query, context):
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="bot_stats")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="manage_users")],
        [InlineKeyboardButton("💰 إدارة النقاط", callback_data="manage_points")],
        [InlineKeyboardButton("📢 الاشتراك الإجباري", callback_data="forced_subscription")],
        [InlineKeyboardButton("🎰 إدارة الروليت", callback_data="manage_roulettes")],
        [InlineKeyboardButton("📈 تقارير مفصلة", callback_data="detailed_reports")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        "🛠 *لوحة تحكم أدمن روليت MS* 🛠\n\n"
        "اختر الإدارة المناسبة:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

def bot_stats(query, context):
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE date(joined_date) = date("now")')
    new_today = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM roulettes')
    total_roulettes = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM roulettes WHERE date(created_date) = date("now")')
    roulettes_today = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(balance) FROM users')
    total_points = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(invitation_count) FROM users')
    total_invitations = cursor.fetchone()[0] or 0
    
    conn.close()
    
    stats_text = f"""📊 *إحصائيات بوت روليت MS*

👥 *المستخدمين:*
👤 إجمالي المستخدمين: {total_users}
🆕 مستخدمين جدد اليوم: {new_today}

🎰 *الروليت:*
🎪 إجمالي الروليتات: {total_roulettes}
🆕 روليتات اليوم: {roulettes_today}

💰 *النقاط:*
💎 إجمالي النقاط: {total_points}
📤 إجمالي الدعوات: {total_invitations}

📈 *نسبة النشاط:*
{(roulettes_today/max(total_users,1))*100:.1f}% نشاط اليوم"""

    keyboard = [
        [InlineKeyboardButton("🔄 تحديث", callback_data="bot_stats")],
        [InlineKeyboardButton("📈 تقارير مفصلة", callback_data="detailed_reports")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="admin_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')

# باقي الدوال تبقى كما هي مع تغيير الاسم لـ"روليت MS"

def main():
    updater = Updater(ADMIN_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", admin_start))
    dp.add_handler(CommandHandler("add_points", add_points_command))
    dp.add_handler(CommandHandler("subtract_points", subtract_points_command))
    dp.add_handler(CallbackQueryHandler(admin_callback))
    
    PORT = int(os.environ.get('PORT', 8444))
    updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=ADMIN_BOT_TOKEN,
        webhook_url=f"https://your-app-name.railway.app/{ADMIN_BOT_TOKEN}"
    )
    updater.idle()

if __name__ == '__main__':
    main()
