from src.imports import *
from handlers.sharing_quiz import *
from src.user_management import *
import traceback
from handlers.group_sharing import *
from handlers.subscribe import *
from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode

from src.user_management import (
    get_user_profile, touch_user_activity, check_user_exists, create_new_user,
    get_user_language, get_total_users, get_total_processed_files,
    get_todays_active_users, get_total_groups, get_success_rate,
)
from src.async_utils import fire_and_forget
from src.perf_timing import track_handler


import asyncio


async def _typing(context, chat_id):
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception:
        pass

async def back_to_main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle back to main menu button press."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    
    await show_main_menu_with_welcome(update, context, user, language or "en")
    return CONTENT


MAIN_MENU_TRANSLATIONS = {
    "en": {
        "welcome_message": "🔥 *Welcome {name}!*\n\nI'm here to help you create amazing quizzes quickly and easily.\n Send me text, pdf, word, txt, or a URL and I'll turn it into an engaging quiz for you!",
        "send_document": (
            "📤 <b>Ready to Create Your Quiz!</b>\n\n"
            "Send me any content and I'll turn it into a quiz!\n\n"
            "<b>What you can send:</b>\n"
            "• 📄 Document (PDF, Word, TXT)\n"
            "• 🔗 A URL / website link\n"
            "• 🖼 A picture or image\n"
            "• 💭 Plain text\n\n"
            "<b>💡 For best results, be specific:</b>\n"
            "• History: not <i>7 wonders</i> ❌ → <i>7 wonders of the ancient world</i> ✅\n"
            "• English: not <i>Grammar and vocabulary</i> ❌ → <i>Grammar and vocabulary A1 level Food topic</i> ✅\n"
            "• Science: not <i>Physics</i> ❌ → <i>Newton's 3 laws of motion with examples</i> ✅\n\n"
            "<b>The more specific you are, the better your quiz will be!</b> 🎯"
        ),
        "contest_message": "🌍 *Join our language learning challenge and find your perfect match in 30 seconds! Details: @lingomatch_bot*",

        "create_quiz": "🎯 Create Quiz",
        "split_quiz": "📂 Split Quiz Hemis",
        "settings": "⚙️ Settings",
        "help": "❓ Help",
        "balance": "💰 Balance",
        "share": "🔗 Share & Earn",
        "quiz_type_set": "✅ *Quiz type set to {quiz_type_name}*",
        "error_occurred": "❌ An error occurred. Please try again.",
                "my_quizzes": "📚 My Quizzes",
                "processing":"⏳ Processing your input. Please wait..."
    },
    "ru": {
        "welcome_message": "🔥 *Добро пожаловать {name}!*\n\nЯ помогу вам быстро и легко создавать викторины. \nОтправьте мне текст, PDF, Word, TXT или URL, и я превращу это в увлекательную викторину для вас!",
        "send_document": (
            "📤 <b>Готов создать ваш тест!</b>\n\n"
            "Отправьте мне любой контент — я превращу его в тест!\n\n"
            "<b>Что можно отправить:</b>\n"
            "• 📄 Документ (PDF, Word, TXT)\n"
            "• 🔗 Ссылку на сайт\n"
            "• 🖼 Картинку или изображение\n"
            "• 💭 Обычный текст\n\n"
            "<b>💡 Для лучшего результата будьте конкретны:</b>\n"
            "• История: не <i>7 чудес</i> ❌ → <i>7 чудес древнего мира</i> ✅\n"
            "• Английский: не <i>Грамматика и лексика</i> ❌ → <i>Грамматика и лексика уровень A1 тема Еда</i> ✅\n"
            "• Наука: не <i>Физика</i> ❌ → <i>3 закона Ньютона с примерами</i> ✅\n\n"
            "<b>Чем точнее запрос — тем лучше тест!</b> 🎯"
        ),
        "contest_message": "🌍 *Присоединяйтесь к нашему челленджу по изучению языков и найдите идеального партнера за 30 секунд! Подробности: @lingomatch_bot*",

        "create_quiz": "🎯 Создать викторину",
        "split_quiz": "📂 Разделить квиз Hemis",
        "settings": "⚙️ Настройки",
        "help": "❓ Помощь",
        "balance": "💰 Баланс",
        "share": "🔗 Пригласить и заработать",
        "quiz_type_set": "✅ *Тип викторины установлен: {quiz_type_name}*",
        "error_occurred": "❌ Произошла ошибка. Попробуйте снова.",
        "my_quizzes": "📚 Мои Викторины",
        "processing":"⏳ Обрабатываю ваш запрос. Пожалуйста, подождите..."
    },
    "uz": {
        "welcome_message": "🔥 *Xush kelibsiz {name}!*\n\nMen sizga tez va oson quizlar yaratishda yordam beraman. \n\nSun'iy intellekt bilan istalgan mavzuda quiz tuzish uchun - 🎯 Quiz yaratish\n\n Yakuniy yoki Hemis testlaringizni bo'lish uchun - 📂 Hemis quizni bo'lish tugmasini bosing.\n\n💡Bizning yangi botimiz siz uchun sekundlarda maxsus presentatsiyalar yaratib beradi: @SimplePresentation\\_maker\\_bot",
        "send_document": (
            "📤 <b>Testingizni yaratishga tayyorman!</b>\n\n"
            "Menga istalgan kontent yuboring — men uni testga aylantirib beraman!\n\n"
            "<b>Nima yuborish mumkin:</b>\n"
            "• 📄 Hujjat (PDF, Word, TXT)\n"
            "• 🔗 Havola yoki veb-sayt\n"
            "• 🖼 Rasm yoki fotosurat\n"
            "• 💭 Oddiy matn\n\n"
            "<b>💡 Yaxshi natija uchun aniq yozing:</b>\n"
            "• Tarix: <i>7 mo'jiza</i> emas ❌ → <i>Qadimgi dunyoning 7 mo'jizasi</i> ✅\n"
            "• Ingliz tili: <i>Grammatika va vocabulary</i> emas ❌ → <i>Grammatika va vocabulary A1 level Food topic</i> ✅\n"
            "• Science: <i>Fizika</i> emas ❌ → <i>Nyutonning 3 qonuni va misollar</i> ✅\n\n"
            "<b>Mavzu qancha aniq bo'lsa, quiz shuncha sifatli chiqadi!</b> 🎯"
        ),
        "contest_message": "🌍 *Til o'rganish uchun partneringizni 30 sekundda toping! Batafsil ma'lumot: @lingomatch_bot*",

        
        "create_quiz": "🎯 Quiz yaratish",
        "split_quiz": "📂 Hemis quizni bo'lish",
        "settings": "⚙️ Sozlamalar",
        "help": "❓ Yordam",
        "balance": "💰 Balans",
        "share": "🔗 Ulashing va bepul quiz",
        "quiz_type_set": "✅ *Quiz turi: {quiz_type_name}*",
        "error_occurred": "❌ Xatolik yuz berdi. Qayta urinib ko‘ring.",
                "my_quizzes": "📚 Mening Quizlarim",
                "processing":"⏳ Bergan mavzuyingizni o'rganyapman. Iltimos, kuting..."
    }
}

# --- DMTT branding: teacher info under the welcome text, no ads for other bots ---
from src.brand import IS_DMTT, WELCOME_BLOCK_MD
if IS_DMTT:
    for _lang, _t in MAIN_MENU_TRANSLATIONS.items():
        _t["welcome_message"] += WELCOME_BLOCK_MD.get(_lang, WELCOME_BLOCK_MD["uz"])
        _t["contest_message"] = ""      # was an ad for another of your bots


def sanitize_name(name: str) -> str:
    """Remove or replace special Markdown characters in names"""
    if not name:
        return "User"
    # Replace problematic characters with space or remove them
    name = name.replace('*', '').replace('_', '').replace('[', '').replace(']', '')
    name = name.replace('`', '').replace('~', '').replace('>', '').replace('#', '')
    # Clean up multiple spaces and strip
    name = ' '.join(name.split())
    return name.strip() or "User"


async def show_main_menu_with_welcome(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user,
    language: str
):
    """Show main menu with welcome message (fully translated)."""
    context.user_data.clear()

    try:
        t = MAIN_MENU_TRANSLATIONS.get(language, MAIN_MENU_TRANSLATIONS["en"])

        # Sanitize the user's first name before using it
        safe_name = sanitize_name(user.first_name)
        welcome_text = t["welcome_message"].format(name=safe_name)
        
        # Get contest message
        contest_text = t.get("contest_message", "")

        keyboard = [
            [KeyboardButton(t["create_quiz"])],
            [KeyboardButton(t["split_quiz"])],
            [KeyboardButton(t["my_quizzes"])],
            [KeyboardButton(t["settings"]), KeyboardButton(t["help"])],
            [KeyboardButton(t["balance"]), KeyboardButton(t["share"])]
        ]

        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False,
            selective=True
        )

        if update.message:
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            # Send contest message separately
            # if contest_text:
            #     await update.message.reply_text(
            #         contest_text,
            #         parse_mode=ParseMode.MARKDOWN
            #     )
        elif update.callback_query:
            await update.callback_query.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            # Send contest message separately
            if contest_text:
                await update.callback_query.message.reply_text(
                    contest_text,
                    parse_mode=ParseMode.MARKDOWN
                )

    except Exception as e:
        logger.error(f"Main menu error for user {user.id}: {e}")
        error_msg = get_translation(language, "error_occurred")

        if update.message:
            await update.message.reply_text(error_msg)
        elif update.callback_query:
            await update.callback_query.message.reply_text(error_msg)

UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

async def _handle_join_battle(update, context, args, user):
    """
    Opponent follows an invite link:
      ?start=join_battle_{room_id}_{quiz_id}
    This is always opened in the BOT PRIVATE CHAT.
    Ensures the user exists (creates them if not), then shows the room button.
    """
    from src.multiplayer_fight import WEB_APP_URL
    from src.user_management import get_user_language, get_shared_quiz
    from handlers.sharing_quiz import SHARING_TRANSLATIONS
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    logger.info(
        f"[JOIN_BATTLE] User {user.id} (@{user.username}) arrived via join_battle link. "
        f"raw_arg={args[0]!r}"
    )

    # ── Parse room_id + quiz_id ────────────────────────────────────────────
    rest = args[0][len("join_battle_"):]

    match = UUID_PATTERN.search(rest)
    if not match:
        logger.warning(f"[JOIN_BATTLE] Could not find UUID in arg: {args[0]!r}")
        await update.message.reply_text("❌ Invalid invite link.")
        return

    quiz_id = match.group(0)
    room_id = rest[: match.start()].rstrip("_")

    if not room_id:
        logger.warning(f"[JOIN_BATTLE] room_id is empty after parsing. rest={rest!r}")
        await update.message.reply_text("❌ Invalid invite link — missing room ID.")
        return

    logger.info(f"[JOIN_BATTLE] Parsed room_id={room_id!r}  quiz_id={quiz_id!r}")

    # ── Ensure user exists in DB ───────────────────────────────────────────
    user_exists = await check_user_exists(user.id)

    if not user_exists:
        logger.info(
            f"[JOIN_BATTLE] New user {user.id} (@{user.username}) — creating profile."
        )
        created = await create_new_user(
            user_id=user.id,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            username=user.username or "",
            language="uz",        # default; they can change later
            quiz_time=30,
            quiz_questions=5,
            inviter_id=None,
        )
        if not created:
            logger.error(
                f"[JOIN_BATTLE] Failed to create user profile for {user.id}."
            )
            await update.message.reply_text(
                "❌ Could not create your profile. Please try again."
            )
            return
        logger.info(f"[JOIN_BATTLE] Profile created successfully for user {user.id}.")
    else:
        logger.info(
            f"[JOIN_BATTLE] Existing user {user.id} (@{user.username}) — updating activity."
        )
        asyncio.create_task(
            update_user_activity(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
        )

    # ── Fetch language + quiz data ─────────────────────────────────────────
    language = await get_user_language(user.id) or "en"
    t = SHARING_TRANSLATIONS.get(language, SHARING_TRANSLATIONS["en"])

    quiz_data = await get_shared_quiz(quiz_id)
    if not quiz_data:
        logger.warning(f"[JOIN_BATTLE] Quiz {quiz_id!r} not found in DB.")
        await update.message.reply_text("❌ Quiz not found.")
        return

    title         = quiz_data.get("title", "Quiz")
    num_questions = len(quiz_data.get("questions", []))
    quiz_time     = quiz_data.get("quiz_time", 30)

    logger.info(
        f"[JOIN_BATTLE] Sending join UI to user {user.id}. "
        f"room={room_id}  quiz={quiz_id}  title={title!r}"
    )

    JOIN_TEXT = {
        "en": (
            f"⚔️ <b>You've been challenged to a Quiz Battle!</b>\n\n"
            f"<b>Quiz:</b> {title}\n"
            f"📊 {num_questions} questions | ⏱️ {quiz_time} sec per question\n"
            f"<b>Room ID:</b> <code>{room_id}</code>\n\n"
            "Tap <b>Enter Battle Room</b> to join!\n"
            "⚡ Answer fast and correctly to win!"
        ),
        "uz": (
            f"⚔️ <b>Sizni Quiz Jangi ga taklif qilishdi!</b>\n\n"
            f"<b>Quiz:</b> {title}\n"
            f"📊 {num_questions} ta savol | ⏱️ {quiz_time} soniya har savol\n"
            f"<b>Xona ID:</b> <code>{room_id}</code>\n\n"
            "<b>Jang Xonasiga Kirish</b> tugmasini bosing!\n"
            "⚡ Tez va to'g'ri javob bering — g'alaba sizniki!"
        ),
        "ru": (
            f"⚔️ <b>Вас вызвали на Дуэль!</b>\n\n"
            f"<b>Квиз:</b> {title}\n"
            f"📊 {num_questions} вопросов | ⏱️ {quiz_time} сек на вопрос\n"
            f"<b>ID комнаты:</b> <code>{room_id}</code>\n\n"
            "Нажмите <b>Войти в комнату</b> и сразитесь!\n"
            "⚡ Отвечайте быстро и правильно — победа ваша!"
        ),
    }

    web_app_url = f"{WEB_APP_URL}?room={room_id}"

    await update.message.reply_text(
        JOIN_TEXT.get(language, JOIN_TEXT["en"]),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    t.get("enter_room", "⚔️ Enter Battle Room"),
                    web_app=WebAppInfo(url=web_app_url),
                )
            ]
        ]),
    )

    logger.info(
        f"[JOIN_BATTLE] Done — user {user.id} received join UI for room {room_id}."
    )

async def web_app_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle data sent from the web app (e.g. export results)."""
    try:
        data = json.loads(update.effective_message.web_app_data.data)
    except Exception:
        return

    action = data.get("action")

    if action == "export_results":
        text = data.get("text", "No results available.")
        room_id = data.get("room_id", "")

        # Send results as a formatted message to the user
        await update.effective_message.reply_text(
            f"📊 <b>Battle Results Exported</b>\n"
            f"Room: <code>{room_id}</code>\n\n"
            f"<pre>{text}</pre>",
            parse_mode="HTML"
        )

async def _handle_battle_info(update, context, args, user):
    """
    Creator taps '1v1 Battle' from an inline-shared quiz result.
    Deep link: ?start=battle_info_{quiz_id}
    Creates exactly ONE room. Opponent link always uses join_battle_...
    """
    from src.multiplayer_fight import create_multiplayer_room, WEB_APP_URL
    from src.user_management import get_user_language, get_shared_quiz
    from handlers.sharing_quiz import SHARING_TRANSLATIONS, generate_invite_share_url
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    raw = args[0][len("battle_info_"):]

    match = UUID_PATTERN.search(raw)
    if not match:
        await update.message.reply_text("❌ Invalid battle link.", parse_mode="HTML")
        return

    quiz_id = match.group(0)
    language = await get_user_language(user.id) or 'en'
    t = SHARING_TRANSLATIONS.get(language, SHARING_TRANSLATIONS['en'])

    quiz_data = await get_shared_quiz(quiz_id)
    if not quiz_data:
        await update.message.reply_text("❌ <b>Quiz not found.</b>", parse_mode="HTML")
        return

    title         = quiz_data.get("title", "Quiz")
    num_questions = len(quiz_data.get("questions", []))
    quiz_time     = quiz_data.get("quiz_time", 30)

    try:
        room_data   = await create_multiplayer_room(quiz_id, quiz_data, user.id)
        room_id     = room_data.get("room_id")
        web_app_url = room_data.get("web_app_url") or f"{WEB_APP_URL}?room={room_id}"
    except Exception as e:
        await update.message.reply_text(
            "❌ Could not create battle room. Try again later.", parse_mode="HTML"
        )
        return

    bot_username = (await context.bot.get_me()).username

    # FIX #7: join link goes to bot private chat — NOT directly to web app
    # So when shared to a group, tapping it opens bot DM which shows the join button
    join_link = f"https://t.me/{bot_username}?start=join_battle_{room_id}_{quiz_id}"

    # FIX #7: share_url uses the join_link (telegram deep link) for group sharing
    share_url = generate_invite_share_url(join_link, t.get('invite_text', '⚔️ Join my Quiz Battle!'))

    INFO_TEXT = {
        'en': (
            f"⚔️ <b>1v1 Quiz Battle</b>\n\n"
            f"<b>Quiz:</b> {title}\n"
            f"📊 {num_questions} questions | ⏱️ {quiz_time} sec per question\n"
            f"<b>Room ID:</b> <code>{room_id}</code>\n\n"
            f"1️⃣ Tap <b>Open Battle Room</b> to enter your room.\n"
            f"2️⃣ Tap <b>Invite Opponent</b> to share the join link.\n\n"
            f"🔗 Opponent's join link:\n<code>{join_link}</code>"
        ),
        'uz': (
            f"⚔️ <b>1v1 Quiz Jangi</b>\n\n"
            f"<b>Quiz:</b> {title}\n"
            f"📊 {num_questions} ta savol | ⏱️ {quiz_time} soniya har savol\n"
            f"<b>Xona ID:</b> <code>{room_id}</code>\n\n"
            f"1️⃣ <b>Jang Xonasini Ochish</b> — xonaga kiring.\n"
            f"2️⃣ <b>Raqibni Taklif Qilish</b> — havolani yuboring.\n\n"
            f"🔗 Raqib havolasi:\n<code>{join_link}</code>"
        ),
        'ru': (
            f"⚔️ <b>1v1 Дуэль</b>\n\n"
            f"<b>Квиз:</b> {title}\n"
            f"📊 {num_questions} вопросов | ⏱️ {quiz_time} сек на вопрос\n"
            f"<b>ID комнаты:</b> <code>{room_id}</code>\n\n"
            f"1️⃣ Нажмите <b>Открыть комнату</b> — войдите в свою комнату.\n"
            f"2️⃣ Нажмите <b>Пригласить соперника</b> — отправьте ссылку.\n\n"
            f"🔗 Ссылка для соперника:\n<code>{join_link}</code>"
        )
    }

    await update.message.reply_text(
        INFO_TEXT.get(language, INFO_TEXT['en']),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            # Creator opens the web app directly
            [InlineKeyboardButton(t.get('open_room', '⚔️ Open Battle Room'), web_app=WebAppInfo(url=web_app_url))],
            # FIX #7: Share button uses Telegram deep link — works in groups too
            [InlineKeyboardButton(t.get('invite', '📨 Invite Opponent'), url=share_url)],
        ])
    )


@track_handler("start")

async def start(update, context):
    user = update.effective_user
    if update.effective_chat:
        fire_and_forget(_typing(context, update.effective_chat.id))   # was awaited
    context.user_data["busy"] = False
    args = context.args
    invited_by = None


    # ── JOIN BATTLE — must be first so user creation happens inside the helper ──
    if args and args[0].startswith("join_battle_"):
        logger.info(
            f"[START] join_battle_ deep link detected for user {user.id} "
            f"(@{user.username}). arg={args[0]!r}"
        )
        await _handle_join_battle(update, context, args, user)
        return ConversationHandler.END

    # ── BATTLE INFO (creator tapped 1v1 from inline result) ───────────────
    if args and args[0].startswith("battle_info_"):
        logger.info(
            f"[START] battle_info_ deep link detected for user {user.id}. "
            f"arg={args[0]!r}"
        )
        await _handle_battle_info(update, context, args, user)
        return ConversationHandler.END

    # ── SHARED QUIZ / GROUP QUIZ deep links ───────────────────────────────
    if args and (args[0].startswith("quiz_") or args[0].startswith("groupquiz_")):
        if args[0].startswith("quiz_"):
            quiz_id = args[0][5:]
            logger.info(
                f"[START] Shared quiz deep link. user={user.id}  quiz_id={quiz_id}"
            )

            user_exists = await check_user_exists(user.id)
            if not user_exists:
                created = await create_new_user(
                    user_id=user.id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username,
                    language="uz",
                    quiz_time=30,
                    quiz_questions=5,
                )
                if not created:
                    await update.message.reply_text(
                        "❌ <b>Error: Could not create user profile.</b>",
                        parse_mode="HTML",
                    )
                    return ConversationHandler.END
            else:
                asyncio.create_task(
                    update_user_activity(
                        user_id=user.id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                    )
                )

            quiz_data = await get_shared_quiz(quiz_id)
            if not quiz_data:
                await update.message.reply_text(
                    "❌ <b>Error: Quiz not found.</b>", parse_mode="HTML"
                )
                return CONTENT

            context.user_data["current_quiz"]      = quiz_data
            context.user_data["current_quiz_id"]   = quiz_id
            context.user_data["quiz_start_time"]   = datetime.now(timezone.utc)
            context.user_data["total_questions"]   = len(quiz_data["questions"])
            context.user_data["correct_answers"]   = 0

            title     = quiz_data.get("title", "📝 Multiple Choice Quiz")
            summary   = quiz_data.get("summary", "")
            quiz_time = await get_user_quiz_time(user.id)

            quiz_message = (
                f"✅ <b>Quiz Ready!</b>\n\n"
                f"<b>{title}</b>\n\n"
                f"<b>Summary:</b> {summary}\n\n"
                f"⏱️ <b>Time limit:</b> {quiz_time} seconds per question\n"
                f"📝 <b>Number of questions:</b> {len(quiz_data['questions'])}"
            )
            language     = await get_user_language(user.id) or "en"
            t            = SHARING_TRANSLATIONS.get(language, SHARING_TRANSLATIONS["en"])
            bot_username = (await context.bot.get_me()).username

            keyboard = [
                [InlineKeyboardButton(t["start_quiz"], callback_data=f"quiz_{quiz_id}")],
                [InlineKeyboardButton(t["share_quiz"], switch_inline_query=f"quiz_{quiz_id}")],
                [
                    InlineKeyboardButton(
                        t["share_to_group"],
                        url=f"https://t.me/{bot_username}?startgroup=groupquiz_{quiz_id}",
                    )
                ],
            ]
            await update.message.reply_text(
                quiz_message,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return PROCESSING

        elif args[0].startswith("groupquiz_"):
            quiz_id = args[0][len("groupquiz_"):]
            logger.info(
                f"[START] Group quiz deep link. user={user.id}  quiz_id={quiz_id}"
            )

            quiz_data = await get_shared_quiz(quiz_id)
            if not quiz_data:
                await update.message.reply_text(
                    "❌ <b>Error: Quiz not found.</b>", parse_mode="HTML"
                )
                return ConversationHandler.END

            title           = quiz_data.get("title", "📝 Multiple Choice Quiz")
            summary         = quiz_data.get("summary", "")
            num_questions   = len(quiz_data.get("questions", []))
            creator_user_id = quiz_data.get("user_id")

            quiz_time = quiz_data.get("quiz_time")
            if quiz_time is None:
                quiz_time = (
                    min(await get_user_quiz_time(creator_user_id), 600)
                    if creator_user_id
                    else 30
                )
            else:
                quiz_time = int(quiz_time)

            quiz_info_text    = quiz_data.get("quiz_info", "")
            quiz_info_display = (
                f"\n\n<b>📝 Quiz Info:</b>\n{quiz_info_text}" if quiz_info_text else ""
            )

            quiz_info = (
                f"🎮 <b>Group Quiz Title:</b> {title}\n\n"
                f"<b>Summary:</b> {summary}"
                f"{quiz_info_display}\n\n"
                f"📝 <b>Questions:</b> {num_questions}\n"
                f"⏱️ <b>Time per question:</b> {quiz_time} seconds\n\n"
                f"Press the button below to start the quiz for everyone in this group!\n\n"
                f"Type /stopquiz to stop the quiz."
            )
            language = await get_user_language(user.id) or "en"
            t        = SHARING_TRANSLATIONS.get(language, SHARING_TRANSLATIONS["en"])

            keyboard = [
                [
                    InlineKeyboardButton(
                        t["start_group_quiz"],
                        callback_data=f"start_group_quiz_{quiz_id}",
                    )
                ],
            ]
            await update.message.reply_text(
                quiz_info,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return ConversationHandler.END

    # ── REFERRAL ───────────────────────────────────────────────────────────
    if args and args[0].startswith("ref_"):
        invited_by_str = args[0][4:]
        try:
            invited_by = int(invited_by_str)
            if invited_by == user.id:
                invited_by = None
        except ValueError:
            logger.warning(f"[START] Invalid referral ID: {invited_by_str!r}")
            invited_by = None

            
    # Check if user exists
    try:
        profile = await get_user_profile(user.id)       # cached; replaces check_user_exists + get_user_settings_batch
    except Exception as e:
        logger.error(f"[START] DB error for {user.id}: {e}")
        await update.message.reply_text("❌ Temporary error. Please send /start again.")
        return ConversationHandler.END
    user_exists = profile is not None

    # ---------- ADMIN ----------
    if str(user.id) == "999932510":
        if user_exists:
            fire_and_forget(touch_user_activity(user.id, user.username, user.first_name, user.last_name))

        total_users, total_files, todays_active, total_groups, success_rate = await asyncio.gather(
            get_total_users(), get_total_processed_files(), get_todays_active_users(),
            get_total_groups(), get_success_rate()
        )
        admin_message = (
            "👑 *Admin Dashboard*\n\n"
            f"📊 Total Users: {total_users}\n"
            f"👥 Active Users Today: {todays_active}\n"
            f"📝 Total Processed Files: {total_files}\n\n"
            f"🏘️ Total Groups: {total_groups}\n\n"
            "📈 *Statistics:*\n"
            f"• Average files per user: {total_files / total_users if total_users else 0:.1f}\n"
            f"• Success rate: {success_rate:.1f}%"
        )
        await update.message.reply_text(text=admin_message, parse_mode=ParseMode.MARKDOWN)

        if not user_exists:
            await create_new_user(user_id=user.id, first_name=user.first_name or "",
                                  last_name=user.last_name or "", username=user.username or "",
                                  language="uz", quiz_time=30, quiz_questions=5, inviter_id=None)
            keyboard = [[InlineKeyboardButton(text, callback_data=f"lang_{code}")]
                        for code, text in LANGUAGES.items()]
            await update.message.reply_text(get_translation("en", "choose_language"),
                                            parse_mode=ParseMode.MARKDOWN,
                                            reply_markup=InlineKeyboardMarkup(keyboard))
            return LANGUAGE
        await show_main_menu_with_welcome(update, context, user, profile.get("language") or "en")
        return CONTENT

    # ---------- NEW USER ----------
    if not user_exists:
        await create_new_user(user_id=user.id, first_name=user.first_name or "",
                              last_name=user.last_name or "", username=user.username or "",
                              language="uz", quiz_time=30, quiz_questions=5, inviter_id=invited_by)
        if invited_by:
            context.user_data['invited_by'] = invited_by
        keyboard = [[InlineKeyboardButton(text, callback_data=f"lang_{code}")]
                    for code, text in LANGUAGES.items()]
        await update.message.reply_text(get_translation("en", "choose_language"),
                                        parse_mode=ParseMode.MARKDOWN,
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        return LANGUAGE

    # ---------- EXISTING USER ----------
    if FORCE_SUBSCRIPTION_ENABLED and not await force_subscription_check(update, context):
        return ConversationHandler.END      # normally instant now: positive result is cached

    fire_and_forget(touch_user_activity(user.id, user.username, user.first_name, user.last_name))
    await show_main_menu_with_welcome(update, context, user, profile.get("language") or "en")
    return CONTENT


async def send_next_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    quiz_data: Dict,
    question_idx: int
) -> None:
    try:
        # Initialize unanswered_count if not exists
        if 'unanswered_count' not in context.user_data:
            context.user_data['unanswered_count'] = 0
        
        # FIXED: Check if already sent this question
        current_idx = context.user_data.get('current_question_index', -1)
        if current_idx == question_idx and context.user_data.get('current_poll_id'):
            logger.warning(f"[SEND QUESTION] Question {question_idx} already sent, skipping duplicate")
            return
        
        # FIXED: Check pause BEFORE sending question
        if context.user_data.get('unanswered_count', 0) >= 2 and not context.user_data.get('quiz_paused', False):
            # Get user language
            user_language = await get_user_language(chat_id) or 'en'
            
            texts = {
                'en': {
                    'paused': '⏸️ <b>Quiz Paused</b>\n\nYou haven\'t answered the last 2 questions.\n\nDo you want to continue or stop the quiz?',
                    'continue': '▶️ Continue',
                    'stop': '🛑 Stop Quiz'
                },
                'uz': {
                    'paused': '⏸️ <b>Quiz to\'xtatildi</b>\n\nSiz oxirgi 2 ta savolga javob bermadingiz.\n\nDavom ettirishni yoki to\'xtatishni xohlaysizmi?',
                    'continue': '▶️ Davom etish',
                    'stop': '🛑 To\'xtatish'
                },
                'ru': {
                    'paused': '⏸️ <b>Квиз приостановлена</b>\n\nВы не ответили на последние 2 вопроса.\n\nПродолжить или остановить викторину?',
                    'continue': '▶️ Продолжить',
                    'stop': '🛑 Остановить'
                }
            }
            
            lang_texts = texts.get(user_language, texts['en'])
            
            keyboard = [
                [
                    InlineKeyboardButton(lang_texts['continue'], callback_data="continue_private_quiz"),
                    InlineKeyboardButton(lang_texts['stop'], callback_data="stop_private_quiz")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=lang_texts['paused'],
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            
            context.user_data['quiz_paused'] = True
            context.user_data['paused_at_question'] = question_idx
            return
        
        if not quiz_data or "questions" not in quiz_data:
            logger.error(f"[SEND QUESTION] Invalid quiz_data: {quiz_data}")
            return

        total_questions = len(quiz_data["questions"])
        if question_idx >= total_questions:
            logger.warning(
                f"[SEND QUESTION] Question index {question_idx} >= total questions {total_questions}"
            )
            return

        question = quiz_data["questions"][question_idx]
        options = question["options"]
        allows_multiple = bool(question.get("allows_multiple_answers", False))

        # FIXED: Get quiz_time from multiple sources with correct priority
        quiz_time = quiz_data.get("quiz_time")
        if quiz_time is None:
            quiz_time = context.user_data.get('quiz_time')
        if quiz_time is None:
            quiz_time = 30
        else:
            quiz_time = int(quiz_time)
        
        if quiz_time > 0:
            quiz_time = max(5, min(quiz_time, 600))
        

        MAX_OPTION_LENGTH = 100

        # Truncate options safely
        truncated_options = []
        option_map = {}  # original -> truncated

        for opt in options:
            if len(opt) > MAX_OPTION_LENGTH:
                truncated = opt[: MAX_OPTION_LENGTH - 3] + "..."
                logger.warning(
                    f"[SEND QUESTION] Truncated option from {len(opt)} to {len(truncated)} chars"
                )
            else:
                truncated = opt

            truncated_options.append(truncated)
            option_map[opt] = truncated

        # Resolve correct option indices
        if allows_multiple:
            correct_answers = question.get("correct_answers", [])
            if not correct_answers:
                logger.error(
                    f"[SEND QUESTION] No correct_answers for multi-answer question {question_idx}"
                )
                return

            correct_option_ids = []
            for ans in correct_answers:
                if isinstance(ans, int):
                    correct_option_ids.append(ans)
                else:
                    truncated_ans = option_map.get(ans)
                    if truncated_ans is None:
                        logger.error(
                            f"[SEND QUESTION] Correct answer '{ans}' not found in options"
                        )
                        return
                    correct_option_ids.append(truncated_options.index(truncated_ans))
            
            # Validate all correct option IDs
            for opt_id in correct_option_ids:
                if opt_id >= len(truncated_options) or opt_id < 0:
                    logger.error(f"[SEND QUESTION] Invalid correct option ID: {opt_id}")
                    return
        else:
            correct_answer = question.get("correct_answer")
            if isinstance(correct_answer, int):
                correct_option_id = correct_answer
            else:
                truncated_ans = option_map.get(correct_answer)
                if truncated_ans is None:
                    logger.error(
                        f"[SEND QUESTION] Correct answer '{correct_answer}' not found in options"
                    )
                    return
                correct_option_id = truncated_options.index(truncated_ans)
            
            # Validate correct option ID
            if correct_option_id >= len(truncated_options) or correct_option_id < 0:
                logger.error(f"[SEND QUESTION] Invalid correct option ID: {correct_option_id}")
                return

        question_number = question_idx + 1
        question_base = question['question']


        adjusted_quiz_time = quiz_time + 3 


        # FIXED: Truncate question if too long (Telegram limit is 300 chars)
        # FIXED: Send full question as separate message if too long, then send poll with number only
        MAX_QUESTION_LENGTH = 280

        if len(question_base) > MAX_QUESTION_LENGTH:
            # Send full question text as a separate message first
            full_question_text = f"<b>{question_number}/{total_questions}:</b> {question_base}"
            await context.bot.send_message(
                chat_id=chat_id,
                text=full_question_text,
                parse_mode="HTML"
            )
            # Use only the question number in the poll
            question_text = f"{question_number}/{total_questions}"
        else:
            question_text = f"{question_number}/{total_questions}: {question_base}"

        # Final safety check
        if len(question_text) > 300:
            question_text = question_text[:297] + "..."
            logger.warning(f"[SEND QUESTION] Final truncation applied to question_text")

        context.user_data['current_question_index'] = question_idx

        # FIXED: Only include open_period if quiz_time > 0
        poll_kwargs = {
            "chat_id": chat_id,
            "question": question_text,
            "options": truncated_options,
            "type": Poll.QUIZ,
            "is_anonymous": False,
        }
        
        if quiz_time > 0:
            poll_kwargs["open_period"] = quiz_time + 1

        if allows_multiple:
            poll_message = await context.bot.send_poll(
                **poll_kwargs,
                allows_multiple_answers=True,
                correct_option_id=correct_option_ids
            )
        else:
            poll_message = await context.bot.send_poll(
                **poll_kwargs,
                allows_multiple_answers=False,
                correct_option_id=correct_option_id
            )
        
        # FIXED: Store poll_id and create task to wait for next question
        poll_id = poll_message.poll.id
        context.user_data['current_poll_id'] = poll_id
        
        time_desc = "no time limit" if quiz_time == 0 else f"{quiz_time}s time limit"
        logger.info(f"[SEND QUESTION] Sent question {question_idx + 1}/{total_questions} to chat {chat_id} with {time_desc}")
        
        # FIXED: Create background task to handle poll timeout
        if quiz_time > 0:
            asyncio.create_task(wait_for_private_poll_answer(update, context, chat_id, poll_id, quiz_time, quiz_data, question_idx))

    except Exception as e:
        logger.error(f"[SEND QUESTION] Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def wait_for_private_poll_answer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    poll_id: str,
    quiz_time: int,
    quiz_data: Dict,
    question_idx: int
) -> None:
    """Wait for poll to close and check if it was answered, then proceed."""
    try:
        # Wait for the poll time + 1 second buffer
        await asyncio.sleep(quiz_time + 1)
        
        current_poll_id = context.user_data.get('current_poll_id')
        if current_poll_id != poll_id:
            return
        
        current_question_idx = context.user_data.get('current_question_index', -1)
        if current_question_idx > question_idx:
            logger.info(f"[PRIVATE POLL] Already moved to question {current_question_idx}, skipping timeout for {question_idx}")
            return
        
        # Poll wasn't answered - increment unanswered count
        context.user_data['unanswered_count'] = context.user_data.get('unanswered_count', 0) + 1
        logger.info(f"[PRIVATE POLL] Poll {poll_id} timed out. Unanswered count: {context.user_data['unanswered_count']}")
        
        # Clear current poll ID since we're moving on
        context.user_data.pop('current_poll_id', None)        
        # Check if we should pause (2 unanswered questions)
        if context.user_data.get('unanswered_count', 0) >= 2:
            user_language = await get_user_language(chat_id) or 'en'
            
            texts = {
                'en': {
                    'paused': '⏸️ <b>Quiz Paused</b>\n\nYou haven\'t answered the last 2 questions.\n\nDo you want to continue or stop the quiz?',
                    'continue': '▶️ Continue',
                    'stop': '🛑 Stop Quiz'
                },
                'uz': {
                    'paused': '⏸️ <b>Quiz to\'xtatildi</b>\n\nSiz oxirgi 2 ta savolga javob bermadingiz.\n\nDavom ettirishni yoki to\'xtatishni xohlaysizmi?',
                    'continue': '▶️ Davom etish',
                    'stop': '🛑 To\'xtatish'
                },
                'ru': {
                    'paused': '⏸️ <b>Квиз приостановлена</b>\n\nВы не ответили на последние 2 вопроса.\n\nПродолжить или остановить викторину?',
                    'continue': '▶️ Продолжить',
                    'stop': '🛑 Остановить'
                }
            }
            
            lang_texts = texts.get(user_language, texts['en'])
            
            keyboard = [
                [
                    InlineKeyboardButton(lang_texts['continue'], callback_data="continue_private_quiz"),
                    InlineKeyboardButton(lang_texts['stop'], callback_data="stop_private_quiz")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=lang_texts['paused'],
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            
            context.user_data['quiz_paused'] = True
            context.user_data['paused_at_question'] = question_idx + 1  # Next question
            return
        
        # Not paused yet, proceed to next question
        next_idx = question_idx + 1
        total_questions = len(quiz_data["questions"])
        
        if next_idx < total_questions:
            await send_next_question(update, context, chat_id, quiz_data, next_idx)
        else:
            # Quiz completed
            total_questions_context = context.user_data.get('total_questions', total_questions)
            correct_answers = context.user_data.get('correct_answers', 0)
            accuracy = (correct_answers / total_questions_context * 100) if total_questions_context > 0 else 0

            quiz_start_time = context.user_data.get('quiz_start_time')
            quiz_end_time = datetime.now(timezone.utc)
            time_spent = (quiz_end_time - quiz_start_time).total_seconds() if quiz_start_time else 0

            quiz_id = context.user_data.get('current_quiz_id')
            from src.quiz_results import save_quiz_attempt, notify_quiz_owner
            if quiz_id:
                # Save attempt
                await save_quiz_attempt(
                    quiz_id=quiz_id,
                    user_id=chat_id,
                    username=context._user_data.get('username') if hasattr(context, '_user_data') else None,
                    first_name=update.effective_user.first_name if update and update.effective_user else 'Anonymous',
                    score=correct_answers,
                    total_questions=total_questions_context,
                    time_spent=time_spent
                )
                
                # Notify owner
                await notify_quiz_owner(
                    context=context,
                    quiz_id=quiz_id,
                    participant_id=chat_id,
                    participant_name=update.effective_user.first_name if update and update.effective_user else 'Anonymous',
                    score=correct_answers,
                    total_questions=total_questions_context,
                    time_spent=time_spent
                )                  
            language = await get_user_language(chat_id)
            
            quiz_completed_text = TRANSLATIONS[language]["quiz_completed"].format(
                total_questions=total_questions_context,
                correct_answers=correct_answers,
                accuracy=accuracy,
                time_spent=time_spent
            )

            if quiz_id:
                bot_username = (await context.bot.get_me()).username
                t = SHARING_TRANSLATIONS.get(language, SHARING_TRANSLATIONS['en'])
                keyboard = [
                    [InlineKeyboardButton(t['share_quiz'], switch_inline_query=f"quiz_{quiz_id}")],
                    [InlineKeyboardButton(t['share_to_group'], url=f"https://t.me/{bot_username}?startgroup=groupquiz_{quiz_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                reply_markup = None

            await context.bot.send_message(
                chat_id=chat_id,
                text=quiz_completed_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            # Clean up
            for key in ['correct_answers', 'total_questions', 'quiz_start_time', 'current_quiz_id', 'current_question_index', 'current_quiz', 'current_poll_id', 'unanswered_count']:
                context.user_data.pop(key, None)
            context.user_data['busy'] = False
            
    except Exception as e:
        logger.error(f"[PRIVATE POLL] Error in wait_for_private_poll_answer: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def send_already_using_bot_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Send message when user already exists and tries to use referral link."""
    language = await get_user_language(user_id)

    # Friendly messages in 3 languages
    messages = {
        "en": "ℹ️ You are already using this bot. Welcome back!\n\nYou can continue using all features below.",
        "ru": "ℹ️ Вы уже используете этого бота. Добро пожаловать обратно!\n\nВы можете продолжить использовать все функции ниже.",
        "uz": "ℹ️ Siz allaqachon ushbu botdan foydalanmoqdasiz. Qaytganingiz bilan!\n\nQuyidagi tugmalar orqali davom etishingiz mumkin."
    }
    already_using_message = messages.get(language, messages["en"])

    create_presentation_text = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("create_quiz", "🎯 Create Quiz")
    balance_text = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("balance", "💰 Balance")

    keyboard = [
        [InlineKeyboardButton(create_presentation_text, callback_data="start_creation")],
        [InlineKeyboardButton(balance_text, callback_data="balance")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            already_using_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            already_using_message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language_code = query.data.split('_')[1]
    
    logger.info(f"User {user.id} selected language: {language_code}")
    
    # Update language in database
    await update_user_language(user.id, language_code)
    
    language_messages = {
        "en": "✅ Perfect! English has been set as your language!",
        "ru": "✅ Отлично! Русский язык установлен!",
        "uz": "✅ Ajoyib! O'zbek tili o'rnatildi!"
    }
    
    language_message = language_messages.get(language_code, language_messages["uz"])
    
    # Delete old message
    try:
        await query.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete language selection message: {e}")
    
    # Send language confirmation
    await context.bot.send_message(
        chat_id=user.id,
        text=language_message,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Check subscription with NEW language
    if FORCE_SUBSCRIPTION_ENABLED:  
        if not await force_subscription_check(update, context):
            invited_by = context.user_data.get('invited_by')
            if invited_by:
                context.user_data['pending_referral'] = {
                    'inviter_id': invited_by,
                    'invited_user_id': user.id,
                    'invited_user_language': language_code
                }
            return ConversationHandler.END
    
    # Process referral if subscribed
    invited_by = context.user_data.get('invited_by')
    if invited_by:
        await process_referral_bonus(user.id, invited_by, context, language_code)
        context.user_data.pop('invited_by', None)
    
    # Show main menu
    await show_main_menu_with_welcome(update, context, user, language_code)
    return CONTENT

async def process_referral_bonus(invited_user_id: int, inviter_id: int, context: ContextTypes.DEFAULT_TYPE, invited_user_language: str):
    try:
        # Check referral limit FIRST
        referral_count = await get_user_referral_count(inviter_id)
        
        if referral_count >= 200:
            logger.warning(f"⚠️ User {inviter_id} has reached referral limit ({referral_count} referrals)")
            
            # Notify inviter they've hit the limit
            inviter_lang = await get_user_language(inviter_id)
            
            limit_messages = {
                "en": f"🎉 *Congratulations!*\n\nYou've reached the maximum referral limit with *{referral_count}* successful invitations!\n\nYou cannot earn more referral bonuses, but you can top up your balance anytime.\n\nThank you for your support! 🙏",
                "ru": f"🎉 *Поздравляем!*\n\nВы достигли максимального лимита рефералов с *{referral_count}* успешными приглашениями!\n\nВы больше не можете зарабатывать реферальные бонусы, но можете пополнить баланс в любое время.\n\nСпасибо за вашу поддержку! 🙏",
                "uz": f"🎉 *Sizning do'stingiz referral orqali qo'shilmoqchi bo'ldi, lekin afsuski *\n\nSiz *{referral_count}* ta muvaffaqiyatli taklif bilan maksimal referral limitga yetdingiz!\n\nSiz endi referral bonuslari ishlay olmaysiz, lekin balansni istalgan vaqtda to'ldirishingiz mumkin.\n\nQo'llab-quvvatlaganingiz uchun rahmat! 🙏"
            }
            
            await context.bot.send_message(
                chat_id=inviter_id,
                text=limit_messages.get(inviter_lang, limit_messages["en"]),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Still notify the invited user they joined via referral
            bot_username = context.bot.username
            joining_messages = {
                "en": f"🎉 *You joined through a referral link!*\n\nWelcome to our community!\n\n🔗 *Your referral link:*\n`https://t.me/{bot_username}?start=ref_{invited_user_id}`\n\nShare it to earn free quizzes! 🚀",
                "ru": f"🎉 *Вы присоединились по реферальной ссылке!*\n\nДобро пожаловать в наше сообщество!\n\n🔗 *Ваша реферальная ссылка:*\n`https://t.me/{bot_username}?start=ref_{invited_user_id}`\n\nПоделитесь ей, чтобы заработать бесплатные викторины! 🚀",
                "uz": f"🎉 *Siz referral havola orqali qo'shildingiz!*\n\nJamiyatimizga xush kelibsiz!\n\n🔗 *Sizning referral havolangiz:*\n`https://t.me/{bot_username}?start=ref_{invited_user_id}`\n\nBepul quizlar ishlab topish uchun ulashing! 🚀"
            }
            
            await context.bot.send_message(
                chat_id=invited_user_id,
                text=joining_messages.get(invited_user_language, joining_messages["en"]),
                parse_mode=ParseMode.MARKDOWN
            )
            
            return False
        
        # ANTI-NAKRUTKA: Check if the NEW user is subscribed to required channels
        from handlers.subscribe import check_user_subscriptions
        
        subscription_status = await check_user_subscriptions(invited_user_id, context)
        
        if not subscription_status['is_subscribed']:
            logger.warning(f"⚠️ Anti-nakrutka: User {invited_user_id} tried to complete referral without subscribing to channels")
            
            # Notify the new user they need to subscribe first
            subscription_reminder = {
                "en": "⚠️ *Subscribe First!*\n\nTo activate the referral bonus, please subscribe to our required channels first!",
                "ru": "⚠️ *Подпишитесь сначала!*\n\nЧтобы активировать реферальный бонус, пожалуйста, сначала подпишитесь на наши обязательные каналы!",
                "uz": "⚠️ *Avval obuna bo'ling!*\n\nReferral bonusni faollashtirish uchun avval hamkor kanallarimizga obuna bo'ling!"
            }
            
            await context.bot.send_message(
                chat_id=invited_user_id,
                text=subscription_reminder.get(invited_user_language, subscription_reminder["en"]),
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Store pending referral bonus
            context.user_data['pending_referral'] = {
                'inviter_id': inviter_id,
                'invited_user_id': invited_user_id,
                'invited_user_language': invited_user_language
            }
            
            return False
        
        # If subscribed and under limit, proceed with bonus
        from payment_integration_new import add_balance
        await add_balance(inviter_id, REFERRAL_BONUS, payment_type="referral_bonus", payment_method="manual")
        logger.info(f"✅ Added {REFERRAL_BONUS} balance to inviter {inviter_id} (invited user {invited_user_id} is subscribed)")
        
        # Get invited user's name
        try:
            invited_user_info = await context.bot.get_chat(invited_user_id)
            invited_user_name = invited_user_info.first_name or "Someone"
        except Exception:
            invited_user_name = "Someone"
        
        # Get inviter's language
        inviter_lang = await get_user_language(inviter_id)
        
        # Send bonus notification to inviter
        referral_messages = {
            "en": "🎉 *Referral Bonus!*\n\n{invited_name} joined using your referral link!\n\nYou received bonus credits - 2,000 UZS!\n\nKeep sharing to earn more! 🚀\n\n📊 Total referrals: *{referral_count}/200*",
            "ru": "🎉 *Реферальный бонус!*\n\n{invited_name} присоединился по вашей реферальной ссылке!\n\nВы получили бонусные кредиты - 2,000 UZS!\n\nПродолжайте делиться, чтобы заработать больше! 🚀\n\n📊 Всего рефералов: *{referral_count}/200*",
            "uz": "🎉 *Referral bonusi!*\n\n{invited_name} sizning referral havolangiz orqali qo'shildi!\n\nSiz bonus kreditlar oldingiz - 2,000 UZS!\n\nKo'proq daromad olish uchun ulashishda davom eting! 🚀\n\n📊 Jami referallar: *{referral_count}/200*"
        }
        
        notify_message = referral_messages.get(inviter_lang, referral_messages["en"]).format(
            invited_name=invited_user_name,
            referral_count=referral_count + 1  
        )

        keyboard = [
            [InlineKeyboardButton(
                TRANSLATIONS.get(inviter_lang, TRANSLATIONS["en"]).get("balance", "💰 Balance"),
                callback_data="balance"
            )],
            [InlineKeyboardButton(
                TRANSLATIONS.get(inviter_lang, TRANSLATIONS["en"]).get("share", "🔗 Share & Earn"),
                callback_data="share"
            )],
            [InlineKeyboardButton(
                TRANSLATIONS.get(inviter_lang, TRANSLATIONS["en"]).get("create_quiz", "🎯 Create Quiz"),
                callback_data="create_quiz"
            )]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=inviter_id,
            text=notify_message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

        user_referral_link = f"https://t.me/{context.bot.username}?start=ref_{invited_user_id}"
        
        joining_messages = {
            "en": f"🎉 *You joined through a referral link!*\n\nYour friend received a bonus for inviting you!\n\n🔗 *Your referral link:*\n`{user_referral_link}`\n\nShare it to earn free quizzes! For every friend who joins, you get bonus credits! 🚀",
            "ru": f"🎉 *Вы присоединились по реферальной ссылке!*\n\nВаш друг получил бонус за ваше приглашение!\n\n🔗 *Ваша реферальная ссылка:*\n`{user_referral_link}`\n\nПоделитесь ей, чтобы заработать бесплатные викторины! За каждого друга вы получаете бонусные кредиты! 🚀",
            "uz": f"🎉 *Siz referral havola orqali qo'shildingiz!*\n\nDo'stingiz sizni taklif qilgani uchun bonus oldi!\n\n🔗 *Sizning referral havolangiz:*\n`{user_referral_link}`\n\nBepul quizlar ishlab topish uchun ulashing! Har bir do'st uchun bonus kreditlar olasiz! 🚀"
        }
        
        joining_message = joining_messages.get(invited_user_language, joining_messages["en"])
        
        await context.bot.send_message(
            chat_id=invited_user_id,
            text=joining_message,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending referral join message with Markdown: {e}")
        # Fallback: send as plain text
        try:
            await context.bot.send_message(
                chat_id=invited_user_id,
                text=joining_message,
                parse_mode=None
            )
        except:
            pass



async def create_quiz_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle create quiz button press."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    
    # Send document request message
    send_document_text = TRANSLATIONS.get(language, MAIN_MENU_TRANSLATIONS["en"]).get(
        "send_document",
    )
    
    await query.edit_message_text(
        text=send_document_text,
        parse_mode=ParseMode.HTML
    )
    
    return CONTENT

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_chat_action("typing")
    
    language = await get_user_language(user.id)
    
    await update.message.reply_text(
        get_translation(language, "help"),
        parse_mode=ParseMode.MARKDOWN
    )


async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle settings button press - redirect to settings command."""
    query = update.callback_query
    await query.answer()
    
    from handlers.settings_button import settings_button

    user = query.from_user
    language = await get_user_language(user.id)
    
    return await settings_button(update, context)

async def help_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    
    # Send help message directly using callback query
    await query.edit_message_text(
        get_translation(language, "help"),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return CONTENT


async def quiz_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    quiz_type = query.data  # "mc" or "oe"
    language = await get_user_language(user.id)
    
    quiz_type_name = "Multiple Choice" if quiz_type == "mc" else "Open Ended"
    
    try:
        await update_user_quiz_type(user.id, quiz_type)
        
        # Get translated quiz type confirmation message
        confirmation_text = MAIN_MENU_TRANSLATIONS.get(language, MAIN_MENU_TRANSLATIONS["en"]).get(
            "quiz_type_set",
            "✅ *Quiz type set to {quiz_type_name}*"
        ).format(quiz_type_name=quiz_type_name)
        
        # Send confirmation and show main menu
        await query.edit_message_text(
            text=confirmation_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Show main menu after quiz type selection
        await show_main_menu_with_welcome(update, context, user, language or "en")
        
        logger.info(f"✅ QUIZ TYPE SAVED: User {user.id} quiz type updated to {quiz_type} in database")
        
    except Exception as e:
        logger.error(f"❌ ERROR SAVING QUIZ TYPE: {e}")
        await query.edit_message_text(
            text=f"❌ *Error setting quiz type to {quiz_type_name}. Please try again.*",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return CONTENT

async def handle_continue_private_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle continue button for paused private quiz."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Reset pause state
    context.user_data['quiz_paused'] = False
    context.user_data['unanswered_count'] = 0
    
    # Get paused question index
    question_idx = context.user_data.get('paused_at_question', 0)
    quiz_data = context.user_data.get('current_quiz')
    
    if not quiz_data:
        await query.edit_message_text("❌ Quiz data not found. Please start over.")
        return CONTENT
    
    # Delete pause message
    try:
        await query.message.delete()
    except:
        pass
    
    # Continue from paused question
    await send_next_question(update, context, user_id, quiz_data, question_idx)
    return CONTENT


async def handle_stop_private_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle stop button for paused private quiz."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    language = await get_user_language(user_id)
    
    # Calculate partial results
    total_questions = context.user_data.get('total_questions', 0)
    correct_answers = context.user_data.get('correct_answers', 0)
    current_question = context.user_data.get('current_question_index', 0)
    
    stop_messages = {
        'en': (
            "🛑 <b>Quiz Stopped</b>\n\n"
            f"You answered {current_question}/{total_questions} questions\n"
            f"✅ Correct answers: {correct_answers}\n\n"
            "Thanks for participating! Use /start to try again."
        ),
        'uz': (
            "🛑 <b>Quiz To'xtatildi</b>\n\n"
            f"Siz {current_question}/{total_questions} ta savolga javob berdingiz\n"
            f"✅ To'g'ri javoblar: {correct_answers}\n\n"
            "Ishtirok etganingiz uchun rahmat! Qayta urinish uchun /start ni bosing."
        ),
        'ru': (
            "🛑 <b>Квиз Остановлена</b>\n\n"
            f"Вы ответили на {current_question}/{total_questions} вопросов\n"
            f"✅ Правильных ответов: {correct_answers}\n\n"
            "Спасибо за участие! Используйте /start, чтобы попробовать снова."
        )
    }
    
    await query.edit_message_text(
        stop_messages.get(language, stop_messages['en']),
        parse_mode="HTML"
    )
    
    # Clean up
    for key in ['correct_answers', 'total_questions', 'quiz_start_time', 'current_quiz_id', 
                'current_question_index', 'current_quiz', 'current_poll_id', 'unanswered_count',
                'quiz_paused', 'paused_at_question']:
        context.user_data.pop(key, None)
    context.user_data['busy'] = False
    
    return CONTENT