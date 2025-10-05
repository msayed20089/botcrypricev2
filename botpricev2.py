import logging
import aiohttp
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import re
import time
import random

# إعدادات البوت
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = "7097772026:AAFWFBSY38DjSYj3MGatXswfS9XjSqHceso"
CHANNEL_LINK = "https://t.me/zforexms"

# خطوط إموجيز للتصميم العصري
EMOJIS = {
    "welcome": "🌟", "money": "💸", "chart": "📊", "rocket": "🚀", "fire": "🔥",
    "coin": "🪙", "diamond": "💎", "star": "⭐", "flash": "⚡", "growth": "📈",
    "down": "📉", "clock": "⏰", "search": "🔍", "check": "✅", "warning": "⚠️",
    "error": "❌", "channel": "📢", "database": "💾", "signal": "📶", "speed": "💨"
}

# 🔄 Multiple APIs
APIS = [
    {
        'name': 'CoinGecko',
        'search_url': 'https://api.coingecko.com/api/v3/search',
        'price_url': 'https://api.coingecko.com/api/v3/simple/price',
        'weight': 10  # الأولوية
    },
    {
        'name': 'CoinPaprika', 
        'search_url': 'https://api.coinpaprika.com/v1/search',
        'price_url': 'https://api.coinpaprika.com/v1/tickers',
        'weight': 8
    },
    {
        'name': 'Binance',
        'search_url': None,
        'price_url': 'https://api.binance.com/api/v3/ticker/price',
        'weight': 7
    }
] 

class ModernBot:
    def __init__(self):
        # 💾 Caching system
        self.price_cache = {}
        self.search_cache = {}
        self.cache_duration = 30  # ثانية واحدة
        
    def get_cached_data(self, cache_type, key):
        """الحصول على بيانات من الكاش"""
        cache_dict = self.price_cache if cache_type == 'price' else self.search_cache
        if key in cache_dict:
            data, timestamp = cache_dict[key]
            if time.time() - timestamp < self.cache_duration:
                return data
        return None
    
    def set_cached_data(self, cache_type, key, data):
        """تخزين بيانات في الكاش"""
        cache_dict = self.price_cache if cache_type == 'price' else self.search_cache
        cache_dict[key] = (data, time.time())

    def create_modern_message(self, title, content, emoji="🌟"):
        """إنشاء رسالة عصرية بتصميم حديث"""
        message = f"{emoji} ━━━━━━━━━━━━━━━ {emoji}"
        message += f"{content}"
        message += f"{emoji} ━━━━━━━━━━━━━━━ {emoji}"
        return message

    def create_price_card(self, amount, symbol, coin_data, price_data, source):
        """إنشاء كارت سعر عصري"""
        current_time = datetime.now().strftime("%I:%M %p • %d/%m/%Y")
        
        coin_name = coin_data.get('name', 'Unknown')
        coin_symbol = coin_data.get('symbol', '').upper()
        
        usd_price = price_data.get('usd', 0)
        change_24h = price_data.get('usd_24h_change', 0)
        
        total_value_usd = amount * usd_price
        
        # تحديد اللون حسب التغير
        if change_24h > 0:
            trend_emoji = EMOJIS["growth"]
            trend_color = "🟢"
            trend_text = f"+{change_24h:.2f}%"
        else:
            trend_emoji = EMOJIS["down"]
            trend_color = "🔴" 
            trend_text = f"{change_24h:.2f}%"

        message = f"{EMOJIS['coin']} ━━━ *السعر الحالي* ━━━ {EMOJIS['coin']}\n\n"
        
        message += f"🎯 *{coin_name}* : *{coin_symbol}*\n"
        
        message += f" *الكمية:* {amount:,} {symbol}\n"
        message += f" *السعر:* `${usd_price:,.6f}`\n"
        message += f" *القيمة:* `${total_value_usd:,.2f}`\n\n"
        
        message += f" *أداء 24 ساعة:*\n"
        message += f"   {trend_emoji} {trend_color} *{trend_text}*\n\n"
        
        message += f"{EMOJIS['clock']} **{current_time}**"
        
        return message

# إنشاء كائن البوت العصري
modern_bot = ModernBot()

# 🔄 Multiple APIs Search
async def search_coins_multiple(query):
    """البحث عن العملات باستخدام multiple APIs"""
    # التحقق من الكاش أولاً
    cached_result = modern_bot.get_cached_data('search', query.lower())
    if cached_result:
        return cached_result
    
    # ترتيب APIs حسب الأولوية
    sorted_apis = sorted(APIS, key=lambda x: x['weight'], reverse=True)
    
    for api in sorted_apis:
        if api['name'] == 'CoinGecko':
            try:
                async with aiohttp.ClientSession() as session:
                    url = api['search_url']
                    params = {'query': query}
                    
                    async with session.get(url, params=params, timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            coins = data.get('coins', [])
                            formatted_coins = []
                            for coin in coins[:8]:  # تخفيف النتائج
                                formatted_coins.append({
                                    'id': coin.get('id'),
                                    'name': coin.get('name'),
                                    'symbol': coin.get('symbol', '').upper(),
                                    'api_source': 'CoinGecko'
                                })
                            # تخزين في الكاش
                            modern_bot.set_cached_data('search', query.lower(), formatted_coins)
                            return formatted_coins
            except Exception as e:
                print(f"CoinGecko search error: {e}")
                continue
                
        elif api['name'] == 'CoinPaprika':
            try:
                async with aiohttp.ClientSession() as session:
                    url = api['search_url']
                    params = {'q': query, 'limit': 8}
                    
                    async with session.get(url, params=params, timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            coins = data.get('currencies', [])
                            formatted_coins = []
                            for coin in coins:
                                formatted_coins.append({
                                    'id': coin.get('id'),
                                    'name': coin.get('name'),
                                    'symbol': coin.get('symbol', '').upper(),
                                    'api_source': 'CoinPaprika'
                                })
                            modern_bot.set_cached_data('search', query.lower(), formatted_coins)
                            return formatted_coins
            except Exception as e:
                print(f"CoinPaprika search error: {e}")
                continue
    
    return []

# ⚡ Multiple APIs Price with Fallbacks
async def get_coin_price_multiple(coin_id, symbol):
    """الحصول على سعر العملة مع fallbacks متعددة"""
    # التحقق من الكاش أولاً
    cache_key = f"{coin_id}_{symbol}"
    cached_price = modern_bot.get_cached_data('price', cache_key)
    if cached_price:
        return cached_price
    
    sorted_apis = sorted(APIS, key=lambda x: x['weight'], reverse=True)
    
    for api in sorted_apis:
        try:
            if api['name'] == 'CoinGecko':
                price_data = await get_coingecko_price(coin_id)
                if price_data and price_data.get('usd'):
                    price_data['source'] = 'CoinGecko'
                    modern_bot.set_cached_data('price', cache_key, price_data)
                    return price_data
                    
            elif api['name'] == 'CoinPaprika':
                price_data = await get_coinpaprika_price(coin_id)
                if price_data and price_data.get('usd'):
                    price_data['source'] = 'CoinPaprika'
                    modern_bot.set_cached_data('price', cache_key, price_data)
                    return price_data
                    
            elif api['name'] == 'Binance':
                price_data = await get_binance_price(symbol)
                if price_data and price_data.get('usd'):
                    price_data['source'] = 'Binance'
                    modern_bot.set_cached_data('price', cache_key, price_data)
                    return price_data
                    
        except Exception as e:
            print(f"Error with {api['name']}: {e}")
            continue
    
    # Fallback أخير
    price_data = await get_fallback_price(symbol)
    if price_data:
        price_data['source'] = 'Fallback'
        modern_bot.set_cached_data('price', cache_key, price_data)
        return price_data
    
    return None

async def get_coingecko_price(coin_id):
    """الحصول على السعر من CoinGecko"""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd',
                'include_24hr_change': 'true'
            }
            async with session.get(url, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get(coin_id, {})
    except:
        return None

async def get_coinpaprika_price(coin_id):
    """الحصول على السعر من CoinPaprika"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.coinpaprika.com/v1/tickers/{coin_id}"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'usd': data.get('quotes', {}).get('USD', {}).get('price', 0),
                        'usd_24h_change': data.get('quotes', {}).get('USD', {}).get('percent_change_24h', 0)
                    }
    except:
        return None

async def get_binance_price(symbol):
    """الحصول على السعر من Binance"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
            async with session.get(url, timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'usd': float(data.get('price', 0)),
                        'usd_24h_change': 0  # Binance لا يعطي تغير 24h في هذا endpoint
                    }
    except:
        return None

async def get_fallback_price(symbol):
    """Fallback API كحل أخير"""
    try:
        # استخدام CryptoCompare كبديل
        async with aiohttp.ClientSession() as session:
            url = f"https://min-api.cryptocompare.com/data/price?fsym={symbol}&tsyms=USD"
            async with session.get(url, timeout=3) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'usd': data.get('USD', 0),
                        'usd_24h_change': 0
                    }
    except:
        return None

def extract_price_request(text):
    """استخراج طلب السعر"""
    text = text.strip().lower()
    
    patterns = [
        r'(\d+\.?\d*)\s*([a-zA-Z]+)',
        r'([a-zA-Z]+)\s*(\d+\.?\d*)',
        r'(\d+\.?\d*)([a-zA-Z]+)',
        r'([a-zA-Z]+)(\d+\.?\d*)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            for match in matches:
                if len(match) == 2:
                    amount_str, symbol = match
                    try:
                        amount = float(amount_str)
                        if amount > 0 and len(symbol) >= 2:
                            return amount, symbol.upper()
                    except ValueError:
                        continue
    return None, None

def is_price_request(text):
    """التحقق من طلب السعر"""
    if not text or text.startswith('/'):
        return False
    amount, symbol = extract_price_request(text)
    return amount is not None and symbol is not None

def find_best_match(search_results, symbol):
    """إيجاد أفضل تطابق"""
    symbol = symbol.upper()
    
    for coin in search_results:
        if coin.get('symbol', '').upper() == symbol:
            return coin
    
    for coin in search_results:
        if symbol in coin.get('symbol', '').upper():
            return coin
    
    for coin in search_results:
        if symbol in coin.get('name', '').upper():
            return coin
    
    return search_results[0] if search_results else None

# أمر البدء
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء البوت"""
    user = update.effective_user
    
    welcome_content = f"""
*مرحباً {user.first_name}!* 👋

{EMOJIS['rocket']} *بوت الأسعار المتقدم*
• {EMOJIS['chart']} *أسعار حية* - دقة عالية
{EMOJIS['fire']} **جرب الآن!**
"""
    
    keyboard = [
        [InlineKeyboardButton(f"{EMOJIS['money']} ابحث عن عملة", callback_data="get_price")],
        [InlineKeyboardButton(f"{EMOJIS['channel']} قناتنا", url=CHANNEL_LINK)],
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = modern_bot.create_modern_message("بدء الاستخدام", welcome_content, EMOJIS["rocket"])
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

# معالجة الرسائل
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة جميع الرسائل"""
    
    message_text = update.message.text
    
    if not message_text or message_text.startswith('/'):
        return
    
    if is_price_request(message_text):
        amount, coin_symbol = extract_price_request(message_text)
        
        if amount and coin_symbol:
            # رسالة تحميل عصرية
            loading_message = modern_bot.create_modern_message(
                "جاري البحث",
                f"{EMOJIS['search']} **جاري البحث عن {coin_symbol}**\n\n"
                f"{EMOJIS['speed']} **نظام متعدد المصادر يعمل...**\n"
                f"{EMOJIS['database']} **جاري التحقق من الكاش**",
                EMOJIS["search"]
            )
            loading_msg = await update.message.reply_text(loading_message, parse_mode='Markdown')
            
            try:
                # البحث عن العملة باستخدام multiple APIs
                search_results = await search_coins_multiple(coin_symbol)
                
                if search_results:
                    best_match = find_best_match(search_results, coin_symbol)
                    
                    if best_match:
                        coin_id = best_match['id']
                        
                        # الحصول على السعر مع fallbacks متعددة
                        price_data = await get_coin_price_multiple(coin_id, coin_symbol)
                        
                        if price_data and price_data.get('usd'):
                            source = price_data.get('source', 'Unknown')
                            
                            # عرض السعر بتصميم عصري
                            price_message = modern_bot.create_price_card(amount, coin_symbol, best_match, price_data, source)
                            
                            # أزرار عصرية
                            keyboard = [
                                [InlineKeyboardButton(f"{EMOJIS['money']} بحث عن عملة", callback_data="get_price")],
                                [InlineKeyboardButton(f"{EMOJIS['channel']} قناتنا", url=CHANNEL_LINK)],
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            
                            await loading_msg.edit_text(price_message, reply_markup=reply_markup, parse_mode='Markdown')
                            
                        else:
                            error_message = modern_bot.create_modern_message(
                                "خطأ في السعر",
                                f"{EMOJIS['error']} **لم أتمكن من الحصول على سعر {coin_symbol}**\n\n"
                                f"{EMOJIS['warning']} **جرب عملة أخرى مثل:**\n"
                                f"• `BTC` - البيتكوين\n"
                                f"• `ETH` - الإيثيريوم\n"
                                f"• `SOL` - السولانا\n"
                                f"• `TON` - التون",
                                EMOJIS["error"]
                            )
                            await loading_msg.edit_text(error_message, parse_mode='Markdown')
                    else:
                        error_message = modern_bot.create_modern_message(
                            "عملة غير معروفة",
                            f"{EMOJIS['error']} **لم أتعرف على العملة {coin_symbol}**\n\n"
                            f"{EMOJIS['warning']} **تأكد من كتابة الرمز الصحيح**",
                            EMOJIS["error"]
                        )
                        await loading_msg.edit_text(error_message, parse_mode='Markdown')
                else:
                    error_message = modern_bot.create_modern_message(
                        "لا توجد نتائج",
                        f"{EMOJIS['error']} **لم أجد أي عملة باسم {coin_symbol}**\n\n"
                        f"{EMOJIS['warning']} **جرب هذه العملات:**\n"
                        f"• `BTC` - البيتكوين\n"
                        f"• `ETH` - الإيثيريوم\n"
                        f"• `SOL` - السولانا\n"
                        f"• `TON` - التون",
                        EMOJIS["error"]
                    )
                    await loading_msg.edit_text(error_message, parse_mode='Markdown')
                    
            except Exception as e:
                print(f"Unexpected error: {e}")
                error_message = modern_bot.create_modern_message(
                    "خطأ غير متوقع",
                    f"{EMOJIS['error']} **حدث خطأ غير متوقع**\n\n"
                    f"{EMOJIS['warning']} **جرب مرة أخرى أو استخدم عملة أخرى**",
                    EMOJIS["error"]
                )
                await loading_msg.edit_text(error_message, parse_mode='Markdown')

# معالجة الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الضغط على الأزرار"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "get_price":
        price_instructions = modern_bot.create_modern_message(
            "كيفية البحث عن عملة...",
            f"{EMOJIS['money']} **اكتب الكمية واسم العملة:**\n\n"
            f"```\n"
            f"1 BTC \n"
            f"5 TON \n"
            f"```\n\n"
            f" *يدعم جميع العملات الرقمية*\n"
            f" *متعدد المصادر*\n"
            f" *نظام كاش متقدم*",
        )
        
        keyboard = [
            [InlineKeyboardButton(f"{EMOJIS['channel']} قناتنا", url=CHANNEL_LINK)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(price_instructions, reply_markup=reply_markup, parse_mode='Markdown')

# الوظيفة الرئيسية
def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_all_messages
    ))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🚀 البوت المتقدم يعمل الآن!")
    print("🔄 نظام متعدد APIs مع fallbacks تلقائية")
    print("💾 نظام caching متقدم لتسريع الاستجابة")
    print("⚡ أداء محسن وموثوقية عالية")
    print("🎯 تصميم عصري مع إمكانيات متطورة")
    
    application.run_polling()

if __name__ == '__main__':
    main()