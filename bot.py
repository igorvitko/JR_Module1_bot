import logging
import os
import tempfile
from logging.handlers import RotatingFileHandler

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
)

from gpt import ChatGptService
from util import (
    get_ai_service,
    load_message,
    send_text,
    send_text_buttons,
    send_image,
    show_main_menu,
    load_prompt,
    send_random_fact,
    get_mode,
    set_mode,
)
from setting import config

# ---------------------------------------------------------------------------
# Логування (консоль + файл з ротацією)
# ---------------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

file_handler = RotatingFileHandler(
    filename="logs/bot.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

logging.basicConfig(level=logging.INFO, handlers=[
                    file_handler, console_handler])

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Режими (замість станів ConversationHandler)
# При використанні ConversationHandler дуже складно підтримувати кілька
# режимів одночасно (наприклад, gpt-чат і квіз). Якщо користувач починає квіз,
# а потім запускає чат — то він вже не зможе відповісти на питання квізу,
# бо бот буде чекати повідомлення для чату. Тому просто зберігаємо поточний режим
# в context.user_data["mode"] і дивимося на нього в роутері.
# ---------------------------------------------------------------------------

MODE_GPT = "gpt"
MODE_TALK = "talk"
MODE_QUIZ_ANSWER = "quiz_answer"
MODE_VOICE = "voice"
MODE_RECOMMEND = "recommend"

# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Команда /start — користувач: %s (id=%s)",
                user.username or user.first_name, user.id)
    context.user_data.clear()
    await send_image(update, context, "main")
    await send_text(update, context, load_message("main"))
    await show_main_menu(update, context, {
        "start": "Головне меню",
        "random": "Випадковий факт 🧠",
        "gpt": "Чат з GPT 🤖",
        "talk": "Поговорити з особистістю 👤",
        "quiz": "Квіз ❓",
        "voice": "Голосовий GPT 🎙",
        "recommend": "Рекомендації 🎬📚",
    })

    context.user_data["ai_service"] = ChatGptService()

# ---------------------------------------------------------------------------
# /random
# ---------------------------------------------------------------------------


async def random_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_mode(context, None, logger)
    chat_gpt = get_ai_service(context)
    await send_image(update, context, "random")
    message = await update.message.reply_text("⏳")
    await send_random_fact(message, chat_gpt)


async def button_handler_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_gpt = get_ai_service(context)
    await query.answer()
    if query.data == "random":
        await send_random_fact(query.message, chat_gpt)
    elif query.data == "start":
        await start(update, context)


# ---------------------------------------------------------------------------
# /gpt
# ---------------------------------------------------------------------------

async def gpt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_gpt = get_ai_service(context)
    logger.info("Команда /gpt — користувач: %s (id=%s)",
                user.username or user.first_name, user.id)
    chat_gpt.set_prompt(load_prompt("gpt"))
    set_mode(context, MODE_GPT, logger)
    await send_image(update, context, "gpt")
    await send_text(update, context, load_message("gpt"))


async def gpt_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_gpt = get_ai_service(context)
    logger.info("GPT-повідомлення від id=%s: %s",
                update.effective_user.id, user_text[:80])
    message = await update.message.reply_text("⏳ Думаю...")
    answer = await chat_gpt.add_message(user_text)
    keyboard = [[InlineKeyboardButton("Закінчити", callback_data="gpt_end")]]
    await message.edit_text(answer, reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------------------------------------------------------------------
# /talk
# ---------------------------------------------------------------------------

PERSONALITIES = {
    "talk_cobain": "Курт Кобейн",
    "talk_queen": " Єлизавета II",
    "talk_tolkien": "Джон Толкін",
    "talk_nietzsche": "Фрідріх Ніцше",
    "talk_hawking": "Стівен Гокінг",
}


async def talk_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Команда /talk — користувач: %s (id=%s)",
                user.username or user.first_name, user.id)
    set_mode(context, None, logger)
    await send_image(update, context, "talk")
    await send_text_buttons(update, context, load_message("talk"), PERSONALITIES)


async def talk_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_gpt = get_ai_service(context)
    await query.answer()

    if query.data not in PERSONALITIES:
        return

    name = PERSONALITIES[query.data]
    logger.info("Обрана особистість: %s — id=%s", name, query.from_user.id)
    chat_gpt.set_prompt(load_prompt(query.data))
    set_mode(context, MODE_TALK, logger)

    await query.message.reply_text(
        f"Вітаю! Тепер ти розмовляєш з *{name}*. Напиши щось!",
        parse_mode="Markdown",
    )


async def talk_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_gpt = get_ai_service(context)
    await update.message.reply_text("⏳")
    answer = await chat_gpt.add_message(user_text)
    keyboard = [[InlineKeyboardButton("Закінчити", callback_data="talk_end")]]
    await update.message.reply_text(
        answer, reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------------------------------------------------------------------
# /quiz
# ---------------------------------------------------------------------------

QUIZ_TOPICS = {
    "quiz_prog": "🐍 Python",
    "quiz_math": "📐 Математика",
    "quiz_biology": "🧬 Біологія",
}


async def quiz_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Команда /quiz — користувач: %s (id=%s)",
                user.username or user.first_name, user.id)
    context.user_data["quiz_score"] = 0
    context.user_data["quiz_total"] = 0
    set_mode(context, None, logger)
    await send_image(update, context, "quiz")
    await send_text_buttons(update, context, load_message("quiz"), QUIZ_TOPICS)


async def quiz_choose_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "quiz_next":
        topic = context.user_data.get("quiz_topic")
        prompt_keyword = "quiz_more"
    elif query.data == "quiz_change":
        set_mode(context, None, logger)
        await send_text_buttons(update, context, "Обери тему:", QUIZ_TOPICS)
        return
    elif query.data in QUIZ_TOPICS:
        topic = query.data
        context.user_data["quiz_topic"] = topic
        prompt_keyword = topic  # "quiz_prog", "quiz_math" або "quiz_biology"
    else:
        return

    chat_gpt = get_ai_service(context)

    prompt = load_prompt("quiz")
    if prompt_keyword == "quiz_more":
        question = await chat_gpt.add_message("quiz_more")
    else:
        question = await chat_gpt.send_question(prompt, prompt_keyword)
    score = context.user_data["quiz_score"]
    total = context.user_data["quiz_total"]
    set_mode(context, MODE_QUIZ_ANSWER, logger)
    await query.message.reply_text(f"📊 Рахунок: {score}/{total}\n\n{question}")


async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_answer = update.message.text
    chat_gpt = get_ai_service(context)

    result = await chat_gpt.add_message(user_answer)

    context.user_data["quiz_total"] += 1
    if "Правильно!" in result:
        context.user_data["quiz_score"] += 1
        logger.info("Квіз: правильна відповідь від id=%s. Рахунок %s/%s",
                    update.effective_user.id,
                    context.user_data["quiz_score"],
                    context.user_data["quiz_total"])
    else:
        logger.info("Квіз: неправильна відповідь від id=%s. Рахунок %s/%s",
                    update.effective_user.id,
                    context.user_data["quiz_score"],
                    context.user_data["quiz_total"])

    score = context.user_data["quiz_score"]
    total = context.user_data["quiz_total"]
    set_mode(context, None, logger)
    keyboard = [
        [
            InlineKeyboardButton("Ще питання", callback_data="quiz_next"),
            InlineKeyboardButton("Змінити тему", callback_data="quiz_change"),
        ],
        [InlineKeyboardButton("Закінчити", callback_data="start")],
    ]
    await update.message.reply_text(
        f"{result}\n\n📊 Рахунок: {score}/{total}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ---------------------------------------------------------------------------
# /voice
# ---------------------------------------------------------------------------


async def voice_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Команда /voice — користувач: %s (id=%s)",
                user.username or user.first_name, user.id)
    chat_gpt = get_ai_service(context)

    chat_gpt.set_prompt(load_prompt("gpt"))
    set_mode(context, MODE_VOICE, logger)
    await send_image(update, context, "voice")
    await send_text(update, context, load_message("voice"))


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Голосове повідомлення від id=%s", update.effective_user.id)
    voice = update.message.voice
    voice_file = await context.bot.get_file(voice.file_id)
    chat_gpt = get_ai_service(context)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
    await voice_file.download_to_drive(tmp_path)

    with open(tmp_path, "rb") as audio:
        transcript = await chat_gpt.client.audio.transcriptions.create(
            model="whisper-1", file=audio
        )
    os.unlink(tmp_path)

    user_text = transcript.text
    logger.info("Whisper транскрипція: '%s' (id=%s)",
                user_text[:80], update.effective_user.id)
    await update.message.reply_text(f"🗣 Ти сказав: _{user_text}_", parse_mode="Markdown")

    answer = await chat_gpt.add_message(user_text)

    tts_response = await chat_gpt.client.audio.speech.create(
        model="tts-1", voice="nova", input=answer
    )
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
        tmp_audio_path = tmp_audio.name
        tmp_audio.write(tts_response.content)

    with open(tmp_audio_path, "rb") as audio_out:
        await update.message.reply_voice(voice=audio_out)
    os.unlink(tmp_audio_path)


# ---------------------------------------------------------------------------
# /recommend
# ---------------------------------------------------------------------------

RECOMMEND_CATEGORIES = {
    "rec_movies": "🎬 Фільми",
    "rec_books": "📚 Книги",
    "rec_music": "🎵 Музика",
}


async def recommend_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Команда /recommend — користувач: %s (id=%s)",
                user.username or user.first_name, user.id)
    context.user_data["rec_dislikes"] = []
    set_mode(context, None, logger)
    await send_image(update, context, "recommend")
    await send_text_buttons(
        update, context, load_message("recommend"), RECOMMEND_CATEGORIES
    )


async def recommend_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "rec_dislike":
        last = context.user_data.get("rec_last", "")
        if last:
            context.user_data["rec_dislikes"].append(last)
        await _send_recommendation(query.message, context)
        return

    if query.data in RECOMMEND_CATEGORIES:
        context.user_data["rec_category"] = query.data
        cat_name = RECOMMEND_CATEGORIES[query.data]
        set_mode(context, MODE_RECOMMEND, logger)
        await query.message.reply_text(
            f"Обрано: {cat_name}\nНапиши жанр або тематику:"
        )


async def recommend_genre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["rec_genre"] = update.message.text
    await update.message.reply_text("⏳ Шукаю рекомендацію...")
    set_mode(context, None, logger)
    await _send_recommendation(update.message, context)


async def _send_recommendation(message, context: ContextTypes.DEFAULT_TYPE):
    cat_key = context.user_data.get("rec_category", "rec_movies")
    cat_name = RECOMMEND_CATEGORIES.get(cat_key, "фільми")
    genre = context.user_data.get("rec_genre", "будь-який")
    dislikes = context.user_data.get("rec_dislikes", [])
    prompt = load_prompt("recommend")
    exclude = f" Виключи: {', '.join(dislikes)}." if dislikes else ""

    chat_gpt = get_ai_service(context)

    question = (
        f"""Порадь три {cat_name} у жанрі '{genre}'.{exclude} 
        Виведи список з назв та коротких описів (2-3 речення).
        """
    )
    answer = await chat_gpt.send_question(prompt, question)
    context.user_data["rec_last"] = answer
    keyboard = [
        [
            InlineKeyboardButton("👎 Не подобається",
                                 callback_data="rec_dislike"),
            InlineKeyboardButton("Закінчити", callback_data="start"),
        ]
    ]
    await message.reply_text(answer, reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------------------------------------------------------------------
# Роутери — єдині точки входу для повідомлень і кнопок
# ---------------------------------------------------------------------------

async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Єдина точка входу для всіх текстових повідомлень.
    Дивиться на context.user_data["mode"] і вирішує куди відправити.
    """
    mode = get_mode(context)
    logger.info("router: mode=%s, user id=%s", mode, update.effective_user.id)

    if mode == MODE_GPT:
        await gpt_dialog(update, context)
    elif mode == MODE_TALK:
        await talk_dialog(update, context)
    elif mode == MODE_QUIZ_ANSWER:
        await quiz_answer(update, context)
    elif mode == MODE_RECOMMEND:
        await recommend_genre(update, context)
    # якщо mode == None — нічого не робимо, чекаємо команди


async def voice_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Роутер для голосових повідомлень."""
    if get_mode(context) == MODE_VOICE:
        await voice_message(update, context)


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Єдина точка входу для всіх callback-кнопок."""
    query = update.callback_query
    data = query.data

    if data == "start":
        await query.answer()
        await start(update, context)
    elif data == "random":
        await button_handler_random(update, context)

    elif data == "gpt_end":
        await query.answer()
        set_mode(context, None, logger)
        await start(update, context)

    elif data == "talk_end":
        await query.answer()
        set_mode(context, None, logger)
        await start(update, context)
    elif data in PERSONALITIES:
        await talk_choose(update, context)
    elif data in QUIZ_TOPICS or data in ("quiz_next", "quiz_change"):
        await quiz_choose_topic(update, context)
    elif data in RECOMMEND_CATEGORIES or data == "rec_dislike":
        await recommend_choose(update, context)
    else:
        await query.answer()


# ---------------------------------------------------------------------------
# Ініціалізація бота
# ---------------------------------------------------------------------------

app = (
    ApplicationBuilder()
    .token(config.BOT_TOKEN)
    .concurrent_updates(True)
    .persistence(PicklePersistence(filepath="user_data.pkl"))
    .build())

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("random", random_fact))
app.add_handler(CommandHandler("gpt", gpt_start))
app.add_handler(CommandHandler("talk", talk_start))
app.add_handler(CommandHandler("quiz", quiz_start))
app.add_handler(CommandHandler("voice", voice_start))
app.add_handler(CommandHandler("recommend", recommend_start))

app.add_handler(CallbackQueryHandler(callback_router))
app.add_handler(MessageHandler(filters.VOICE, voice_router))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))

logger.info("Бот запущено...")
app.run_polling()
