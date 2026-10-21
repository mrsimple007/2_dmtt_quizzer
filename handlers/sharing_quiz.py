from src.tables import TBL
import uuid
from typing import Optional, Dict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src.imports import *
from src.user_management import get_shared_quiz, get_user_language
from telegram import WebAppInfo


SHARING_TRANSLATIONS = {
    'en': {
        'start_quiz': '🎯 Start Quiz',
        'share_quiz': '📤 Share Quiz',
        'share_to_group': '👥 Share to Group',
        'group_quiz_title': '🎮 Group Quiz Title:',
        'summary': 'Summary:',
        'quiz_info': '📝 Quiz Info:',
        'play_together': '👥 Play together with your group members!',
        'questions': '📊 {num} questions',
        'time_per_question': '⏱️ Time per question: {time} seconds',
        'click_button': 'Click the button below to start the quiz.',
        'stop_command': 'Type /stopquiz to stop the quiz.',
        'start_command': 'To start this quiz in your group, copy and send:',
        'start_group_quiz': '🎯 Start Group Quiz',
        'quiz_ready': '✅ Quiz Ready!',
        'time_limit': '⏱️ Time limit:',
        'num_questions': '📝 Number of questions:',
        'click_to_share': 'questions • Click to share in a group',
        'quiz_prefix': 'Quiz:',
        'multiplayer_battle': '🎮 Multiplayer Battle',
        'open_room': '🎮 Open Battle Room',
        'enter_room': '🎮 Enter Battle Room',
        'invite': '📤 Invite Opponent',
        'share_invite': '📤 Share Invite Link',
        '1v1_battle': '⚔️ 1v1 Battle',
        'share_invite_link': '📤 Share Invite Link',
        'invite_text': "⚔️ I challenge you to a Quiz Battle! 🧠\n\nJoin my room and let's see who's smarter!\nTap the link to enter the battle 👆",
    },
    'uz': {
        'start_quiz': '🎯 Quizni boshlash',
        'share_quiz': '📤 Quizni ulashish',
        'share_to_group': '👥 Guruhda ulashish',
        'group_quiz_title': '🎮 Guruh Quiz nomi:',
        'summary': 'Qisqacha:',
        'quiz_info': '📝 Quiz haqida:',
        'play_together': '👥 Guruh a\'zolaringiz bilan birga o\'ynang!',
        'questions': '📊 {num} ta savol',
        'time_per_question': '⏱️ Har bir savol uchun vaqt: {time} soniya',
        'click_button': 'Quizni boshlash uchun quyidagi tugmani bosing.',
        'stop_command': 'Quizni to\'xtatish uchun /stopquiz yuboring.',
        'start_command': 'Guruhingizda ushbu quizni boshlash uchun nusxa oling va yuboring:',
        'start_group_quiz': '🎯 Guruh Quizni Boshlash',
        'quiz_ready': '✅ Quiz Tayyor!',
        'time_limit': '⏱️ Vaqt chegarasi:',
        'num_questions': '📝 Savollar soni:',
        'click_to_share': 'ta savol • Guruhda ulashish uchun bosing',
        'quiz_prefix': 'Quiz:',
        'multiplayer_battle': '🎮 Multiplayer Battle',
        'open_room': '🎮 Jang Xonasini Ochish',
        'enter_room': '🎮 Jang Xonasiga Kirish',
        'invite': '📤 Raqibni Taklif Qilish',
        'share_invite': '📤 Taklif Havolasini Ulashish',
        '1v1_battle': '⚔️ 1v1 Jang',
        'share_invite_link': '📤 Taklif Havolasini Ulashish',
        'invite_text': "⚔️ Seni Quiz Jangi ga taklif qilyapman! 🧠\n\nKim aqlliroq ekanini ko'ramiz!\nJangga kirish uchun havolani bosing 👆",
    },
    'ru': {
        'start_quiz': '🎯 Начать Квиз',
        'share_quiz': '📤 Поделиться Квизом',
        'share_to_group': '👥 Поделиться в Группе',
        'group_quiz_title': '🎮 Название Группового Квиза:',
        'summary': 'Описание:',
        'quiz_info': '📝 Информация о квизе:',
        'play_together': '👥 Играйте вместе с участниками вашей группы!',
        'questions': '📊 {num} вопросов',
        'time_per_question': '⏱️ Время на вопрос: {time} секунд',
        'click_button': 'Нажмите кнопку ниже, чтобы начать квиз.',
        'stop_command': 'Введите /stopquiz чтобы остановить квиз.',
        'start_command': 'Чтобы начать этот квиз в вашей группе, скопируйте и отправьте:',
        'start_group_quiz': '🎯 Начать Групповой Квиз',
        'quiz_ready': '✅ Квиз Готов!',
        'time_limit': '⏱️ Ограничение по времени:',
        'num_questions': '📝 Количество вопросов:',
        'click_to_share': 'вопросов • Нажмите, чтобы поделиться в группе',
        'quiz_prefix': 'Квиз:',
        'multiplayer_battle': '🎮 Мультиплеерная Битва',
        'open_room': '🎮 Открыть Комнату',
        'enter_room': '🎮 Войти в Комнату',
        'invite': '📤 Пригласить Соперника',
        'share_invite': '📤 Поделиться Ссылкой',
        '1v1_battle': '⚔️ 1v1 Битва',
        'share_invite_link': '📤 Поделиться Ссылкой',
        'invite_text': "⚔️ Вызываю тебя на Дуэль! 🧠\n\nПосмотрим кто умнее!\nНажми на ссылку, чтобы войти в комнату 👆",
    }
}


def generate_share_link(bot_username: str, quiz_id: str) -> str:
    return f"https://t.me/{bot_username}?start=quiz_{quiz_id}"


def generate_invite_share_url(join_link: str, invite_text: str) -> str:
    """Generate a Telegram share URL that opens a share dialog with pre-filled message."""
    import urllib.parse
    encoded_text = urllib.parse.quote(invite_text)
    encoded_url = urllib.parse.quote(join_link)
    return f"https://t.me/share/url?url={encoded_url}&text={encoded_text}"


def get_share_quiz_keyboard(bot_username: str, quiz_id: str, language: str = 'en'):
    """Generate share keyboard with language support."""
    t = SHARING_TRANSLATIONS.get(language, SHARING_TRANSLATIONS['en'])
    link = generate_share_link(bot_username, quiz_id)
    
    keyboard = [
        [InlineKeyboardButton(t['start_quiz'], callback_data=f"start_quiz_{quiz_id}")],
        [InlineKeyboardButton(t['share_quiz'], switch_inline_query=f"quiz_{quiz_id}")],
        [InlineKeyboardButton(t['share_to_group'], url=f"https://t.me/{bot_username}?startgroup=groupquiz_{quiz_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_create_1v1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.multiplayer_fight import create_multiplayer_room, WEB_APP_URL
    query = update.callback_query
    await query.answer("⚔️ Creating your battle room...", show_alert=False)
    
    data = query.data
    if data.startswith("create_1v1_"):
        quiz_id = data[len("create_1v1_"):]
    elif data.startswith("create_multiplayer_"):
        quiz_id = data[len("create_multiplayer_"):]
    else:
        return

    user_id = query.from_user.id
    language = await get_user_language(user_id) or 'en'
    chat_type = query.message.chat.type

    quiz_data = await get_shared_quiz(quiz_id)
    if not quiz_data:
        await query.answer("❌ Quiz not found!", show_alert=True)
        return

    try:
        room_data = await create_multiplayer_room(quiz_id, quiz_data, user_id)
        room_id = room_data.get("room_id")
        web_app_url = room_data.get("web_app_url") or f"{WEB_APP_URL}?room={room_id}"
    except Exception as e:
        logger.error(f"Failed to create multiplayer room: {e}")
        await query.answer("❌ Could not create room. Try again later.", show_alert=True)
        return

    title = quiz_data.get("title", "Quiz")
    num_questions = len(quiz_data.get("questions", []))
    quiz_time = quiz_data.get("quiz_time", 30)
    bot_username = (await context.bot.get_me()).username

    # join_link: deep link that opens the bot in private chat with the join handler
    # This works in groups too — tapping it opens a DM with the bot, not the raw WebApp URL
    join_link = f"https://t.me/{bot_username}?start=join_battle_{room_id}_{quiz_id}"

    t = SHARING_TRANSLATIONS.get(language, SHARING_TRANSLATIONS['en'])
    
    invite_text = t['invite_text']
    share_url = generate_invite_share_url(join_link, invite_text)

    if chat_type == 'private':
        ROOM_CREATED = {
            'en': (
                f"🎮 <b>Battle Room Created!</b>\n\n"
                f"<b>Quiz:</b> {title}\n"
                f"📊 {num_questions} questions\n"
                f"⏱️ {quiz_time} sec per question\n"
                f"<b>Room ID:</b> <code>{room_id}</code>\n\n"
                f"👇 Share the invite with your opponent, then open your battle room!\n\n"
                f"⚡ First to answer correctly wins the point. Highest score wins!"
            ),
            'uz': (
                f"🎮 <b>Jang Xonasi Yaratildi!</b>\n\n"
                f"<b>Quiz:</b> {title}\n"
                f"📊 {num_questions} ta savol\n"
                f"⏱️ Savollar uchun vaqt: {quiz_time} soniya\n"
                f"<b>Xona ID:</b> <code>{room_id}</code>\n\n"
                f"👇 Raqibingizga taklif yuboring, keyin xonaga kiring va bellashing!\n\n"
                f"⚡ Kim tez va to'g'ri javob bersa — g'alaba uniki!"
            ),
            'ru': (
                f"🎮 <b>Комната для Дуэли Создана!</b>\n\n"
                f"<b>Квиз:</b> {title}\n"
                f"📊 {num_questions} вопросов\n"
                f"⏱️ {quiz_time} сек на вопрос\n"
                f"<b>ID комнаты:</b> <code>{room_id}</code>\n\n"
                f"👇 Отправьте приглашение сопернику, затем оба зайдите и сразитесь!\n\n"
                f"⚡ Кто быстрее и правильнее ответит — тот победит!"
            )
        }

        room_text = ROOM_CREATED.get(language, ROOM_CREATED['en'])

        await query.message.reply_text(
            room_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                # Creator (private chat) opens the WebApp directly
                [InlineKeyboardButton(t['open_room'], web_app=WebAppInfo(url=web_app_url))],
                # Share invite opens Telegram share dialog with pre-filled message
                [InlineKeyboardButton(t['invite'], url=share_url)],
            ])
        )

    else:
        # ── GROUP CHAT ──────────────────────────────────────────────────────
        # FIX: Use join_link (bot deep link) NOT web_app_url.
        # web_app_url is a raw https:// link — Telegram can't open WebApps from
        # plain URLs in groups. The join_link opens the bot in private chat first,
        # which then shows the proper web_app button to open the battle room.
        GROUP_ROOM_CREATED = {
            'en': (
                f"⚔️ <b>Team Battle Started!</b>\n\n"
                f"<b>Quiz:</b> {title}\n"
                f"📊 {num_questions} questions | ⏱️ {quiz_time} sec per question\n\n"
                f"🏆 Team up and compete against each other!\n"
                f"⚡ Answer fast and correctly — your team's glory is on the line!\n\n"
                f"👇 Everyone tap <b>Enter Battle Room</b> to join!"
            ),
            'uz': (
                f"⚔️ <b>Jamoa Jangi Boshlandi!</b>\n\n"
                f"<b>Quiz:</b> {title}\n"
                f"📊 {num_questions} ta savol | ⏱️ {quiz_time} soniya har savol\n\n"
                f"🏆 Jamoangiz bilan birlashib, raqiblaringizni yengish vaqti!\n"
                f"⚡ Tez va to'g'ri javob bering — jamoangiz sha'ni siz bilan!\n\n"
                f"👇 Barcha <b>Jang Xonasiga Kirish</b> tugmasini bosing!"
            ),
            'ru': (
                f"⚔️ <b>Командная Битва Началась!</b>\n\n"
                f"<b>Квиз:</b> {title}\n"
                f"📊 {num_questions} вопросов | ⏱️ {quiz_time} сек на вопрос\n\n"
                f"🏆 Объединитесь с командой и сразитесь с соперниками!\n"
                f"⚡ Отвечайте быстро и правильно — честь команды в ваших руках!\n\n"
                f"👇 Все нажимайте <b>Войти в комнату</b>!"
            )
        }

        room_text = GROUP_ROOM_CREATED.get(language, GROUP_ROOM_CREATED['en'])

        await query.message.reply_text(
            room_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t['enter_room'], url=join_link)],
                [InlineKeyboardButton(t['share_invite_link'], url=share_url)],
            ])
        )


async def handle_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query
    results = []
    logger.info(f"[INLINE QUERY] Received inline query: {query.query}")

    user_id = query.from_user.id
    language = await get_user_language(user_id) or 'en'
    t = SHARING_TRANSLATIONS.get(language, SHARING_TRANSLATIONS['en'])
    
    q = query.query.strip()
    logger.info(f"[INLINE QUERY] After strip: '{q}'")

    uuid_regex = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    is_group_quiz = False
    quiz_id = None

    if q.startswith("quiz_"):
        quiz_id = q[5:]
        is_group_quiz = False

    elif q.startswith("battle_"):
        from src.multiplayer_fight import WEB_APP_URL  
        parts = q.split("_", 2)
        if len(parts) == 3:
            _, room_id, quiz_id = parts
            web_app_url = f"{WEB_APP_URL}?room={room_id}"
            quiz_data = await get_shared_quiz(quiz_id)
            title = quiz_data.get("title", "Quiz") if quiz_data else "Quiz"
            
            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=f"⚔️ 1v1 Battle: {title}",
                    description="Tap to join and compete!",
                    input_message_content=InputTextMessageContent(
                        message_text=f"⚔️ <b>1v1 Quiz Battle!</b>\n\n<b>{title}</b>\n\nJoin my room and let's see who's smarter! 🧠",
                        parse_mode="HTML"
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🎮 Join Battle", web_app=WebAppInfo(url=web_app_url))]
                    ])
                )
            )
    elif q.startswith("groupquiz_"):
        quiz_id = q[len("groupquiz_"):]
        is_group_quiz = True
    elif q.startswith("/groupquiz "):
        quiz_id_candidate = q[len("/groupquiz "):].strip()
        if re.match(uuid_regex, quiz_id_candidate):
            quiz_id = quiz_id_candidate
            is_group_quiz = True
        else:
            logger.info("[INLINE QUERY] Invalid /groupquiz format")
            await query.answer([])
            return
    elif re.match(uuid_regex, q):
        quiz_id = q
        is_group_quiz = True
    else:
        logger.info("[INLINE QUERY] Invalid query format")
        await query.answer([])
        return

    quiz_data = await get_shared_quiz(quiz_id)
    if not quiz_data:
        logger.warning(f"[INLINE QUERY] Quiz not found for quiz_id: {quiz_id}")
        await query.answer([])
        return

    title = quiz_data.get('title', '📝 Multiple Choice Quiz')
    summary = quiz_data.get('summary', '')
    num_questions = len(quiz_data.get("questions", []))
    
    quiz_time = quiz_data.get("quiz_time")
    
    if quiz_time is None:
        try:
            quiz_row = supabase.table(TBL.QUIZZES).select("quiz_time").eq("id", quiz_id).execute()
            if quiz_row.data and len(quiz_row.data) > 0:
                quiz_time = quiz_row.data[0].get("quiz_time", 30)
            else:
                quiz_time = 30
        except Exception as e:
            logger.error(f"[INLINE QUERY] Error fetching quiz_time from database: {e}")
            quiz_time = 30
    
    quiz_time = int(quiz_time) if quiz_time else 30
    quiz_info = quiz_data.get('quiz_info', '')
    quiz_info_display = f"\n\n<b>{t['quiz_info']}</b>\n{quiz_info}" if quiz_info else ""

    if is_group_quiz:
        logger.info(f"[INLINE QUERY] Sending group quiz result for quiz_id: {quiz_id}")
            
        results.append(
            InlineQueryResultArticle(
                id=quiz_id,
                title=f"{t['quiz_prefix']} {title}",
                description=f"{num_questions} {t['click_to_share']}",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"{t['group_quiz_title']} {title}\n\n"
                        f"<b>{t['summary']}</b> {summary}"
                        f"{quiz_info_display}\n\n"
                        f"{t['play_together']}\n"
                        f"{t['questions'].format(num=num_questions)}\n"
                        f"{t['time_per_question'].format(time=quiz_time)}\n\n"
                        f"{t['click_button']}\n\n"
                        f"{t['stop_command']}\n\n"
                        f"{t['start_command']}\n"
                        f"<code>/groupquiz {quiz_id}</code>"
                    ),
                    parse_mode="HTML"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        t['start_group_quiz'], callback_data=f"start_group_quiz_{quiz_id}",
                    )],
                ])
            )
        )

    else:
        logger.info(f"[INLINE QUERY] Sending individual quiz result for quiz_id: {quiz_id}")
        link = generate_share_link(context.bot.username, quiz_id)
        
        quiz_message = (
            f"{t['quiz_ready']}\n\n"
            f"<b>{title}</b>\n\n"
            f"<b>{t['summary']}</b> {summary}"
            f"{quiz_info_display}\n\n"
            f"{t['time_limit']} {quiz_time} seconds per question\n"
            f"{t['num_questions']} {num_questions}"
        )
        
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=title,
                description=summary,
                input_message_content=InputTextMessageContent(
                    message_text=quiz_message,
                    parse_mode="HTML"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(t['start_quiz'], url=link)],
                    [InlineKeyboardButton(t['share_quiz'], switch_inline_query=f"quiz_{quiz_id}")],
                    [InlineKeyboardButton(t['share_to_group'], url=f"https://t.me/{context.bot.username}?startgroup=groupquiz_{quiz_id}")]
                ])
            )
        )
    
    await query.answer(results, cache_time=0)