from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, TypeHandler

from gpt import ChatGptService
from util import (load_message, send_text, send_image, show_main_menu, load_prompt,
                  default_callback_handler, send_random_fact)

from setting import config


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = load_message('main')
    await send_image(update, context, 'main')
    await send_text(update, context, text)
    await show_main_menu(update, context, {
        'start': 'Головне меню',
        'random': 'Дізнатися випадковий цікавий факт 🧠',
        'gpt': 'Задати питання чату GPT 🤖',
        'talk': 'Поговорити з відомою особистістю 👤',
        'quiz': 'Взяти участь у квізі ❓'
        # Додати команду в меню можна так:
        # 'command': 'button text'

    })


async def random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_image(update, context, 'random')
    message = await update.message.reply_text("⏳")
    await send_random_fact(message, chat_gpt)


async def button_handler_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "random":
        await send_random_fact(query.message, chat_gpt)
    elif query.data == "start":
        await start(update, context)


async def log_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"=== Апдейт отримано: {type(update)} ===")
    print(update)


chat_gpt = ChatGptService(config.ChatGPT_TOKEN)
app = ApplicationBuilder().token(config.BOT_TOKEN).build()

# app.add_handler(TypeHandler(Update, log_all), group=-1)

# Зареєструвати обробник команди можна так:
app.add_handler(CommandHandler('start', start))
app.add_handler(CommandHandler('random', random))

app.add_handler(CallbackQueryHandler(button_handler_random))

# Зареєструвати обробник колбеку можна так:
# app.add_handler(CallbackQueryHandler(app_button, pattern='^app_.*'))
# app.add_handler(CallbackQueryHandler(default_callback_handler))

print("Бот запущено...")
app.run_polling()
