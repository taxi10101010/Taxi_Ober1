import sqlite3
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# --- إعداد التسجيل (Logging) ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "8806683255:AAFQR0g5dfbnf8vaEDPm8MvFzCse06z6fvs"
WEBAPP_URL = "https://ga1trading1-del.github.io/Taxi_ober_geloka/index.html"

# --- بيانات سيرفر Traccar الخاص بك على Railway ---
TRACCAR_URL = "https://traccar-production-822f.up.railway.app"
TRACCAR_USER = "ga1trading1@gmail.com"
TRACCAR_PASS = "1GALAL1galal"

active_sessions = {}
driver_reply_sessions = {}

# --- التعامل مع قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect("drivers.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drivers (
            traccar_id TEXT PRIMARY KEY,
            telegram_id INTEGER NOT NULL,
            username TEXT,
            driver_name TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_driver(traccar_id, telegram_id, username, driver_name="تكسي1"):
    conn = sqlite3.connect("drivers.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO drivers (traccar_id, telegram_id, username, driver_name)
        VALUES (?, ?, ?, ?)
    """, (traccar_id, telegram_id, username, driver_name))
    conn.commit()
    conn.close()

def get_all_drivers():
    conn = sqlite3.connect("drivers.db")
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, driver_name, traccar_id FROM drivers")
    results = cursor.fetchall()
    conn.close()
    return results

# --- الأوامر والرسائل الخاصة بـ Telegram ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🗺️ فتح الخريطة واختيار تاكسي", web_app=WebAppInfo(url=WEBAPP_URL))]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "🚖 **أهلاً بك في خدمة التاكسي!**\n\n"
        "اضغط على الزر أدناه لفتح الخريطة التفاعلية واختيار أقرب تاكسي لك مباشر من الخريطة 👇",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def register_driver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "بدون اسم مستخدم"
    args = context.args

    if not args:
        await update.message.reply_text("⚠️ يرجى استخدام الأمر بالشكل الصحيح:\n`/register_driver 79259172 تكسي1`", parse_mode="Markdown")
        return

    traccar_id = args[0]
    driver_name = args[1] if len(args) > 1 else "تكسي1"
    
    add_driver(traccar_id, user_id, username, driver_name)

    await update.message.reply_text(
        f"✅ **تم تسجيلك كسائق بنجاح!**\n\n"
        f"🚕 اسم التاكسي: `{driver_name}`\n"
        f"🆔 معرف Traccar: `{traccar_id}`\n"
        f"📱 Telegram ID: `{user_id}`",
        parse_mode="Markdown"
    )

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    selected_driver_name = update.effective_message.web_app_data.data
    customer_name = update.effective_user.first_name or "زبون"
    customer_username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون اسم مستخدم"

    drivers = get_all_drivers()
    selected_driver_id = None

    for telegram_id, driver_name, traccar_id in drivers:
        if driver_name == selected_driver_name or driver_name in selected_driver_name:
            selected_driver_id = telegram_id
            break

    if selected_driver_id:
        active_sessions[user_id] = (selected_driver_id, selected_driver_name)
        driver_reply_sessions[selected_driver_id] = user_id

        await update.message.reply_text(
            f"✅ **تم اختيار التاكسي ({selected_driver_name}) بنجاح من الخريطة!**\n\n"
            f"اكتب رسالتك الآن أو أرسل موقعك الجغرافي وسيصل للسائق مباشرة.",
            parse_mode="Markdown"
        )

        try:
            await context.bot.send_message(
                chat_id=selected_driver_id,
                text=f"🚨 **زبون جديد اختارك من الخريطة!**\n\n"
                     f"👤 الزبون: {customer_name} ({customer_username})\n"
                     f"💬 يمكنك الرد عليه مباشرة عبر كتابة أي رسالة هنا.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"خطأ إشعار السائق: {e}")
    else:
        await update.message.reply_text(
            f"⚠️ التاكسي المختار (`{selected_driver_name}`) غير مسجل حساب تليجرام له حالياً لتلقي الرسائل.",
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    customer_name = update.effective_user.first_name or "زبون"
    customer_username = f"@{update.effective_user.username}" if update.effective_user.username else "بدون اسم مستخدم"

    drivers = get_all_drivers()
    driver_ids = [d[0] for d in drivers]

    if user_id in driver_ids:
        if user_id in driver_reply_sessions:
            target_customer_id = driver_reply_sessions[user_id]
            try:
                await context.bot.send_message(
                    chat_id=target_customer_id,
                    text=f"🚖 **رسالة من السائق:**\n{user_text}"
                )
                await update.message.reply_text("✅ تم إرسال الرد للزبون بنجاح!")
            except Exception:
                await update.message.reply_text("⚠️ تعذر إرسال الرسالة للزبون.")
        else:
            await update.message.reply_text("ℹ️ أنت مسجل كسائق. بانتظار طلبات الزبائن.")
        return

    selected_driver_id = None
    selected_driver_name = None

    for telegram_id, driver_name, traccar_id in drivers:
        if driver_name in user_text:
            active_sessions[user_id] = (telegram_id, driver_name)
            selected_driver_id = telegram_id
            selected_driver_name = driver_name
            break

    if not selected_driver_id and user_id in active_sessions:
        selected_driver_id, selected_driver_name = active_sessions[user_id]

    if selected_driver_id:
        driver_reply_sessions[selected_driver_id] = user_id
        try:
            await context.bot.send_message(
                chat_id=selected_driver_id,
                text=f"🚨 **رسالة من الزبون ({customer_name})!**\n\n"
                     f"💬 النص: {user_text}\n"
                     f"👤 الحساب: {customer_username}",
                parse_mode="Markdown"
            )
            await update.message.reply_text(f"✅ تم توجيه رسالتك إلى ({selected_driver_name})!")
        except Exception:
            await update.message.reply_text("⚠️ تعذر الوصول للسائق.")
    else:
        await update.message.reply_text("⚠️ يرجى فتح الخريطة واختيار تاكسي أو كتابة اسمه أولاً.")

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    user_id = update.effective_user.id
    customer_name = update.effective_user.first_name or "زبون"

    if user_id in active_sessions:
        driver_id, driver_name = active_sessions[user_id]
        driver_reply_sessions[driver_id] = user_id
        try:
            await context.bot.send_message(
                chat_id=driver_id,
                text=f"📍 **وصل موقع جغرافي من الزبون ({customer_name})!**",
                parse_mode="Markdown"
            )
            await context.bot.send_location(
                chat_id=driver_id,
                latitude=location.latitude,
                longitude=location.longitude
            )
            await update.message.reply_text(f"✅ تم إرسال موقعك للسائق ({driver_name}) بنجاح!")
        except Exception as e:
            logging.error(f"خطأ: {e}")

def main():
    init_db()
    
    bot_app = ApplicationBuilder().token(TOKEN).build()

    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("register_driver", register_driver))
    bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    bot_app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    bot_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🚀 البوت يعمل بنجاح...")
    bot_app.run_polling()

if __name__ == "__main__":
    main()
