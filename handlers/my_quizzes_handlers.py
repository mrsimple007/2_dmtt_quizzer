from src.tables import TBL
from src.imports import *
import time
from src.user_management import run_supabase, get_user_language, get_user_quizzes_light, get_shared_quiz
from src.cache import cache_del
from src.async_utils import fire_and_forget
from src.perf_timing import track_handler

MY_QUIZZES_TRANSLATIONS = {
    "en": {
        "title": "📚 *Your Quizzes*\n\nSelect a quiz to view or share:",
        "no_quizzes": "📭 *No Quizzes Yet*\n\nYou haven't created any quizzes yet. Tap '🎯 Create Quiz' to make your first quiz!",
        "quiz_item": "📝 {title}\n❓ {num_questions} questions",
        "back": "🔙 Back to Menu",
        "edit_quiz_info": "✏️ Edit Quiz Info",
        "enter_new_info": "📝 *Edit Quiz Info*\n\nPlease enter the new quiz information:\n\n*Format:*\n```\nTitle: Your Quiz Title\nDescription: Your quiz description\n```\n\nOr tap Skip to keep current info.",
        "quiz_info_updated": "✅ *Quiz Info Updated!*\n\nYour quiz information has been successfully updated.\n\n*Previous:* {old_info}\n*New:* {new_info}",
        "skip": "⏭️ Skip",
        "summary_label": "Summary",
        "quiz_info_label": "Quiz Info",
        "time_label": "Time",
        "questions_label": "Questions",
        "no_time_limit": "No time limit",
        "sec_per_question": "sec per question",
        "choose_option": "Choose an option:",
        'view_results': '📊 View Results'
    },
    "uz": {
        "title": "📚 *Sizning Quizlaringiz*\n\nKo'rish yoki ulashish uchun quizni tanlang:",
        "no_quizzes": "📭 *Sizda Hali Quiz Yo'q*\n\nSiz hali hech qanday quiz yaratmadingiz. Birinchi quizingizni yaratish uchun '🎯 Quiz yaratish' tugmasini bosing!",
        "quiz_item": "📝 {title}\n❓ {num_questions} ta savol",
        "back": "🔙 Menyuga Qaytish",
        "edit_quiz_info": "✏️ Quiz Ma'lumotini Tahrirlash",
        "enter_new_info": "📝 *Quiz Ma'lumotini Tahrirlash*\n\nYangi quiz ma'lumotini kiriting:\n\n*Format:*\n```\nSarlavha: Quiz Sarlavhasi\nTavsif: Quiz tavsifi\n```\n\nYoki joriy ma'lumotni saqlash uchun O'tkazib yuborish tugmasini bosing.",
        "quiz_info_updated": "✅ *Quiz Ma'lumoti Yangilandi!*\n\nQuiz ma'lumotingiz muvaffaqiyatli yangilandi.\n\n*Avvalgi:* {old_info}\n*Yangi:* {new_info}",
        "skip": "⏭️ O'tkazib yuborish",
        "summary_label": "Qisqacha",
        "quiz_info_label": "Quiz Ma'lumoti",
        "time_label": "Vaqt",
        "questions_label": "Savollar",
        "no_time_limit": "Vaqt chegarasiz",
        "sec_per_question": "soniya har bir savol uchun",
        "choose_option": "Variantni tanlang:",
        "view_results": "📊 Natijalarni Ko'rish"
    },
    "ru": {
        "title": "📚 *Ваши Викторины*\n\nВыберите викторину для просмотра или публикации:",
        "no_quizzes": "📭 *Викторин Пока Нет*\n\nВы еще не создали ни одной викторины. Нажмите '🎯 Создать викторину', чтобы создать первую!",
        "quiz_item": "📝 {title}\n❓ {num_questions} вопросов",
        "back": "🔙 Вернуться в меню",
        "edit_quiz_info": "✏️ Редактировать Информацию",
        "enter_new_info": "📝 *Редактирование Информации о Квизе*\n\nВведите новую информацию о квизе:\n\n*Формат:*\n```\nНазвание: Название Квиза\nОписание: Описание квиза\n```\n\nИли нажмите Пропустить, чтобы сохранить текущую информацию.",
        "quiz_info_updated": "✅ *Информация о Квизе Обновлена!*\n\nИнформация о вашем квизе успешно обновлена.\n\n*Предыдущая:* {old_info}\n*Новая:* {new_info}",
        "skip": "⏭️ Пропустить",
        "summary_label": "Краткое описание",
        "quiz_info_label": "Информация о квизе",
        "time_label": "Время",
        "questions_label": "Вопросы",
        "no_time_limit": "Без ограничения времени",
        "sec_per_question": "сек на вопрос",
        "choose_option": "Выберите опцию:",
        'view_results': "📊 Посмотреть результаты"
    }
}

EDIT_QUIZ_INFO = 4



async def handle_split_quiz_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass 

QUIZZES_PER_PAGE = 8
_LIST_TTL = 120 


async def _get_list(user_id: int, context, force: bool = False):
    """Light list kept in user_data (a few KB). It used to hold up to 50 FULL quizzes per user."""
    ud = context.user_data
    lst = ud.get('my_quizzes_list')
    if force or not lst or time.time() - ud.get('my_quizzes_ts', 0) > _LIST_TTL:
        lst = await get_user_quizzes_light(user_id)
        ud['my_quizzes_list'] = lst
        ud['my_quizzes_ts'] = time.time()
    return lst


def _build_page(quizzes, page, t):
    total = len(quizzes)
    total_pages = max(1, (total + QUIZZES_PER_PAGE - 1) // QUIZZES_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * QUIZZES_PER_PAGE

    keyboard = []
    for q in quizzes[start:start + QUIZZES_PER_PAGE]:
        title = (q.get('title') or 'Untitled Quiz')[:30]
        label = t["quiz_item"].format(title=title, num_questions=q.get('question_count') or q.get('num_questions') or "?")
        keyboard.append([InlineKeyboardButton(label, callback_data=f"view_my_quiz_{q['id']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"my_quizzes_page_{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"my_quizzes_page_{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton(t["back"], callback_data="back_to_main_menu")])

    text = t["title"] + f"\n_Page {page + 1}/{total_pages}_"
    return text, InlineKeyboardMarkup(keyboard), page


async def _edit_or_plain(query, text, markup):
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    except Exception as e:
        if "not modified" in str(e).lower():
            return
        logger.warning(f"markdown edit failed ({e}); retrying as plain text")
        await query.edit_message_text(text, reply_markup=markup)


@track_handler("my_quizzes")
async def my_quizzes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    language = await get_user_language(user.id)
    t = MY_QUIZZES_TRANSLATIONS.get(language, MY_QUIZZES_TRANSLATIONS["en"])

    quizzes = await _get_list(user.id, context, force=True)    # always fresh when opened from the menu
    if not quizzes:
        await update.message.reply_text(t["no_quizzes"], parse_mode=ParseMode.MARKDOWN)
        return CONTENT

    context.user_data['my_quizzes_page'] = 0
    text, kb, _ = _build_page(quizzes, 0, t)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    return CONTENT


async def send_quizzes_page(message, context, quizzes, page, t, language=None):
    """Kept for compatibility with any other caller."""
    text, kb, _ = _build_page(quizzes, page, t)
    await message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def handle_my_quizzes_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    fire_and_forget(query.answer())
    user = query.from_user
    language = await get_user_language(user.id)
    t = MY_QUIZZES_TRANSLATIONS.get(language, MY_QUIZZES_TRANSLATIONS["en"])

    page = int(query.data.replace("my_quizzes_page_", ""))
    quizzes = await _get_list(user.id, context)
    text, kb, page = _build_page(quizzes, page, t)
    context.user_data['my_quizzes_page'] = page
    await _edit_or_plain(query, text, kb)
    return CONTENT


async def handle_back_to_my_quizzes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The ONLY definition now. The old second copy used quiz.get('quiz_id') and broke every button."""
    query = update.callback_query
    fire_and_forget(query.answer())
    user = query.from_user
    language = await get_user_language(user.id)
    t = MY_QUIZZES_TRANSLATIONS.get(language, MY_QUIZZES_TRANSLATIONS["en"])

    quizzes = await _get_list(user.id, context)
    if not quizzes:
        await query.edit_message_text(t["no_quizzes"], parse_mode=ParseMode.MARKDOWN)
        return CONTENT
    text, kb, _ = _build_page(quizzes, context.user_data.get('my_quizzes_page', 0), t)
    await _edit_or_plain(query, text, kb)
    return CONTENT

_QT = {
    "button": {"en": "⏱ Change Time", "uz": "⏱ Quiz vaqtni o'zgartirish", "ru": "⏱ Изменить время"},
    "choose": {"en": "⏱ *Select time per question:*",
               "uz": "⏱ *Har bir savol uchun vaqtni tanlang:*",
               "ru": "⏱ *Выберите время на вопрос:*"},
    "done": {"en": "✅ Time updated to {t} sec per question",
             "uz": "✅ Vaqt yangilandi: har bir savol uchun {t} soniya",
             "ru": "✅ Время обновлено: {t} сек на вопрос"},
    "denied": {"en": "⛔ Only the quiz owner can change this.",
               "uz": "⛔ Buni faqat quiz egasi o'zgartira oladi.",
               "ru": "⛔ Изменить может только автор квиза."},
    "back": {"en": "🔙 Back", "uz": "🔙 Orqaga", "ru": "🔙 Назад"},
}
_TIME_OPTIONS = [15, 20, 30, 45, 60, 90, 120]


async def _is_owner(quiz_data, quiz_id, user_id) -> bool:
    owner = quiz_data.get("user_id")
    if owner is None:
        from src.user_management import get_quiz_owner_id
        owner = await get_quiz_owner_id(quiz_id)
    return str(owner) == str(user_id)


async def handle_quiz_time_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    fire_and_forget(query.answer())
    language = await get_user_language(query.from_user.id)
    quiz_id = query.data.replace("qt_menu_", "")

    quiz_data = await get_shared_quiz(quiz_id)
    if not quiz_data:
        await query.edit_message_text("❌ Quiz not found.")
        return CONTENT
    if not await _is_owner(quiz_data, quiz_id, query.from_user.id):
        await query.answer(_QT["denied"].get(language, _QT["denied"]["en"]), show_alert=True)
        return CONTENT

    rows, row = [], []
    for s in _TIME_OPTIONS:
        row.append(InlineKeyboardButton(f"{s}s", callback_data=f"qt_set_{quiz_id}_{s}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(_QT["back"].get(language, "🔙 Back"), callback_data=f"view_my_quiz_{quiz_id}")])

    await query.edit_message_text(_QT["choose"].get(language, _QT["choose"]["en"]),
                                  parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=InlineKeyboardMarkup(rows))
    return CONTENT


async def handle_quiz_time_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    fire_and_forget(query.answer())
    language = await get_user_language(query.from_user.id)

    rest = query.data.replace("qt_set_", "")
    quiz_id, _, secs = rest.rpartition("_")
    try:
        seconds = int(secs)
    except ValueError:
        return CONTENT
    if seconds not in _TIME_OPTIONS:
        return CONTENT

    cached = await get_shared_quiz(quiz_id)
    if not cached:
        await query.edit_message_text("❌ Quiz not found.")
        return CONTENT
    if not await _is_owner(cached, quiz_id, query.from_user.id):
        await query.answer(_QT["denied"].get(language, _QT["denied"]["en"]), show_alert=True)
        return CONTENT

    quiz_data = dict(cached)               # never mutate the cached object
    quiz_data["quiz_time"] = seconds
    await run_supabase(
        lambda: supabase.table(TBL.QUIZZES)
            .update({'quiz_data': quiz_data, 'quiz_time': seconds})
            .eq('id', quiz_id).execute()
    )
    cache_del(("quiz", quiz_id))

    # show the quiz card again, with the new time
    text, kb = _quiz_view(quiz_data, quiz_id, language, context.bot.username)
    note = _QT["done"].get(language, _QT["done"]["en"]).format(t=seconds)
    await _edit_or_plain(query, f"{note}\n\n{text}", kb)
    return CONTENT



def _quiz_view(quiz_data, quiz_id, language, bot_username):
    btn_text = BUTTON_TRANSLATIONS.get(language, BUTTON_TRANSLATIONS["en"])
    t = MY_QUIZZES_TRANSLATIONS.get(language, MY_QUIZZES_TRANSLATIONS["en"])

    title = quiz_data.get("title", "📝 Multiple Choice Quiz")
    summary = quiz_data.get("summary", "")
    num_questions = len(quiz_data.get("questions", []))
    quiz_time = quiz_data.get("quiz_time", 30)
    quiz_info = quiz_data.get("quiz_info", "")

    keyboard = [
        [InlineKeyboardButton(btn_text["start_quiz"], callback_data=f"start_quiz_{quiz_id}"),
         InlineKeyboardButton(btn_text["share_quiz"], switch_inline_query=f"quiz_{quiz_id}")],
        [InlineKeyboardButton(btn_text["share_to_group"],
                              url=f"https://t.me/{bot_username}?startgroup=groupquiz_{quiz_id}"),
         InlineKeyboardButton(t["edit_quiz_info"], callback_data=f"edit_quiz_info_{quiz_id}")],
        [InlineKeyboardButton(t['view_results'], callback_data=f"view_quiz_results_{quiz_id}"),
         InlineKeyboardButton(btn_text["download_word"], callback_data=f"download_quiz_{quiz_id}")],
        [InlineKeyboardButton(_QT["button"].get(language, _QT["button"]["en"]),
                        callback_data=f"qt_menu_{quiz_id}")],
        [InlineKeyboardButton("🔙 Back to My Quizzes", callback_data="back_to_my_quizzes")],
    ]

    time_label = t["no_time_limit"] if quiz_time == 0 else f"{quiz_time} {t['sec_per_question']}"
    info = f"\n\n📝 *{t['quiz_info_label']}:*\n{quiz_info}" if quiz_info else ""
    text = (f"*{title}*\n\n📝 *{t['summary_label']}:* {summary}{info}\n\n"
            f"⏱️ *{t['time_label']}:* {time_label}\n"
            f"❓ *{t['questions_label']}:* {num_questions}\n\n{t['choose_option']}")
    return text, InlineKeyboardMarkup(keyboard)


async def handle_view_my_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    fire_and_forget(query.answer())
    user = query.from_user
    language = await get_user_language(user.id)

    quiz_id = query.data.replace("view_my_quiz_", "")
    quiz_data = await get_shared_quiz(quiz_id)
    if not quiz_data:
        await query.edit_message_text("❌ Quiz not found.")
        return CONTENT

    context.user_data['editing_quiz_id'] = quiz_id
    text, kb = _quiz_view(quiz_data, quiz_id, language, context.bot.username)   # no get_me() call
    await _edit_or_plain(query, text, kb)
    return CONTENT


async def handle_edit_quiz_info_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    fire_and_forget(query.answer())
    language = await get_user_language(query.from_user.id)
    t = MY_QUIZZES_TRANSLATIONS.get(language, MY_QUIZZES_TRANSLATIONS["en"])

    context.user_data['editing_quiz_id'] = query.data.replace("edit_quiz_info_", "")
    context.user_data['busy'] = False
    context.user_data['awaiting_quiz_info_edit'] = True

    kb = InlineKeyboardMarkup([[InlineKeyboardButton(t["skip"], callback_data="skip_edit_quiz_info")]])
    await query.edit_message_text(t["enter_new_info"], parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    return EDIT_QUIZ_INFO


async def receive_edited_quiz_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    language = await get_user_language(user.id)
    t = MY_QUIZZES_TRANSLATIONS.get(language, MY_QUIZZES_TRANSLATIONS["en"])

    context.user_data.pop('awaiting_quiz_info_edit', None)
    quiz_id = context.user_data.get('editing_quiz_id')
    if not quiz_id:
        await update.message.reply_text("❌ Error: Quiz ID not found.")
        return CONTENT

    new_info = (update.message.text or "").strip()
    if not new_info:
        return CONTENT

    try:
        cached = await get_shared_quiz(quiz_id)
        if not cached:
            await update.message.reply_text("❌ Quiz not found.")
            return CONTENT
        quiz_data = dict(cached)         # copy: never mutate the cached object

        old_title = quiz_data.get('title', 'Untitled')
        old_display = old_title.split(' - Part ')[0]
        part_suffix = (' - Part ' + old_title.split(' - Part ')[-1]) if ' - Part ' in old_title else ''

        new_title = new_info + part_suffix
        quiz_data['title'] = new_title
        quiz_data['quiz_info'] = new_info

        await run_supabase(                              # was a blocking call
            lambda: supabase.table(TBL.QUIZZES)
                .update({'quiz_data': quiz_data, 'title': new_title})
                .eq('id', quiz_id).execute()
        )
        cache_del(("quiz", quiz_id))                     # next read gets the new data
        context.user_data.pop('my_quizzes_list', None)   # the list shows titles

        try:
            await update.message.reply_text(
                t["quiz_info_updated"].format(old_info=old_display, new_info=new_info),
                parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text("✅ Quiz info updated.")

        return await show_updated_quiz(update, context, quiz_id, language)

    except Exception as e:
        logger.error(f"Error updating quiz info: {e}", exc_info=True)
        await update.message.reply_text("❌ Error updating quiz info.")
        return CONTENT


async def handle_skip_edit_quiz_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    fire_and_forget(query.answer())
    context.user_data.pop('awaiting_quiz_info_edit', None)
    quiz_id = context.user_data.get('editing_quiz_id')
    language = await get_user_language(query.from_user.id)
    return await show_updated_quiz(update, context, quiz_id, language)


async def show_updated_quiz(update, context, quiz_id, language):
    quiz_data = await get_shared_quiz(quiz_id) if quiz_id else None
    target = update.callback_query.message if update.callback_query else update.message

    if not quiz_data:
        await target.reply_text("❌ Quiz not found.")
        return CONTENT

    text, kb = _quiz_view(quiz_data, quiz_id, language, context.bot.username)
    try:
        await target.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception:
        await target.reply_text(text, reply_markup=kb)
    return CONTENT