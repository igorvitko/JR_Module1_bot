from telegram import Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes

from gpt import ChatGptService
from util import (load_message, send_text, send_image, show_main_menu, load_prompt,
                  default_callback_handler)

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
    prompt = load_prompt('random')
    text = load_message('random')
    chat_gpt.set_prompt(prompt)

    await send_image(update, context, 'random')

    message = await update.message.reply_text("Зачекайте, я шукаю інформацію ...")
    fact = chat_gpt.send_message_list()
    response = f"{text}\n{fact}"

    await message.edit_text(response)


chat_gpt = ChatGptService(config.ChatGPT_TOKEN)
app = ApplicationBuilder().token(config.BOT_TOKEN).build()

# Зареєструвати обробник команди можна так:
app.add_handler(CommandHandler('start', start))
app.add_handler(CommandHandler('random', random))

# Зареєструвати обробник колбеку можна так:
# app.add_handler(CallbackQueryHandler(app_button, pattern='^app_.*'))
# app.add_handler(CallbackQueryHandler(default_callback_handler))
print("Бот запущено...")
app.run_polling()
