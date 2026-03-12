
import logging


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CallbackQueryHandler, CommandHandler,
                          ContextTypes, ConversationHandler, MessageHandler,
                          TypeHandler, filters)

from gpt import ChatGptService
from util import (load_message, send_text, send_image, show_main_menu, load_prompt,
                  default_callback_handler, send_random_fact, send_text_buttons)

from setting import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
# logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

GPT_DIALOG = 1

TALK_CHOOSE = 10
TALK_DIALOG = 11


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Команда /start — користувач: %s (id=%s)",
                user.username or user.first_name, user.id)
    context.user_data.clear()
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
    return ConversationHandler.END


async def random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /random — користувач: %s (id=%s)",
                update.effective_user.username or update.effective_user.first_name,
                update.effective_user.id)

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


async def gpt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /gpt — користувач: %s (id=%s)",
                update.effective_user.username or update.effective_user.first_name, update.effective_user.id)
    prompt = load_prompt("gpt")
    chat_gpt.set_prompt(prompt)
    await send_image(update, context, "gpt")
    await send_text(update, context, load_message("gpt"))
    return GPT_DIALOG


async def gpt_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    logger.info("GPT-повідомлення від %s: %s",
                update.effective_user.id, user_text[:80])
    await update.message.reply_text("⏳ Думаю...")
    answer = await chat_gpt.add_message(user_text)
    await send_text(update, context, answer)
    return GPT_DIALOG


PERSONALITIES = {
    "talk_cobain": "Курт Кобейн",
    "talk_queen": " Єлизавета II",
    "talk_tolkien": "Джон Толкін",
    "talk_nietzsche": "Фрідріх Ніцше",
    "talk_hawking": "Стівен Гокінг",
}


async def talk_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Команда /talk — користувач: %s (id=%s)",
                update.effective_user.username or update.effective_user.first_name, update.effective_user.id)
    await send_image(update, context, "talk")
    await send_text_buttons(update, context, load_message("talk"), PERSONALITIES)
    return TALK_CHOOSE


async def talk_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "start":
        await start(update, context)
        return ConversationHandler.END

    if query.data not in PERSONALITIES:
        return TALK_CHOOSE

    name = PERSONALITIES[query.data]
    logger.info("Обрана особистість: %s — користувач id=%s",
                name, query.from_user.id)
    prompt = load_prompt(query.data)
    chat_gpt.set_prompt(prompt)

    await query.message.reply_text(
        f"Вітаю! Тепер ти розмовляєш з *{name}*. Напиши щось!",
        parse_mode="Markdown",
    )
    return TALK_DIALOG


async def talk_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text("⏳")
    answer = await chat_gpt.add_message(user_text)

    keyboard = [[InlineKeyboardButton("Закінчити", callback_data="start")]]
    await update.message.reply_text(
        answer, reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TALK_DIALOG


async def talk_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start(update, context)
    return ConversationHandler.END


async def cancel_to_gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Перехід до /gpt під час іншого діалогу (id=%s)",
                update.effective_user.id)
    return await gpt_start(update, context)


async def cancel_to_talk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Перехід до /talk під час іншого діалогу (id=%s)",
                update.effective_user.id)
    return await talk_start(update, context)


async def cancel_to_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Перехід до /quiz під час іншого діалогу (id=%s)",
                update.effective_user.id)
    return await quiz_start(update, context)


COMMON_FALLBACKS = [
    CommandHandler("start", start),
    CommandHandler("gpt", cancel_to_gpt),
    CommandHandler("talk", cancel_to_talk),
    CommandHandler("quiz", cancel_to_quiz),
]


# async def log_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     print(f"=== Апдейт отримано: {type(update)} ===")
#     print(update)

chat_gpt = ChatGptService(config.ChatGPT_TOKEN)
app = ApplicationBuilder().token(config.BOT_TOKEN).build()

# app.add_handler(TypeHandler(Update, log_all), group=-1)

# Зареєструвати обробник команди можна так:
app.add_handler(CommandHandler('random', random))
app.add_handler(CallbackQueryHandler(
    button_handler_random, pattern='^(random|start)$'))

gpt_handler = ConversationHandler(
    entry_points=[CommandHandler("gpt", gpt_start)],
    states={GPT_DIALOG: [MessageHandler(
        filters.TEXT & ~filters.COMMAND, gpt_dialog)]},
    fallbacks=COMMON_FALLBACKS,
    per_message=False,
)
app.add_handler(gpt_handler)

talk_handler = ConversationHandler(
    entry_points=[CommandHandler("talk", talk_start)],
    states={
        TALK_CHOOSE: [CallbackQueryHandler(talk_choose)],
        TALK_DIALOG: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, talk_dialog),
            CallbackQueryHandler(talk_end, pattern="^start$"),
        ],
    },
    fallbacks=COMMON_FALLBACKS,
    per_message=False,
)
app.add_handler(talk_handler)


app.add_handler(CommandHandler('start', start))

# Зареєструвати обробник колбеку можна так:
# app.add_handler(CallbackQueryHandler(app_button, pattern='^app_.*'))
# app.add_handler(CallbackQueryHandler(default_callback_handler))

print("Бот запущено...")
app.run_polling()
