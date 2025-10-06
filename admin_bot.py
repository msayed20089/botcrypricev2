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
        "🛠 *لوحة تحكم الأدمن* 🛠\n\n"
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
        "🛠 *لوحة تحكم الأدمن* 🛠\n\n"
        "اختر الإدارة المناسبة:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def bot_stats(query, context):
    conn = sqlite3.connect('roulette.db')
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
    
    stats_text = f"""📊 *إحصائيات البوت الشاملة*

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
    conn = sqlite3.connect('roulette.db')
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

async def manage_points(query, context):
    points_text = """💰 *إدارة النقاط والنظام المالي*

🎯 *العمليات المتاحة:*
➕ إضافة نقاط لمستخدم
➖ خصم نقاط من مستخدم
📊 عرض رصيد مستخدم
🔄 ضبط رصيد مستخدم

📈 *إحصائيات النقاط:*
- إجمالي النقاط في النظام
- توزيع النقاط على المستخدمين
- حركة النقاط اليومية"""

    keyboard = [
        [InlineKeyboardButton("➕ إضافة نقاط", callback_data="add_points_menu")],
        [InlineKeyboardButton("➖ خصم نقاط", callback_data="subtract_points_menu")],
        [InlineKeyboardButton("📊 تقرير النقاط", callback_data="points_report")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="admin_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(points_text, reply_markup=reply_markup, parse_mode='Markdown')

async def forced_subscription(query, context):
    conn = sqlite3.connect('roulette.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT channel_username, channel_id FROM forced_channels')
    channels = cursor.fetchall()
    
    channels_text = "📢 *قنوات الاشتراك الإجباري*\n\n"
    
    if channels:
        for i, (channel_username, channel_id) in enumerate(channels, 1):
            channels_text += f"{i}. @{channel_username} (ID: {channel_id})\n"
    else:
        channels_text += "❌ لا توجد قنوات مضافة\n\n"
    
    channels_text += "\n🎯 *لإضافة قناة:*\nأرسل /add_channel @username channel_id"
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة قناة", callback_data="add_channel")],
        [InlineKeyboardButton("🗑 حذف قناة", callback_data="remove_channel")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="admin_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(channels_text, reply_markup=reply_markup, parse_mode='Markdown')

async def manage_roulettes(query, context):
    conn = sqlite3.connect('roulette.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT r.id, u.first_name, r.participants_count, r.max_participants, r.created_date FROM roulettes r JOIN users u ON r.creator_id = u.user_id ORDER BY r.created_date DESC LIMIT 10')
    recent_roulettes = cursor.fetchall()
    
    roulettes_text = "🎰 *آخر 10 روليتات*\n\n"
    
    for roulette in recent_roulettes:
        r_id, creator_name, participants, max_participants, created_date = roulette
        roulettes_text += f"🎪 روليت #{r_id}\n👤 بواسطة: {creator_name}\n👥 {participants}/{max_participants}\n📅 {created_date[:16]}\n\n"
    
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🔄 تحديث", callback_data="manage_roulettes")],
        [InlineKeyboardButton("📊 إحصائيات الروليت", callback_data="roulettes_stats")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="admin_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(roulettes_text, reply_markup=reply_markup, parse_mode='Markdown')

async def detailed_reports(query, context):
    conn = sqlite3.connect('roulette.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT first_name, username, invitation_count, total_invitations FROM users ORDER BY invitation_count DESC LIMIT 10')
    top_inviters = cursor.fetchall()
    
    cursor.execute('SELECT COUNT(*), date(created_date) FROM roulettes GROUP BY date(created_date) ORDER BY date(created_date) DESC LIMIT 7')
    weekly_activity = cursor.fetchall()
    
    reports_text = "📈 *تقارير مفصلة*\n\n"
    
    reports_text += "🏆 *أفضل 10 دعاة:*\n"
    for i, (name, username, invites, total) in enumerate(top_inviters, 1):
        username = username or "بدون معرف"
        reports_text += f"{i}. {name} (@{username}) - {invites} دعوة\n"
    
    reports_text += "\n📊 *نشاط الأسبوع:*\n"
    for count, date in weekly_activity:
        reports_text += f"📅 {date}: {count} روليت\n"
    
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton("📤 تقرير الدعوات", callback_data="invitations_report")],
        [InlineKeyboardButton("🎰 تقرير الروليت", callback_data="roulettes_report")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="admin_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(reports_text, reply_markup=reply_markup, parse_mode='Markdown')

async def add_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ usage: /add_points user_id amount")
        return
    
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        
        conn = sqlite3.connect('roulette.db')
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
        
        conn = sqlite3.connect('roulette.db')
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
    
    port = int(os.environ.get('PORT', 8443))
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=ADMIN_BOT_TOKEN,
        webhook_url=f"https://your-app-name.railway.app/{ADMIN_BOT_TOKEN}"
    )

if __name__ == '__main__':
    main()
