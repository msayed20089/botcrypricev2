import logging
import sqlite3
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# إعدادات البوت الإداري
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "8468030434:AAFsD_w1CLVasp0wN2ce5hT3zWxNs438OLI")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6096879850"))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ غير مصرح لك بالوصول!")
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
    elif data == "forced_subscription":
        await forced_subscription(query, context)
    elif data == "manage_roulettes":
        await manage_roulettes(query, context)
    elif data == "detailed_reports":
        await detailed_reports(query, context)
    elif data == "admin_main":
        await admin_start_callback(query, context)

async def admin_start_callback(query, context):
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="bot_stats")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="manage_users")],
        [InlineKeyboardButton("💰 إدارة النقاط", callback_data="manage_points")],
        [InlineKeyboardButton("📢 الاشتراك الإجباري", callback_data="forced_subscription")],
        [InlineKeyboardButton("🎰 إدارة الروليت", callback_data="manage_roulettes")],
        [InlineKeyboardButton("📈 تقارير مفصلة", callback_data="detailed_reports")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🛠 *لوحة تحكم أدمن روليت MS* 🛠\n\n"
        "اختر الإدارة المناسبة:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def bot_stats(query, context):
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
    
    await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')

async def manage_users(query, context):
    conn = sqlite3.connect('roulette.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, username, first_name, balance, joined_date FROM users ORDER BY joined_date DESC LIMIT 10')
    recent_users = cursor.fetchall()
    
    users_text = "👥 *آخر 10 مستخدمين*\n\n"
    
    for user in recent_users:
        user_id, username, first_name, balance, joined_date = user
        username = username or "بدون معرف"
        users_text += f"👤 {first_name} (@{username})\n🆔 {user_id} | 💰 {balance} نقطة\n📅 {joined_date[:10]}\n\n"
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    conn.close()
    
    users_text += f"📊 إجمالي المستخدمين: {total_users}"
    
    keyboard = [
        [InlineKeyboardButton("🔍 بحث عن مستخدم", callback_data="search_user")],
        [InlineKeyboardButton("📊 أفضل 10 دعاة", callback_data="top_inviters")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="admin_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(users_text, reply_markup=reply_markup, parse_mode='Markdown')

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

async def subtract_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ usage: /subtract_points user_id amount")
        return
    
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        
        conn = sqlite3.connect('roulette.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        
        cursor.execute('SELECT first_name, balance FROM users WHERE user_id = ?', (user_id,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            name, new_balance = user_data
            await update.message.reply_text(f"✅ تم خصم {amount} نقطة من المستخدم {name}\n💰 الرصيد الجديد: {new_balance}")
        else:
            await update.message.reply_text("❌ المستخدم غير موجود")
            
    except ValueError:
        await update.message.reply_text("❌ رقم المستخدم أو الكمية غير صحيحة")

def main():
    application = Application.builder().token(ADMIN_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", admin_start))
    application.add_handler(CommandHandler("add_points", add_points_command))
    application.add_handler(CommandHandler("subtract_points", subtract_points_command))
    application.add_handler(CallbackQueryHandler(admin_callback))
    
    application.run_polling()

if __name__ == '__main__':
    main()
