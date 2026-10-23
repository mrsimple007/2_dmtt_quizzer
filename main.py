from email.mime import application
from handlers.main_commands import admin_daily_command, admin_monthly_command, admin_update_groups
from src.imports import *
from handlers.start_handler import *
from handlers.sharing_quiz import *
from handlers.settings_button import *
from handlers.group_sharing import *
from src.quiz_service import *
from handlers.subscribe import *
from handlers.leaderboard import leaderboard_command, leaderboard_callback_handler
from handlers.manual_payment import *
from auto_message_sender import *
from handlers.quiz_splitter import *
from handlers.quiz_split_handlers import *
from handlers.quiz_results_handlers import *
from telegram import WebAppInfo
from handlers.my_quizzes_handlers import EDIT_QUIZ_INFO, receive_edited_quiz_info, handle_skip_edit_quiz_info, handle_view_my_quiz, handle_back_to_my_quizzes, handle_edit_quiz_info_button, handle_my_quizzes_page
from src.perf_timing import track_handler, timed, loop_lag_monitor, patch_telegram_http
from src.async_utils import fire_and_forget
from src.user_management import (
    get_user_profile, get_user_language, get_user_quiz_type, get_user_quiz_time,
    get_user_quiz_questions, get_account_snapshot, get_user_stats, get_user_balance,
    refund_balance,
)

from telegram.ext import TypeHandler
from src.cache import cache_sweeper
from src.memory_guard import touch_user, janitor, memory_monitor

async def _post_init(app):
    asyncio.create_task(loop_lag_monitor())
    asyncio.create_task(cache_sweeper())
    asyncio.create_task(janitor(app))
    asyncio.create_task(memory_monitor(app))


ASK_QUIZ_INFO = 3
FREE_QUIZZES_BEFORE_PAYMENT = 3   # see the note on the 3-vs-1 inconsistency at the end
def _md_escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace("_", "\\_").replace("*", "\\*")
                .replace("`", "\\`").replace("[", "\\[").replace("]", "\\]"))

from telegram import ReplyKeyboardRemove
from telegram.ext import ApplicationHandlerStop
from src.imports import is_free_user


async def free_users_only_gate(update, context):
    # Votes, poll updates, chat-member events etc. are not "private chat usage"
    if update.poll_answer or update.poll or update.my_chat_member or update.chat_member:
        return

    user = update.effective_user
    chat = update.effective_chat


    # Nothing to gate: no user, or not a private chat (groups pass through)
    if user is None:
        return
    if chat and chat.type != "private":
        return

    # Whitelisted users and admins go through to the normal handlers
    if is_free_user(user.id) or user.id in NOTIFICATION_ADMIN_IDS:
        return

    # Everyone else is blocked
    try:
        if update.callback_query:
            await update.callback_query.answer()
        elif update.message:
            from handlers.start_handler import MAIN_MENU_TRANSLATIONS, sanitize_name
            lang = (user.language_code or "uz")[:2]
            if lang not in MAIN_MENU_TRANSLATIONS:
                lang = "uz"
            text = MAIN_MENU_TRANSLATIONS[lang]["welcome_message"].format(
                name=sanitize_name(user.first_name))
            await update.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardRemove(),
            )
    except Exception as e:
        logger.warning(f"[GATE] failed for {user.id}: {e}")

    raise ApplicationHandlerStop

def _language_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [("🌐 Auto Detect", "auto"), ("🇺🇿 Uzbek", "uz")],
        [("🇬🇧 English", "en"), ("🇷🇺 Russian", "ru")],
        [("🇩🇪 German", "de"), ("🇫🇷 French", "fr")],
        [("🇪🇸 Spanish", "es"), ("🇸🇦 Arabic", "ar")],
        [("🇰🇷 Korean", "ko"), ("🇨🇳 Chinese", "zh")],
        [("🇮🇳 Hindi", "hi"), ("🇧🇩 Bengali", "bn")],
        [("🇵🇰 Urdu", "ur")],
    ]
    kb = [[InlineKeyboardButton(label, callback_data=f"quiz_lang_{code}") for label, code in row]
          for row in rows]
    kb.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main_menu")])
    return InlineKeyboardMarkup(kb)

async def get_quiz_gate(user_id: int, quiz_questions: int = None) -> dict:
    """
    Everything the 'may this user create a quiz?' check needs, from ONE query.
    Before: ~6 sequential DB calls, copied in 3 places.
    """
    from payment_integration_new import get_quiz_price
    from handlers.premium import parse_subscription, parse_daily_free

    quiz_questions = quiz_questions or await get_user_quiz_questions(user_id) or 10
    price = get_quiz_price(quiz_questions)          # kopecks

    gate = {"blocked": False, "balance": 0, "price": price, "total_quizzes": 0,
            "is_premium": False, "has_free": False, "free_info": {"used": 0, "available": 0}}
    from src.imports import is_free_user
    if is_free_user(user_id):
        return gate          # blocked=False: free users are never asked for balance

    try:
        with timed("gate: account snapshot"):
            snap = await get_account_snapshot(user_id)
    except Exception as e:
        # Fail OPEN: a DB hiccup must not tell the user "insufficient balance".
        # The real charge still happens later in process_content.
        logger.error(f"[GATE] snapshot failed for {user_id}: {e}")
        return gate

    gate["balance"] = snap.get("balance") or 0
    gate["total_quizzes"] = snap.get("total_quizzes") or 0
    gate["is_premium"] = bool(parse_subscription(snap).get("is_active"))
    if gate["is_premium"]:
        gate["free_info"] = parse_daily_free(snap)
    gate["has_free"] = gate["free_info"].get("available", 0) > 0
    gate["blocked"] = (not gate["has_free"]
                       and gate["total_quizzes"] >= FREE_QUIZZES_BEFORE_PAYMENT
                       and gate["balance"] < price)
    return gate


def insufficient_balance_payload(language: str, gate: dict):
    tr = INSUFFICIENT_BALANCE_TRANSLATIONS.get(language, INSUFFICIENT_BALANCE_TRANSLATIONS['en'])
    text = tr["insufficient_balance"].format(
        current_balance=int(gate["balance"] // 100), required=int(gate["price"] // 100))
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(tr["topup_button"], callback_data="topup_balance")],
        [InlineKeyboardButton(tr["share_earn"], callback_data="share")],
    ])
    return text, kb


async def _send_language_selection(send, language, extracted_text, gate=None):
    """`send` is update.message.reply_text or a bot.send_message partial. Shows preview + language buttons."""
    preview = extracted_text[:150] + "..." if len(extracted_text) > 150 else extracted_text
    preview = _md_escape(preview)

    free_quiz_text = ""
    if gate and gate.get("has_free"):
        free_quiz_translations = {
            'en': "\n\n🎁 **Free quiz available!** ({used}/3 used today)",
            'uz': "\n\n🎁 **Bepul quiz mavjud!** ({used}/3 bugun ishlatildi)",
            'ru': "\n\n🎁 **Доступна бесплатная викторина!** ({used}/3 использовано сегодня)",
        }
        free_quiz_text = free_quiz_translations.get(language, free_quiz_translations['en']).format(
            used=gate["free_info"].get("used", 0))

    reply_markup = _language_keyboard()
    try:
        await send(
            text=(f"✅ *{TRANSLATIONS[language]['content_extracted']}*\n\n"
                  f"*{TRANSLATIONS[language]['preview']}:*\n"
                  f"```\n{preview}\n```\n\n"
                  f"*Select quiz language:*{free_quiz_text}"),
            parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error sending language selection: {e}")
        await send(
            text=f"✅ *{TRANSLATIONS[language]['content_extracted']}*\n\n*Select quiz language:*",
            parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)



@track_handler("handle_content") 
@track_handler("handle_content")
async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from handlers.my_quizzes_handlers import my_quizzes_command

    user = update.effective_user
    language = await get_user_language(user.id)          # cached

    fire_and_forget(update.message.reply_chat_action("typing"))     # was awaited

    if context.user_data.get('awaiting_quiz_info_edit'):
        from handlers.my_quizzes_handlers import receive_edited_quiz_info
        return await receive_edited_quiz_info(update, context)

    if context.user_data.get('awaiting_receipt'):
        from handlers.manual_payment import handle_receipt_submission
        await handle_receipt_submission(update, context)
        return CONTENT

    if not language and update.message.text and not update.message.text.startswith('/'):
        start_messages = {
            'en': "👉 Please start the bot first with /start, then send your topic.",
            'uz': "👉 Avval /start bilan botni boshlang va keyin mavzuni bering.",
            'ru': "👉 Сначала запустите бота командой /start, затем отправьте тему."
        }
        await update.message.reply_text("\n".join(start_messages.values()), parse_mode=ParseMode.HTML)
        return CONTENT

    # ---------------- menu buttons ----------------
    if update.message.text:
        menu_commands = [
            "🎯 Create Quiz", "⚙️ Settings", "❓ Help", "💰 Balance", "🔗 Share & Earn",
            "🎯 Quiz yaratish", "⚙️ Sozlamalar", "❓ Yordam", "💰 Balans", "🔗 Ulashing va bepul quiz",
            '🎯 Создать викторину', '⚙️ Настройки', '❓ Помощь', '💰 Баланс', '🔗 Поделиться и заработать',
            '📂 Split Quiz Hemis', "📂 Hemis quizni bo'lish", '📂 Разделить Квиз Hemis',
            "↩️ Back to Menu", "↩️ Menyuga Qaytish", "↩️ Вернуться в меню",
            "📚 My Quizzes", "📚 Mening Quizlarim", "📚 Мои Викторины",
        ]
        text_in = update.message.text

        if text_in in menu_commands:
            context.user_data['busy'] = False
            from payment_integration_new import balance_command

            if "Create Quiz" in text_in or "Quiz yaratish" in text_in or "Создать викторину" in text_in:
                for k in ('extracted_text', 'quiz_questions', 'quiz_time', 'detected_language'):
                    context.user_data.pop(k, None)
                t = MAIN_MENU_TRANSLATIONS.get(language, MAIN_MENU_TRANSLATIONS["en"])
                await update.message.reply_text(t["send_document"], parse_mode=ParseMode.HTML)
                return CONTENT

            elif "My Quizzes" in text_in or "Mening Quizlarim" in text_in or "Мои Викторины" in text_in:
                await my_quizzes_command(update, context)
                return CONTENT

            elif "Back" in text_in or "Menyuga" in text_in or "Вернуться" in text_in:
                context.user_data.pop('extracted_text', None)
                context.user_data.pop('split_quizzes', None)
                context.user_data['busy'] = False
                from handlers.start_handler import start
                await start(update, context)
                return CONTENT

            elif "Settings" in text_in or "Sozlamalar" in text_in or "Настройки" in text_in:
                from handlers.settings_button import settings_command
                await settings_command(update, context)
                return CONTENT

            elif "Help" in text_in or "Yordam" in text_in or "Помощь" in text_in:
                await help_command(update, context)
                return CONTENT

            elif "Balance" in text_in or "Balans" in text_in or "Баланс" in text_in:
                await balance_command(update, context)
                return CONTENT

            elif ("Split Quiz Hemis" in text_in or "Hemis quizni bo'lish" in text_in
                  or "Разделить Квиз Hemis" in text_in):
                from handlers.quiz_split_handlers import start_split_quiz
                return await start_split_quiz(update, context)

            elif ("Share & Earn" in text_in or "Ulashing va bepul quiz" in text_in
                  or "Поделиться и заработать" in text_in):
                await share_main(update, context)
                return CONTENT

            return CONTENT

        if text_in.startswith('/start'):
            context.user_data.clear()
            context.user_data['busy'] = False
            return CONTENT

        if text_in.startswith('/'):
            context.user_data['busy'] = False
            return CONTENT

    if context.user_data.get('busy'):
        logger.info(f"⏭️ User {user.id} is busy processing, rejecting new message")
        return CONTENT

    extracted_text = ""
    # 3 sequential cached lookups. They cost 0 DB calls now.
    file_info = {
        'user_id': user.id,
        'quiz_type': await get_user_quiz_type(user.id),
        'quiz_time': await get_user_quiz_time(user.id),
        'quiz_questions': await get_user_quiz_questions(user.id),
        'status': 'pending'
    }

    # ---------------- video ----------------
    if update.message.video:
        coming_soon_messages = {
            'en': ("🎥 *Video Processing - Coming Soon!*\n\n"
                   "We're currently working on video processing features. We'll announce when it's ready!\n\n"
                   "👉 Send /start to restart the bot\n📢 Join @SimpleLearnUz for updates"),
            'uz': ("🎥 *Video qayta ishlash - Tez orada!*\n\n"
                   "Hozirda video qayta ishlash xususiyati ustida ishlayapmiz. Tayyor bo'lganda e'lon qilamiz!\n\n"
                   "👉 Botni qayta ishga tushirish uchun /start yuboring\n"
                   "📢 Yangiliklar uchun @SimpleLearnUz kanaliga qo'shiling"),
            'ru': ("🎥 *Обработка видео - Скоро!*\n\n"
                   "Мы работаем над функцией обработки видео. Объявим, когда будет готово!\n\n"
                   "👉 Отправьте /start для перезапуска бота\n"
                   "📢 Присоединяйтесь к @SimpleLearnUz для обновлений"),
        }
        await update.message.reply_text(coming_soon_messages.get(language, coming_soon_messages['en']),
                                        parse_mode=ParseMode.MARKDOWN)
        return CONTENT

    # ---------------- images ----------------
    if update.message.photo or (update.message.document and update.message.document.mime_type
                                and update.message.document.mime_type.startswith("image/")):
        context.user_data['busy'] = True
        t = MAIN_MENU_TRANSLATIONS.get(language, MAIN_MENU_TRANSLATIONS["en"])
        status_message = await update.message.reply_text(t["processing"], parse_mode=ParseMode.MARKDOWN)
        try:
            if update.message.photo:
                file = await context.bot.get_file(update.message.photo[-1].file_id)
            else:
                file = await context.bot.get_file(update.message.document.file_id)
            file_bytes = await file.download_as_bytearray()

            from src.image_processing import process_image_file
            with timed("image OCR"):
                success, extracted_text, _ = await process_image_file(bytes(file_bytes), user_id=user.id)

            try:
                await status_message.delete()
            except Exception as e:
                logger.error(f"Error deleting status message: {e}")

            if not success or not extracted_text:
                context.user_data['busy'] = False
                await update.message.reply_text(
                    "❌ Could not extract text from image. Please try a clearer image.",
                    parse_mode=ParseMode.MARKDOWN)
                return CONTENT
            extracted_text = extracted_text.strip()

        except Exception as e:
            logger.error(f"Error processing image: {e}")
            try:
                await status_message.delete()
            except Exception:
                pass
            context.user_data['busy'] = False
            await update.message.reply_text(
                f"❌ *Error Processing Image*\n\nAn error occurred: {str(e)}",
                parse_mode=ParseMode.MARKDOWN)
            return CONTENT

    # ---------------- audio / voice ----------------
    elif update.message.voice or update.message.audio:
        context.user_data['busy'] = True
        MAX_AUDIO_SIZE = 5 * 1024 * 4096
        audio_obj = update.message.voice or update.message.audio
        audio_size = audio_obj.file_size

        if audio_size > MAX_AUDIO_SIZE:
            context.user_data['busy'] = False
            await update.message.reply_text(
                f"⚠️ *Audio Too Large*\n\nThe audio file is {audio_size / 1024 / 1024:.2f} MB, "
                f"which exceeds the maximum allowed size of 5 MB. Please upload a smaller audio file.",
                parse_mode=ParseMode.MARKDOWN)
            return CONTENT

        status_message = await update.message.reply_text(
            get_translation(language, "transcribing"), parse_mode=ParseMode.MARKDOWN)
        try:
            file = await context.bot.get_file(audio_obj.file_id)
            file_bytes = await file.download_as_bytearray()

            from src.audio_processing import extract_text_from_audio
            with timed("audio transcription"):
                success, message, transcript_text = await extract_text_from_audio(file_bytes, ELEVENLABS_API_KEY)

            try:
                await status_message.delete()
            except Exception as e:
                logger.error(f"Error deleting status message: {e}")

            if not success:
                context.user_data['busy'] = False
                await update.message.reply_text(f"❌ *Transcription Error*\n\n{message}",
                                                parse_mode=ParseMode.MARKDOWN)
                return CONTENT
            if not transcript_text:
                context.user_data['busy'] = False
                await update.message.reply_text(
                    "❌ *No Text Extracted*\n\nCould not extract any text from the audio. "
                    "Please try a different audio file.", parse_mode=ParseMode.MARKDOWN)
                return CONTENT

            extracted_text = transcript_text
            file_info.update({
                'file_name': getattr(audio_obj, 'file_name', None) or 'audio', 'file_type': 'audio',
                'file_size': audio_size, 'content_type': audio_obj.mime_type, 'status': 'success',
                'processed_at': datetime.now(timezone.utc).isoformat()
            })

        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            try:
                await status_message.delete()
            except Exception:
                pass
            context.user_data['busy'] = False
            await update.message.reply_text(
                f"❌ *Error Processing Audio*\n\nAn error occurred: {str(e)}",
                parse_mode=ParseMode.MARKDOWN)
            return CONTENT

    # ---------------- documents (pdf / word / txt / excel) ----------------
    # `and not extracted_text`: an image sent as a FILE was already handled above.
    if update.message.document and not extracted_text:
        document = update.message.document
        if document.file_size > 15 * 1024 * 1024:
            await update.message.reply_text(
                TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("too_large"),
                parse_mode=ParseMode.MARKDOWN)
            return CONTENT

        file_name = document.file_name or ""
        file_ext = os.path.splitext(file_name)[1].lower() if file_name else ""
        logger.info(f"📄 Detected type: DOCUMENT ({file_ext}) from user {user.id}")

        if file_ext in ['.pdf', '.docx', '.doc', '.txt', '.xlsx', '.xls']:
            # ONE query replaces get_user_stats + get_user_quiz_questions + get_user_balance
            gate = await get_quiz_gate(user.id)
            if gate["blocked"]:
                text, kb = insufficient_balance_payload(language, gate)
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
                return CONTENT

            context.user_data['busy'] = True
            t = MAIN_MENU_TRANSLATIONS.get(language, MAIN_MENU_TRANSLATIONS["en"])
            status_message = await update.message.reply_text(t["processing"], parse_mode=ParseMode.MARKDOWN)

            asyncio.create_task(_process_document_background(
                context=context, user_id=user.id, chat_id=update.message.chat_id,
                file_id=document.file_id, file_ext=file_ext, file_name=file_name,
                file_info=file_info, language=language,
                status_message_id=status_message.message_id, document=document))
            return CONTENT
        else:
            await update.message.reply_text(
                TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("unsupported"),
                parse_mode=ParseMode.MARKDOWN)
            return CONTENT

    # ---------------- text / URL ----------------
    elif update.message.text:
        text = update.message.text

        if text.startswith(('http://', 'https://')) or any(text.startswith(p) for p in ['www.', 'youtu.be/']):
            context.user_data['busy'] = True
            t = MAIN_MENU_TRANSLATIONS.get(language, MAIN_MENU_TRANSLATIONS["en"])
            if not text.startswith(('http://', 'https://')):
                text = 'https://' + text.replace('www.', '', 1) if text.startswith('www.') else 'https://' + text

            status_message = await update.message.reply_text(t["processing"], parse_mode=ParseMode.MARKDOWN)
            try:
                with timed("URL extraction"):
                    extracted_text = await extract_text_from_url(text)
                if extracted_text.startswith("Error:") or "Failed to retrieve content from URL" in extracted_text:
                    try:
                        await status_message.delete()
                    except Exception:
                        pass
                    context.user_data['busy'] = False
                    await update.message.reply_text(
                        f"⚠️ *URL Access Issue*\n\n{extracted_text}\n\nPlease check if:\n"
                        f"• The URL is correct\n• The website allows access\n• The site isn't behind a login",
                        parse_mode=ParseMode.MARKDOWN)
                    return CONTENT
                file_info.update({
                    'file_name': text, 'file_type': 'url', 'file_size': len(text),
                    'content_type': 'text/url', 'status': 'success',
                    'processed_at': datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                logger.error(f"Error processing URL: {e}")
                try:
                    await status_message.delete()
                except Exception:
                    pass
                context.user_data['busy'] = False
                await update.message.reply_text(
                    f"❌ *Error Processing URL*\n\nI encountered an issue: `{str(e)}`\nPlease try a different URL.",
                    parse_mode=ParseMode.MARKDOWN)
                return CONTENT
            try:
                await status_message.delete()
            except Exception:
                pass
        else:
            context.user_data['busy'] = True
            extracted_text = text
            file_info.update({
                'file_name': 'text_message', 'file_type': 'text', 'file_size': len(text),
                'content_type': 'text/plain', 'status': 'success',
                'processed_at': datetime.now(timezone.utc).isoformat()
            })

    # ---------------- common: clean, check, show language selection ----------------
    if extracted_text:
        extracted_text = re.sub(r'\s+', ' ', extracted_text).strip()

        MAX_CONTENT_LENGTH = 10000
        if len(extracted_text) > MAX_CONTENT_LENGTH:
            extracted_text = truncate_content_for_processing(extracted_text, MAX_CONTENT_LENGTH)
            extracted_text = re.sub(r'\s+', ' ', extracted_text).strip()

        if len(extracted_text) < 5:
            context.user_data['busy'] = False
            await update.message.reply_text(
                TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("content_too_short"),
                parse_mode=ParseMode.MARKDOWN)
            return CONTENT

        context.user_data['extracted_text'] = extracted_text

        # ONE query (was: stats + questions + balance + subscription + daily-free = ~6 calls)
        gate = await get_quiz_gate(user.id)
        if gate["blocked"]:
            context.user_data['busy'] = False
            text_msg, kb = insufficient_balance_payload(language, gate)
            await update.message.reply_text(text_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
            return CONTENT

        await _send_language_selection(
            lambda **kw: update.message.reply_text(**kw), language, extracted_text, gate)
        return PROCESSING

    return CONTENT


@track_handler("lang_select")
async def handle_language_detect_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    
    # ✅ FIX: Only process quiz_lang_ callbacks
    if not query.data.startswith("quiz_lang_"):
        return PROCESSING
    
    selected_lang = query.data.split("_")[-1]
    
    # Detect language and store ONLY for quiz generation
    if selected_lang == "auto":
        extracted_text = context.user_data.get('extracted_text', '')
        if not extracted_text:
            await query.message.reply_text("❌ No content found. Please start over with /start")
            return CONTENT
        
        detected_language = detect_language(extracted_text)
        context.user_data['detected_language'] = detected_language
    else:
        lang_mapping = {
            'uz': 'uz',
            'en': 'en', 
            'ru': 'ru',
            'de': 'de',
            'fr': 'fr',
            'es': 'es',
            'ar': 'ar',
            'ko': 'ko',
            'zh': 'zh',
            'hi': 'hi',
            'bn': 'bn',
            'ur': 'ur'
        }
        detected_language = lang_mapping.get(selected_lang, 'en')
        context.user_data['detected_language'] = detected_language
    
    # Get preview
    extracted_text = context.user_data.get('extracted_text', '')
    if not extracted_text:
        await query.message.reply_text("❌ No content found. Please start over with /start")
        return CONTENT
        
    preview = extracted_text[:150] + "..." if len(extracted_text) > 150 else extracted_text
    preview = preview.replace("\\", "\\\\").replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[").replace("]", "\\]")

    from handlers.premium import get_user_subscription
    
    # Check if user has premium
    subscription = await get_user_subscription(user.id)
    is_premium = subscription["is_active"]

    if is_premium:
        keyboard = [
            [
                InlineKeyboardButton("5", callback_data="set_questions_5"),
                InlineKeyboardButton("10", callback_data="set_questions_10"),
                InlineKeyboardButton("15", callback_data="set_questions_15"),
            ],
            [
                InlineKeyboardButton("20", callback_data="set_questions_20"),
                InlineKeyboardButton("25", callback_data="set_questions_25"),
                InlineKeyboardButton("30", callback_data="set_questions_30"),
            ],
            [
                InlineKeyboardButton("40 🌟", callback_data="set_questions_40"),
                InlineKeyboardButton("50 🌟", callback_data="set_questions_50"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_language_select")
            ]
        ]
    else:       
        keyboard = [
            [
                InlineKeyboardButton("5 questions", callback_data="set_questions_5"),
                InlineKeyboardButton("10 questions", callback_data="set_questions_10"),
                InlineKeyboardButton("15 questions", callback_data="set_questions_15"),
            ],
            [
                InlineKeyboardButton("20 questions", callback_data="set_questions_20"),
                InlineKeyboardButton("25 questions", callback_data="set_questions_25"),
                InlineKeyboardButton("30 questions", callback_data="set_questions_30"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_language_select")
            ]
        ]

    # ✅ FIX: reply_markup is now always assigned regardless of premium status
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            text=(
                f"✅ *{TRANSLATIONS[language]['content_extracted']}*\n\n"
                f"*{TRANSLATIONS[language]['preview']}:*\n"
                f"```\n{preview}\n```\n\n"
                f"📚 *Quiz Language:* {detected_language.upper()}\n\n"
                f"*{TRANSLATIONS[language]['choose_num_questions']}*"
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
    
    return PROCESSING


async def handle_back_to_language_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    extracted_text = context.user_data.get('extracted_text', '')
    preview = extracted_text[:150] + "..." if len(extracted_text) > 150 else extracted_text
    preview = preview.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[").replace("]", "\\]")

    keyboard = [
        [
            InlineKeyboardButton("🌐 Auto Detect", callback_data="quiz_lang_auto"),
            InlineKeyboardButton("🇺🇿 Uzbek", callback_data="quiz_lang_uz"),
        ],
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="quiz_lang_en"),
            InlineKeyboardButton("🇷🇺 Russian", callback_data="quiz_lang_ru"),
        ],
        [
            InlineKeyboardButton("🇩🇪 German", callback_data="quiz_lang_de"),
            InlineKeyboardButton("🇫🇷 French", callback_data="quiz_lang_fr"),
        ],
        [
            InlineKeyboardButton("🇪🇸 Spanish", callback_data="quiz_lang_es"),
            InlineKeyboardButton("🇸🇦 Arabic", callback_data="quiz_lang_ar"),
        ],
        [
            InlineKeyboardButton("🇰🇷 Korean", callback_data="quiz_lang_ko"),
            InlineKeyboardButton("🇨🇳 Chinese", callback_data="quiz_lang_zh"),
        ],
        [
            InlineKeyboardButton("🇮🇳 Hindi", callback_data="quiz_lang_hi"),
            InlineKeyboardButton("🇧🇩 Bengali", callback_data="quiz_lang_bn"),
        ],
        [
            InlineKeyboardButton("🇵🇰 Urdu", callback_data="quiz_lang_ur"),
        ],
        [
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            text=(
                f"✅ *{TRANSLATIONS[language]['content_extracted']}*\n\n"
                f"*{TRANSLATIONS[language]['preview']}:*\n"
                f"```\n{preview}\n```\n\n"
                f"*Select quiz language:*"
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
    
    return PROCESSING


async def send_countdown_and_start_quiz(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
    quiz_data: dict,
    language: str
):
    """Send countdown in background without blocking other users."""
    try:
        countdown_texts = COUNTDOWN_TRANSLATIONS.get(language, COUNTDOWN_TRANSLATIONS['en'])
        
        # Send initial message
        status_message = await context.bot.send_message(
            chat_id=chat_id,
            text=countdown_texts['ready'],
            parse_mode="HTML"
        )
        
        await asyncio.sleep(1)
        await status_message.edit_text(countdown_texts['set'], parse_mode="HTML")
        
        await asyncio.sleep(1)
        await status_message.edit_text(countdown_texts['go'], parse_mode="HTML")
        
        await asyncio.sleep(1)
        
        # Delete countdown message
        try:
            await status_message.delete()
        except Exception as e:
            logger.error(f"Error deleting countdown message: {e}")
        
        # Start quiz
        await send_next_question(update, context, user_id, quiz_data, 0)
        
    except Exception as e:
        logger.error(f"Error in countdown: {e}")


async def handle_back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    
    # Clear any stored content data
    context.user_data.pop('extracted_text', None)
    context.user_data.pop('quiz_questions', None)
    context.user_data['busy'] = False
    
    # Show main menu
    await show_main_menu_with_welcome(update, context, user, language or "en")
    
    return CONTENT


async def _generate_and_send_quiz_background(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int, extracted_text: str,
    detected_language: str, quiz_type: str, language: str, quiz_questions: int,
    quiz_time: int, file_info: Dict, processing_message_id: int
):
    delivered = False
    try:
        from handlers.my_quizzes_handlers import MY_QUIZZES_TRANSLATIONS
        logger.info(f"[BACKGROUND QUIZ] Starting generation for user {user_id}")

        with timed("quiz: AI generate_quiz"):
            # 4th argument is the USER ID (the old call passed `language` here by mistake)
            success, message, quiz_data = await generate_quiz(
                extracted_text, quiz_type, detected_language, user_id, num_questions=quiz_questions)

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=processing_message_id)
        except Exception as e:
            logger.error(f"Error deleting processing message: {e}")

        file_info['processed_at'] = datetime.now(timezone.utc).isoformat()
        file_info['status'] = 'success' if success else 'error'
        file_info['error_message'] = None if success else message
        fire_and_forget(save_file_info(file_info))               # nobody waits for this

        if not success:
            await context.bot.send_message(chat_id=chat_id,
                                           text=f"❌ *Quiz Generation Error*\n\n{message}",
                                           parse_mode=ParseMode.MARKDOWN)
            return          # `finally` refunds

        context.user_data['current_quiz'] = quiz_data

        if quiz_type == "mc":
            quiz_info = context.user_data.get('quiz_info', '')

            if quiz_info:
                custom_title = custom_description = None
                for line in quiz_info.split('\n'):
                    low = line.lower()
                    if low.startswith(('title:', 'sarlavha:', 'название:')):
                        custom_title = line.split(':', 1)[1].strip()
                    elif low.startswith(('description:', 'tavsif:', 'описание:')):
                        custom_description = line.split(':', 1)[1].strip()
                title = custom_title or quiz_data.get("title", "📝 *Multiple Choice Quiz*")
                summary = custom_description or quiz_data.get("summary", "")
                quiz_data["quiz_info"] = quiz_info
                if custom_title:
                    quiz_data["title"] = custom_title
                if custom_description:
                    quiz_data["summary"] = custom_description
            else:
                title = quiz_data.get("title", "📝 *Multiple Choice Quiz*")
                summary = quiz_data.get("summary", "")

            actual_quiz_time = context.user_data.get('quiz_time', quiz_time)
            quiz_data["quiz_time"] = actual_quiz_time

            with timed("quiz: save_shared_quiz"):
                quiz_id = await save_shared_quiz(quiz_data, user_id, bot=context.bot)
            context.user_data['current_quiz_id'] = quiz_id

            # the multiplayer room used to be created here but its button was commented out,
            # so it cost a network call for nothing. handle_create_1v1 creates rooms on demand.

            fire_and_forget(update_quiz_stats(user_id, False))
            # fire_and_forget(log_quiz_activity(user_id, context))

            bot_username = context.bot.username or (await context.bot.get_me()).username
            lang = language if language in ["en", "uz", "ru"] else "en"
            btn_text = BUTTON_TRANSLATIONS[lang]

            keyboard = [
                [InlineKeyboardButton(btn_text["start_quiz"], callback_data=f"start_quiz_{quiz_id}")],
                [InlineKeyboardButton(btn_text["share_quiz"], switch_inline_query=f"quiz_{quiz_id}")],
                [InlineKeyboardButton(btn_text["share_to_group"],
                                      url=f"https://t.me/{bot_username}?startgroup=groupquiz_{quiz_id}")],
                [InlineKeyboardButton(MY_QUIZZES_TRANSLATIONS[language]["edit_quiz_info"],
                                      callback_data=f"edit_quiz_info_{quiz_id}")],
                [InlineKeyboardButton(btn_text["download_word"], callback_data=f"download_quiz_{quiz_id}")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            t = QUIZ_INFO_TRANSLATIONS.get(language, QUIZ_INFO_TRANSLATIONS["en"])
            quiz_info_display = f"\n📝 *{t.get('quiz_info_label', 'Quiz Info')}:* {quiz_info}\n" if quiz_info else ""

            quiz_ready_text = (
                f"✅ *{TRANSLATIONS[language]['quiz_ready_title']}*\n\n"
                f"*{title}*\n\n"
                f"*{TRANSLATIONS[language]['summary_label']}:* {summary}\n"
                f"{quiz_info_display}\n"
                f"⏱️ *{TRANSLATIONS[language]['time_limit']}:* {actual_quiz_time} {TRANSLATIONS[language]['seconds_per_question']}\n"
                f"📝 *{TRANSLATIONS[language]['num_questions']}:* {len(quiz_data['questions'])}\n"
                f"🎮 *{TRANSLATIONS[language]['choose_option']}:*\n"
                f"🎯 *{TRANSLATIONS[language]['start_quiz_desc']}*\n"
                f"📤 *{TRANSLATIONS[language]['share_quiz_desc']}*"
            )
            await context.bot.send_message(chat_id=chat_id, text=quiz_ready_text,
                                           parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            delivered = True

        else:  # open-ended
            formatted_messages = format_quiz_for_telegram(quiz_data, quiz_type)
            if formatted_messages:
                formatted_messages[-1] += "\n\nDone with @SimpleQuizzer_bot\nJoin our channel: @SimpleLearnUz"
            for msg in formatted_messages:
                await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.HTML,
                                               disable_web_page_preview=True)
            delivered = True

            fire_and_forget(update_quiz_stats(user_id, False))
            # fire_and_forget(log_quiz_activity(user_id, context))

            await context.bot.send_message(chat_id=chat_id, text=get_translation(language, "send_document"),
                                           parse_mode=ParseMode.HTML)

        logger.info(f"[BACKGROUND QUIZ] Completed for user {user_id}")

    except Exception as e:
        logger.error(f"[BACKGROUND QUIZ] Error for user {user_id}: {e}", exc_info=True)
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=processing_message_id)
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ *Oops! Something went wrong*\n\nPlease try again or share a different document. /start to restart.",
                parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
    finally:
        amount = context.user_data.pop('charged_amount', 0)
        if amount and not delivered:                     # the only place money is given back
            if await refund_balance(user_id, amount):
                logger.info(f"[BACKGROUND QUIZ] Refunded {amount} kopecks to user {user_id}")
                try:
                    msgs = {"uz": "💸 To'lovingiz qaytarildi. Iltimos, qayta urinib ko'ring.",
                            "ru": "💸 Оплата возвращена. Пожалуйста, попробуйте снова.",
                            "en": "💸 Your payment was refunded. Please try again."}
                    await context.bot.send_message(chat_id=chat_id, text=msgs.get(language, msgs["en"]))
                except Exception:
                    pass
        context.user_data['busy'] = False
        context.user_data.pop('generating', None)



async def _process_document_background(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int, file_id: str,
    file_ext: str, file_name: str, file_info: Dict, language: str,
    status_message_id: int, document
):
    """Download and extract in the background so other users aren't blocked."""
    try:
        with timed("doc: download"):
            file = await context.bot.get_file(file_id)
            file_bytes = await file.download_as_bytearray()

        extracted_text = None
        with timed(f"doc: extract {file_ext}"):
            if file_ext == '.pdf':
                extracted_text = await extract_text_from_pdf(file_bytes)
            elif file_ext == '.docx':
                extracted_text = await extract_text_from_docx(file_bytes)
            elif file_ext == '.doc':
                extracted_text = await extract_text_from_doc(file_bytes)
            elif file_ext == '.txt':
                extracted_text = await extract_text_from_txt(file_bytes)
            elif file_ext in ['.xlsx', '.xls']:
                extracted_text = await extract_text_from_excel(file_bytes)

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=status_message_id)
        except Exception as e:
            logger.error(f"Error deleting status message: {e}")

        if not extracted_text:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ *No Text Extracted*\n\nCould not extract any text from the document. Please try a different file.",
                parse_mode=ParseMode.MARKDOWN)
            return

        extracted_text = re.sub(r'\s+', ' ', extracted_text).strip()
        if len(extracted_text) > 10000:
            extracted_text = truncate_content_for_processing(extracted_text, 10000)

        if len(extracted_text) < 5:
            await context.bot.send_message(
                chat_id=chat_id,
                text=TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("content_too_short"),
                parse_mode=ParseMode.MARKDOWN)
            return

        context.user_data['extracted_text'] = extracted_text

        file_info.update({
            'file_name': file_name, 'file_type': file_ext[1:], 'file_size': document.file_size,
            'content_type': document.mime_type, 'status': 'success',
            'processed_at': datetime.now(timezone.utc).isoformat()
        })

        # Same gate, now complete: it also knows about premium free quizzes
        # (the old version here ignored them and could wrongly block premium users).
        gate = await get_quiz_gate(user_id)
        if gate["blocked"]:
            user_lang = await get_user_language(user_id) or 'en'
            text_msg, kb = insufficient_balance_payload(user_lang, gate)
            await context.bot.send_message(chat_id=chat_id, text=text_msg,
                                           parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
            return

        await _send_language_selection(
            lambda **kw: context.bot.send_message(chat_id=chat_id, **kw),
            language, extracted_text, gate)
        logger.info(f"[BACKGROUND DOC] completed for user {user_id}")

    except Exception as e:
        logger.error(f"[BACKGROUND DOC] Error for user {user_id}: {e}")
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=status_message_id)
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ *Error Processing Document*\n\nAn error occurred: {str(e)}",
            parse_mode=ParseMode.MARKDOWN)
    finally:
        context.user_data['busy'] = False


@track_handler("process_content")
async def process_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    fire_and_forget(query.answer())                 # stop the spinner immediately

    user = query.from_user
    language = await get_user_language(user.id) or 'uz'
    quiz_type = await get_user_quiz_type(user.id)

    if query.data != "process_quiz":
        return CONTENT

    # double-tap guard (checked and set before any await that could interleave)
    if context.user_data.get('generating'):
        return PROCESSING
    context.user_data['generating'] = True
    launched = False

    try:
        fire_and_forget(query.message.reply_chat_action("typing"))

        generating_texts = {
            'en': '🧠 *Generating your quiz... Please wait*',
            'uz': '🧠 *Quizingiz yaratilmoqda... Iltimos kuting*',
            'ru': '🧠 *Генерирую ваш тест... Пожалуйста, подождите*'
        }
        no_content_texts = {
            'en': '❌ *No content found*\n\nPlease share some content to create a quiz. /start the bot again.',
            'uz': '❌ *Mazmun topilmadi*\n\nTest yaratish uchun kontent yuboring. Botni qayta /start qiling.',
            'ru': '❌ *Контент не найден*\n\nПожалуйста, отправьте контент для создания теста. Перезапустите бота /start.'
        }

        extracted_text = context.user_data.get('extracted_text', '')
        if not extracted_text:
            await query.message.reply_text(no_content_texts.get(language, no_content_texts['uz']),
                                           parse_mode=ParseMode.MARKDOWN)
            context.user_data['busy'] = False
            return CONTENT

        from payment_integration_new import deduct_balance
        from handlers.premium import use_daily_free_quiz
        from src.imports import is_free_user

        quiz_time = context.user_data.get('quiz_time') or await get_user_quiz_time(user.id) or 30
        quiz_questions = context.user_data.get('quiz_questions') or await get_user_quiz_questions(user.id) or 5
        detected_language = context.user_data.get('detected_language', 'en')

        file_info = {'user_id': user.id, 'quiz_type': quiz_type, 'quiz_time': quiz_time,
                     'quiz_questions': quiz_questions, 'status': 'pending'}

        # ---- payment: free daily quiz first, then balance ----
        gate = await get_quiz_gate(user.id, quiz_questions)
        context.user_data.pop('charged_amount', None)
        context.user_data.pop('used_free_quiz', None)

        if not is_free_user(user.id) and gate["total_quizzes"] >= FREE_QUIZZES_BEFORE_PAYMENT:
            used_free = False
            if gate["has_free"]:
                used_free = await use_daily_free_quiz(user.id)
                if used_free:
                    context.user_data['used_free_quiz'] = True
            if not used_free:
                if not await deduct_balance(user.id, gate["price"]):
                    text_msg, kb = insufficient_balance_payload(language, gate)
                    await query.message.reply_text(text_msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
                    context.user_data['busy'] = False
                    return CONTENT
                context.user_data['balance_deducted'] = True
                context.user_data['charged_amount'] = gate["price"]    # refunded if generation fails

        status_message = await query.message.reply_text(
            generating_texts.get(language, generating_texts['uz']), parse_mode=ParseMode.MARKDOWN)

        context.user_data['busy'] = True
        asyncio.create_task(_generate_and_send_quiz_background(
            context=context, user_id=user.id, chat_id=query.message.chat_id,
            extracted_text=extracted_text, detected_language=detected_language,
            quiz_type=quiz_type, language=language, quiz_questions=quiz_questions,
            quiz_time=quiz_time, file_info=file_info,
            processing_message_id=status_message.message_id))
        launched = True
        return PROCESSING

    except Exception as e:
        logger.error(f"Error in process_content: {e}", exc_info=True)
        # Charged but never launched -> give it back
        amount = context.user_data.pop('charged_amount', 0)
        if amount and not launched:
            await refund_balance(user.id, amount)
        try:
            await query.message.reply_text(
                "❌ *Oops! Something went wrong*\n\nPlease try again or share a different document.",
                parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
        context.user_data['busy'] = False
        return CONTENT

    finally:
        if not launched:
            context.user_data.pop('generating', None)




async def handle_back_or_change_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    language = await get_user_language(user.id)
    extracted_text = context.user_data.get('extracted_text', '')
    preview = extracted_text[:150] + "..." if len(extracted_text) > 150 else extracted_text
    preview = preview.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[").replace("]", "\\]")

    from handlers.premium import get_user_subscription
    
    # Check if user has premium
    subscription = await get_user_subscription(user.id)
    is_premium = subscription["is_active"]

    if is_premium:
        keyboard = [
            [
                InlineKeyboardButton("5", callback_data="set_questions_5"),
                InlineKeyboardButton("10", callback_data="set_questions_10"),
                InlineKeyboardButton("15", callback_data="set_questions_15"),
            ],
            [
                InlineKeyboardButton("20", callback_data="set_questions_20"),
                InlineKeyboardButton("25", callback_data="set_questions_25"),
                InlineKeyboardButton("30", callback_data="set_questions_30"),
            ],
            [
                InlineKeyboardButton("40 🌟", callback_data="set_questions_40"),
                InlineKeyboardButton("50 🌟", callback_data="set_questions_50"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_language_select")
            ]
        ]
    else:       
        keyboard = [
            [
                InlineKeyboardButton("5 questions", callback_data="set_questions_5"),
                InlineKeyboardButton("10 questions", callback_data="set_questions_10"),
                InlineKeyboardButton("15 questions", callback_data="set_questions_15"),
            ],
            [
                InlineKeyboardButton("20 questions", callback_data="set_questions_20"),
                InlineKeyboardButton("25 questions", callback_data="set_questions_25"),
                InlineKeyboardButton("30 questions", callback_data="set_questions_30"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_language_select")
            ]
        ]

    # ✅ FIX: reply_markup is now always assigned regardless of premium status
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            text=(
                f"✅ *{TRANSLATIONS[language]['content_extracted']}*\n\n"
                f"*{TRANSLATIONS[language]['preview']}:*\n"
                f"```\n{preview}\n```\n\n"
                f"*{TRANSLATIONS[language]['choose_num_questions']}*"
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        # Fallback to delete and send if edit fails
        try:
            await query.message.delete()
        except Exception as e:
            logger.error(f"Error deleting previous message: {e}")

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                f"✅ *{TRANSLATIONS[language]['content_extracted']}*\n\n"
                f"*{TRANSLATIONS[language]['preview']}:*\n"
                f"```\n{preview}\n```\n\n"
                f"*{TRANSLATIONS[language]['choose_num_questions']}*"
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    return PROCESSING

async def handle_set_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    num_questions = int(query.data.split("_")[-1])
    context.user_data['quiz_questions'] = num_questions
    
    user = query.from_user
    language = await get_user_language(user.id)
    
    # Show quiz time selection with "No Time Limit" option
    keyboard = [
        [
            InlineKeyboardButton("15 sec", callback_data="set_quiz_time_15"),
            InlineKeyboardButton("20 sec", callback_data="set_quiz_time_20"),
            InlineKeyboardButton("30 sec", callback_data="set_quiz_time_30"),
        ],
        [
            InlineKeyboardButton("45 sec", callback_data="set_quiz_time_45"),
            InlineKeyboardButton("60 sec", callback_data="set_quiz_time_60"),
        ],
        [
            InlineKeyboardButton("⏳ No Time ", callback_data="set_quiz_time_0"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="change_questions")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            text=f"⏱️ *Select time per question*\n\nYou've chosen *{num_questions} questions*.\n\nHow much time should users have for each question?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
    
    return PROCESSING

async def handle_set_quiz_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    quiz_time = int(query.data.split("_")[-1])
    context.user_data['quiz_time'] = quiz_time
    
    user = query.from_user
    language = await get_user_language(user.id)
    
    # Ask for quiz info instead of going to confirmation
    t = QUIZ_INFO_TRANSLATIONS.get(language, QUIZ_INFO_TRANSLATIONS["en"])
    
    keyboard = [
        [InlineKeyboardButton(t["skip_quiz_info"], callback_data="skip_quiz_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            text=t["ask_quiz_info"],
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
    
    return ASK_QUIZ_INFO

async def handle_skip_quiz_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle skipping quiz info and show confirmation."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    
    # Show confirmation
    return await show_quiz_confirmation(update, context, language)

async def receive_main_quiz_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive quiz info for main quiz creation."""
    user = update.effective_user
    language = await get_user_language(user.id)
    
    quiz_info = update.message.text.strip()
    
    if len(quiz_info) >= 3:
        if len(quiz_info) > 200:
            quiz_info = quiz_info[:200]
        
        context.user_data['quiz_info'] = quiz_info
        
        t = QUIZ_INFO_TRANSLATIONS.get(language, QUIZ_INFO_TRANSLATIONS["en"])
        confirmation = t["quiz_info_received"].format(info=quiz_info)
        await update.message.reply_text(confirmation, parse_mode=ParseMode.MARKDOWN)
    
    # Show confirmation instead of calling process_content
    return await show_quiz_confirmation(update, context, language)

async def show_quiz_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, language: str) -> int:
    """Show quiz configuration confirmation."""
    # Get preview of content
    extracted_text = context.user_data.get('extracted_text', '')
    preview = extracted_text[:100] + "..." if len(extracted_text) > 100 else extracted_text
    
    # Get stored values
    quiz_questions = context.user_data.get('quiz_questions', 5)
    quiz_time = context.user_data.get('quiz_time', 30)
    quiz_type = await get_user_quiz_type(update.effective_user.id)
    quiz_info = context.user_data.get('quiz_info', '')
    
    # Get translations
    t = QUIZ_INFO_TRANSLATIONS.get(language, QUIZ_INFO_TRANSLATIONS["en"])
    
    # Format quiz type
    quiz_type_str = t["multiple_choice"] if quiz_type == "mc" else t["open_ended"]
    
    # Format time display
    time_display = t["no_time_limit"] if quiz_time == 0 else f"{quiz_time} sec"
    
    # ADD QUIZ INFO TO DISPLAY
    quiz_info_display = f"\n📝 *{t.get('quiz_info_label', 'Quiz Info')}:* {quiz_info}\n" if quiz_info else ""
    
    confirm_text = (
        f"{t['quiz_config']}\n\n"
        f"{t['type']} `{quiz_type_str}`\n"
        f"{t['questions']} `{quiz_questions}`\n"
        f"{t['time_per_question']} `{time_display}`\n"
        f"{quiz_info_display}\n"
        f"{t['content_preview']}\n"
        f"```{preview}```\n\n"
        f"{t['ready_generate']}"
    )
    
    # FIXED: Add "Change Quiz Info" button
    keyboard = [
        [InlineKeyboardButton(t["generate_quiz"], callback_data="process_quiz")],
        [
            InlineKeyboardButton(t["change_questions"], callback_data="change_questions"),
            InlineKeyboardButton(t["change_time"], callback_data="change_quiz_time")
        ],
        [InlineKeyboardButton(t["change_quiz_info"], callback_data="change_quiz_info")],
        [InlineKeyboardButton(t["back_to_menu"], callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        try:
            await update.callback_query.message.reply_text(
                text=confirm_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error sending confirmation: {e}")
    else:
        try:
            await update.message.reply_text(
                text=confirm_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error sending confirmation: {e}")
    
    return PROCESSING


async def handle_change_quiz_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle changing quiz info from confirmation screen."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    
    t = QUIZ_INFO_TRANSLATIONS.get(language, QUIZ_INFO_TRANSLATIONS["en"])
    
    keyboard = [
        [InlineKeyboardButton(t["skip_quiz_info"], callback_data="skip_quiz_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            text=t["ask_quiz_info"],
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
    
    return ASK_QUIZ_INFO


async def ask_quiz_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask for quiz information after time selection."""
    language = await get_user_language(update.effective_user.id)
    
    text = QUIZ_INFO_TRANSLATIONS[language]["ask_quiz_info"]
    
    keyboard = [
        [InlineKeyboardButton(
            QUIZ_INFO_TRANSLATIONS[language]["skip_quiz_info"],
            callback_data="skip_quiz_info"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    return ASK_QUIZ_INFO


async def handle_change_quiz_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    language = await get_user_language(user.id)
    
    keyboard = [
        [
            InlineKeyboardButton("15 sec", callback_data="set_quiz_time_15"),
            InlineKeyboardButton("20 sec", callback_data="set_quiz_time_20"),
            InlineKeyboardButton("30 sec", callback_data="set_quiz_time_30"),
        ],
        [
            InlineKeyboardButton("45 sec", callback_data="set_quiz_time_45"),
            InlineKeyboardButton("60 sec", callback_data="set_quiz_time_60"),
        ],
        [
            InlineKeyboardButton("⏳ No Time ", callback_data="set_quiz_time_0"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="back_to_confirmation")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await query.edit_message_text(
            text="⏱️ *Select time per question*\n\nHow much time should users have for each question?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
    
    return PROCESSING

async def get_quiz(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Dict:
    """Retrieve quiz data from user_data."""
    try:
        # Get quiz data from user_data
        quiz_data = context.user_data.get('current_quiz')
        if not quiz_data:
            return None
            
        quiz_time = await get_user_quiz_time(user_id)
        
        return {
            'quiz_data': quiz_data,
            'title': quiz_data.get('title', '📝 Multiple Choice Quiz'),
            'summary': quiz_data.get('summary', ''),
            'quiz_time': quiz_time
        }
    except Exception as e:
        logger.error(f"Error retrieving quiz: {e}")
        return None

@track_handler("quiz_actions")
async def handle_quiz_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle poll answers for both group and private quizzes."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    language = await get_user_language(user.id)
    countdown_texts = COUNTDOWN_TRANSLATIONS.get(language, COUNTDOWN_TRANSLATIONS['en'])
    
    quiz_id = None
    
    # ✅ FIXED: Better language selection detection
    if query.data.startswith("quiz_lang_"):
        # Check if it's actually a language selection, not a quiz ID
        lang_codes = ["auto", "uz", "en", "ru", "de", "fr", "es", "ar", "ko", "zh", "hi", "bn", "ur"]
        lang_suffix = query.data.replace("quiz_lang_", "")
        if lang_suffix in lang_codes:
            logger.warning(f"[QUIZ START] Ignoring language selection callback: {query.data}")
            return PROCESSING
        
    # Extract quiz_id from callback data
    if query.data.startswith("start_quiz_"):
        quiz_id = query.data.replace("start_quiz_", "") 
        logger.info(f"[QUIZ START] Extracted quiz_id from start_quiz_: {quiz_id}")
    elif query.data.startswith("quiz_"):
        # Make sure it's not a language selection
        if query.data not in ["quiz_lang_auto", "quiz_lang_uz", "quiz_lang_en", "quiz_lang_ru"]:
            quiz_id = query.data.replace("quiz_", "")  
    
    # Handle both shared/split quizzes AND regular quizzes with ID
    if quiz_id:
        logger.info(f"[QUIZ START] Starting quiz {quiz_id} for user {user.id}")
        
        # ✅ ALWAYS load from database first
        quiz_data = await get_shared_quiz(quiz_id)
        logger.info(f"[QUIZ START] Retrieved quiz data from DB: {bool(quiz_data)}")
        
        if not quiz_data:
            logger.error(f"[QUIZ START] No quiz data found in DB for quiz_id: {quiz_id}")
            
            # ✅ ADDED: Try to check if quiz exists in database with better error logging
            try:
                # You might need to add this debug query to your database functions
                logger.error(f"[QUIZ START] Attempting to query database directly for quiz_id: {quiz_id}")
            except Exception as e:
                logger.error(f"[QUIZ START] Database error: {e}")
            
            user_lang = await get_user_language(user.id) or 'en'
            if user_lang == 'ru':
                error_text = (
                    "❌ <b>Ошибка: Квиз не найден</b>\n\n"
                    f"Quiz ID: <code>{quiz_id}</code>\n\n"
                    "Похоже, что квиз был удален или не существует. Пожалуйста, нажмите /start, затем 'Мои викторины', чтобы найти доступные квизы."
                )
            elif user_lang == 'uz':
                error_text = (
                    "❌ <b>Xatolik: Quiz topilmadi</b>\n\n"
                    f"Quiz ID: <code>{quiz_id}</code>\n\n"
                    "Quiz o'chirilgan yoki mavjud emas. Iltimos, /start buyrug'ini bosing va 'Mening Quizlarim' bo'limidan mavjud quizlarni toping."
                )
            else:
                error_text = (
                    "❌ <b>Error: No quiz found</b>\n\n"
                    f"Quiz ID: <code>{quiz_id}</code>\n\n"
                    "The quiz was deleted or doesn't exist. Please use /start and then 'My quizzes' to find available quizzes."
                )
            await context.bot.send_message(
                chat_id=user.id,
                text=error_text,
                parse_mode=ParseMode.HTML
            )
            return CONTENT

        # Store quiz data in context
        context.user_data['current_quiz'] = quiz_data
        context.user_data['current_quiz_id'] = quiz_id
        context.user_data['quiz_start_time'] = datetime.now(timezone.utc)
        context.user_data['total_questions'] = len(quiz_data["questions"])
        context.user_data['correct_answers'] = 0
        context.user_data['current_question_index'] = 0
        context.user_data['unanswered_count'] = 0
        
        logger.info(f"[QUIZ START] Quiz state initialized for quiz_id: {quiz_id}")
        
        asyncio.create_task(
            send_countdown_and_start_quiz(
                update=update,
                context=context,
                chat_id=user.id,
                user_id=user.id,
                quiz_data=quiz_data,
                language=language
            )
        )
        
        return CONTENT

    elif query.data == "start_quiz":
        logger.info(f"[QUIZ START] Starting regular quiz without ID for user {user.id}")
        
        # ✅ Try to get from context first, then from last created quiz
        quiz_data = context.user_data.get('current_quiz')
        
        if not quiz_data:
            # ✅ If not in context, try to get the user's most recent quiz from DB
            logger.info(f"[QUIZ START] No quiz in context, fetching from DB for user {user.id}")
            quiz_id = context.user_data.get('current_quiz_id')
            
            if quiz_id:
                quiz_data = await get_shared_quiz(quiz_id)
                if quiz_data:
                    context.user_data['current_quiz'] = quiz_data
                    logger.info(f"[QUIZ START] Loaded quiz {quiz_id} from DB")
        
        if not quiz_data:
            logger.error(f"[QUIZ START] No quiz data found for user {user.id}")
            user_lang = await get_user_language(user.id) or 'en'
            if user_lang == 'ru':
                error_text = (
                    "❌ <b>Ошибка: Квиз не найден</b>\n\n"
                    "Похоже, что у вас нет активного квиза. Пожалуйста, нажмите /start, затем 'Создать викторину' или 'Мои викторины'."
                )
            elif user_lang == 'uz':
                error_text = (
                    "❌ <b>Xatolik: Quiz topilmadi</b>\n\n"
                    "Sizda faol quiz yo'q. Iltimos, /start buyrug'ini bosing va 'Quiz yaratish' yoki 'Mening Quizlarim' bo'limiga o'ting."
                )
            else:
                error_text = (
                    "❌ <b>Error: No quiz found</b>\n\n"
                    "It looks like you have no active quiz. Please use /start and then 'Create Quiz' or 'My quizzes'."
                )
            await context.bot.send_message(
                chat_id=user.id,
                text=error_text,
                parse_mode=ParseMode.HTML
            )
            return CONTENT

        # Initialize quiz state
        context.user_data['total_questions'] = len(quiz_data["questions"])
        context.user_data['correct_answers'] = 0
        context.user_data['current_question_index'] = 0  
        context.user_data['unanswered_count'] = 0
        context.user_data['quiz_start_time'] = datetime.now(timezone.utc)
        
        logger.info(f"[QUIZ START] Quiz state initialized. Total questions: {context.user_data['total_questions']}")

        asyncio.create_task(
            send_countdown_and_start_quiz(
                update=update,
                context=context,
                chat_id=user.id,
                user_id=user.id,
                quiz_data=quiz_data,
                language=language
            )
        )
        
        return CONTENT
    
    elif query.data == "share_quiz":
        logger.info(f"[QUIZ START] Share quiz clicked for user {user.id}")

        context.user_data['quiz_start_time'] = datetime.now(timezone.utc)
        quiz_data = context.user_data.get('current_quiz')
        logger.info(f"[QUIZ START] Retrieved quiz data from context: {bool(quiz_data)}")
        
        if not quiz_data:
            logger.error(f"[QUIZ START] No quiz data found in context for user {user.id}")
            user_lang = await get_user_language(user.id) or 'en'
            if user_lang == 'ru':
                error_text = (
                    "❌ <b>Ошибка: Квиз не найден</b>\n\n"
                    "Похоже, что у вас нет активного квиза. Пожалуйста, нажмите /start, затем 'Мои викторины', чтобы найти и начать свой квиз."
                )
            elif user_lang == 'uz':
                error_text = (
                    "❌ <b>Xatolik: Quiz topilmadi</b>\n\n"
                    "Sizda faol quiz yo'q. Iltimos, /start buyrug'ini bosing va 'Mening Quizlarim' bo'limidan quizni boshlang."
                )
            else:
                error_text = (
                    "❌ <b>Error: No quiz found</b>\n\n"
                    "It looks like you have no active quiz. Please use /start and then 'My quizzes' to find and start your quiz."
                )
            await context.bot.send_message(
                chat_id=user.id,
                text=error_text,
                parse_mode=ParseMode.HTML
            )
            return CONTENT
        
        # Initialize quiz state
        context.user_data['total_questions'] = len(quiz_data["questions"])
        context.user_data['correct_answers'] = 0
        
        logger.info(f"[QUIZ START] Quiz state initialized. Total questions: {context.user_data['total_questions']}")

        asyncio.create_task(
            send_countdown_and_start_quiz(
                update=update,
                context=context,
                chat_id=user.id,
                user_id=user.id,
                quiz_data=quiz_data,
                language=language
            )
        )
        
        return CONTENT

@track_handler("poll_answer")
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle poll answers for both group and private quizzes."""
    if not update.poll_answer or not hasattr(update.poll_answer, "user"):
        logger.warning("[POLL ANSWER] No poll_answer or user in update")
        return
    
    try:
        poll_answer = update.poll_answer
        user_id = poll_answer.user.id
        poll_id = poll_answer.poll_id
        if any(poll_id in s.get("poll_to_question", {}) for s in GROUP_QUIZ_STATE.values()):
            return  # group quiz votes are handled by handle_group_poll_answer
        answer_time = datetime.now(timezone.utc)
        
        group_quiz_found = False
        for chat_id, state in GROUP_QUIZ_STATE.items():
            if poll_id in state.get("poll_to_question", {}):
                group_quiz_found = True
                
                state["unanswered_count"] = 0
                logger.info(f"[GROUP QUIZ] Poll answer received for group quiz in chat {chat_id}")
                
                # Get question data
                question_data = state["poll_to_question"][poll_id]
                question_start_time = question_data.get("start_time")
                
                # Calculate time spent
                if isinstance(question_start_time, datetime):
                    time_spent = (answer_time - question_start_time).total_seconds()
                else:
                    time_spent = 0
                
                if poll_answer.option_ids:
                    user_choice = poll_answer.option_ids[0]
                    correct_option_id = question_data["correct_option_id"]
                    
                    # FIXED: Handle both single int and list of ints for correct answers
                    if isinstance(correct_option_id, list):
                        is_correct = user_choice in correct_option_id
                    else:
                        is_correct = user_choice == correct_option_id
                
                    # Initialize or update user score
                    if "scores" not in state:
                        state["scores"] = {}
                    if user_id not in state["scores"]:
                        state["scores"][user_id] = 0
                    
                    # Update score if correct
                    if is_correct:
                        state["scores"][user_id] += 1

                    # Store detailed answer info
                    if "user_answers" not in state:
                        state["user_answers"] = {}
                    if user_id not in state["user_answers"]:
                        state["user_answers"][user_id] = []

                    # Get question details
                    quiz_data = state.get("quiz_data", {})
                    question = quiz_data["questions"][question_data["question_idx"]]
                    options = question["options"]
                    
                    # FIXED: Handle correct answer display for both single and multiple correct answers
                    if isinstance(correct_option_id, list):
                        correct_answer = [options[idx] for idx in correct_option_id]
                    else:
                        correct_answer = options[correct_option_id]
                    
                    # Store answer data
                    answer_data = {
                        "question_idx": question_data["question_idx"],
                        "user_choice": user_choice,
                        "correct_option": correct_option_id,
                        "is_correct": is_correct,
                        "time_spent": time_spent,
                        "answer_time": answer_time,
                        "user_answer": options[user_choice],
                        "correct_answer": correct_answer
                    }
                    
                    state["user_answers"][user_id].append(answer_data)

                    # Update state
                    GROUP_QUIZ_STATE[chat_id] = state
                
                logger.info(f"[GROUP QUIZ] Processed group quiz answer, returning early")
                return  
        
        if not group_quiz_found:
            context.user_data['unanswered_count'] = 0
            quiz_data = context.user_data.get('current_quiz')
            
            if not quiz_data:
                logger.error(f"[PRIVATE QUIZ] No quiz data found in context for user {user_id}")
                return
            
            if not poll_answer.option_ids:
                logger.error(f"[PRIVATE QUIZ] No option_ids in poll_answer for poll_id {poll_id}")
                return
            
            # Get the current question index from user_data
            current_question = context.user_data.get('current_question_index', 0)
            total_questions = len(quiz_data["questions"])
            
            # Get the question data
            question = quiz_data["questions"][current_question]
            
            # Check if the answer was correct
            user_choice = poll_answer.option_ids[0]
            
            # FIXED: Handle both single and multiple correct answers properly
            if question.get("allows_multiple_answers"):
                correct_answers = question.get("correct_answers", [])
                # Convert text answers to indices if needed
                correct_option_ids = []
                for ans in correct_answers:
                    if isinstance(ans, int):
                        correct_option_ids.append(ans)
                    else:
                        try:
                            correct_option_ids.append(question["options"].index(ans))
                        except ValueError:
                            pass
                is_correct = user_choice in correct_option_ids
            else:
                correct_answer = question.get("correct_answer")
                if isinstance(correct_answer, int):
                    correct_option_id = correct_answer
                else:
                    try:
                        correct_option_id = question["options"].index(correct_answer)
                    except ValueError:
                        logger.error(f"[PRIVATE QUIZ] Could not find correct answer in options")
                        correct_option_id = 0
                is_correct = user_choice == correct_option_id
            
            # Update correct answers count
            if 'correct_answers' not in context.user_data:
                context.user_data['correct_answers'] = 0
            
            if is_correct:
                context.user_data['correct_answers'] += 1
                logger.info(f"[PRIVATE QUIZ] ✅ User {user_id} answered correctly. Total: {context.user_data['correct_answers']}")
            else:
                logger.info(f"[PRIVATE QUIZ] ❌ User {user_id} answered incorrectly. Total correct: {context.user_data['correct_answers']}")

            context.user_data.pop('current_poll_id', None)
            # Check if there are more questions
            if current_question + 1 < total_questions:
                # Update question index and send next question
                context.user_data['current_question_index'] = current_question + 1
                logger.info(f"[PRIVATE QUIZ] Sending question {current_question + 2}/{total_questions}")
                await send_next_question(update, context, user_id, quiz_data, current_question + 1)
            else:
                # Quiz completed - calculate final score
                total_questions_context = context.user_data.get('total_questions', total_questions)
                correct_answers = context.user_data.get('correct_answers', 0)
                accuracy = (correct_answers / total_questions_context * 100) if total_questions_context > 0 else 0

                logger.info(f"[QUIZ COMPLETE] User {user_id} finished quiz. Correct: {correct_answers}/{total_questions_context}")

                # Calculate time spent
                quiz_start_time = context.user_data.get('quiz_start_time')
                quiz_end_time = datetime.now(timezone.utc)
                time_spent = (quiz_end_time - quiz_start_time).total_seconds() if quiz_start_time else 0

                # Get quiz_id
                quiz_id = context.user_data.get('current_quiz_id')
                
                # ✅ ADDED: Save quiz attempt and notify owner
                if quiz_id:
                    from src.quiz_results import save_quiz_attempt, notify_quiz_owner
                    
                    try:
                        user_info = await context.bot.get_chat(user_id)
                        username = user_info.username
                        first_name = user_info.first_name or 'Anonymous'
                        last_name = user_info.last_name or ''
                        
                        if username:
                            participant_name = f"{first_name} {last_name} (@{username})".strip()
                        else:
                            participant_name = f"{first_name} {last_name}".strip()
                    except:
                        username = None
                        first_name = 'Anonymous'
                        participant_name = f"User {user_id}"

                    async def _save_and_notify():
                        try:
                            await save_quiz_attempt(
                                quiz_id=quiz_id,
                                user_id=user_id,
                                username=username,
                                first_name=first_name,
                                score=correct_answers,
                                total_questions=total_questions_context,
                                time_spent=time_spent
                            )
                            
                            from src.quiz_results import get_quiz_owner_id
                            owner_id = await get_quiz_owner_id(quiz_id)
                            if owner_id not in NOTIFICATION_ADMIN_IDS:
                                await notify_quiz_owner(
                                    context=context,
                                    quiz_id=quiz_id,
                                    participant_id=user_id,
                                    participant_name=participant_name,
                                    score=correct_answers,
                                    total_questions=total_questions_context,
                                    time_spent=time_spent
                                )
                        except Exception as e:
                            logger.error(f"[BACKGROUND] Error saving/notifying quiz results: {e}")

                    asyncio.create_task(_save_and_notify())




                # Send completion message
                language = await get_user_language(user_id)
                
                quiz_completed_text = TRANSLATIONS[language]["quiz_completed"].format(
                    total_questions=total_questions_context,
                    correct_answers=correct_answers,
                    accuracy=accuracy,
                    time_spent=time_spent
                )

                if quiz_id:
                    bot_username = (await context.bot.get_me()).username
                    keyboard = [
                        [InlineKeyboardButton("📤 Share Quiz", switch_inline_query=f"quiz_{quiz_id}")],
                        [InlineKeyboardButton("👥 Share to Group", url=f"https://t.me/{bot_username}?startgroup=groupquiz_{quiz_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                else:
                    reply_markup = None

                await context.bot.send_message(
                    chat_id=user_id,
                    text=quiz_completed_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
                
                # Clean up user_data
                for key in ['correct_answers', 'total_questions', 'quiz_start_time', 'current_quiz_id', 'current_question_index', 'current_quiz']:
                    if key in context.user_data:
                        del context.user_data[key]
                context.user_data['busy'] = False
                
                logger.info(f"[PRIVATE QUIZ] ✅ Quiz cleanup completed for user {user_id}")
                
    except Exception as e:
        logger.error(f"Error handling poll answer: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


initialize_key_semaphores()

def main() -> None:
    # patch_telegram_http()

    from handlers.my_quizzes_handlers import EDIT_QUIZ_INFO, receive_edited_quiz_info, handle_skip_edit_quiz_info, handle_view_my_quiz, handle_back_to_my_quizzes, handle_edit_quiz_info_button
    from payment_integration_new import setup_payment_handlers
    from handlers.stars_payment_quizzer import setup_stars_payment_handlers
    from handlers.main_commands import stop_quiz_command, info_command, admin_stats_command, ALL_MENU_BUTTON_TEXTS, handle_orphaned_button
    from handlers.premium import setup_premium_handlers, subscribe_command

    logging.getLogger("httpx").setLevel(logging.WARNING)

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)
        .connection_pool_size(256)
        .pool_timeout(30)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .get_updates_read_timeout(30)
        .post_init(_post_init)
        .build()
    )
    setup_premium_handlers(application)

    logger.debug("Setting up handlers")
    initialize_key_semaphores()
    setup_broadcast_handlers(application)
    setup_stars_payment_handlers(application)

    application.add_handler(get_split_quiz_handler())
    application.add_handler(TypeHandler(Update, touch_user), group=-1)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LANGUAGE: [
                CallbackQueryHandler(language_selection, pattern=r"^lang_"),
                CommandHandler("start", start),
                CommandHandler("settings", settings_command),
                CommandHandler("help", help_command),
            ],
            EDIT_QUIZ_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_edited_quiz_info),
                CallbackQueryHandler(handle_skip_edit_quiz_info, pattern="^skip_edit_quiz_info$")
        ],

            CONTENT: [
                CommandHandler("start", start),
                CommandHandler("settings", settings_command),
                CommandHandler("help", help_command),
                CallbackQueryHandler(create_quiz_handler, pattern="^create_quiz$"),
                CallbackQueryHandler(settings_callback_handler, pattern="^settings_command$"),
                CallbackQueryHandler(help_callback_handler, pattern="^help_command$"),
                CallbackQueryHandler(back_to_main_handler, pattern="^back_to_main$"), 
 
                CallbackQueryHandler(language_selection, pattern=r"^lang_"),
                CallbackQueryHandler(settings_button, pattern=r"^(settings_|mc$|oe$)"), 
                CallbackQueryHandler(process_content, pattern=r"^process_quiz$"),
                
                CallbackQueryHandler(handle_language_detect_selection, pattern=r"^quiz_lang_(auto|uz|en|ru|de|fr|es|ar|ko|zh|hi|bn|ur)$"),
                CallbackQueryHandler(handle_set_quiz_time, pattern=r"^set_quiz_time_\d+$"),
                CallbackQueryHandler(handle_change_quiz_time, pattern="^change_quiz_time$"),
                CallbackQueryHandler(handle_change_quiz_info, pattern="^change_quiz_info$"),
                CallbackQueryHandler(handle_skip_quiz_info, pattern="^skip_quiz_info$"),
                CallbackQueryHandler(handle_set_questions, pattern=r"^set_questions_\d+$"),
                CallbackQueryHandler(handle_group_quiz_actions, pattern=r"^(start_group_quiz|next_question|finish_quiz)_"),
                CallbackQueryHandler(settings_button, pattern="^settings_quiz_type$"),
                CallbackQueryHandler(settings_button, pattern="^(mc|oe)$"),
                CallbackQueryHandler(settings_button, pattern="^quiz_type_.*$"),
                CallbackQueryHandler(settings_button, pattern="^settings_quiz_time$"),
                CallbackQueryHandler(settings_button, pattern="^quiz_time_\\d+$"),
                CallbackQueryHandler(handle_subscription_check, pattern="^check_subscription$"),
                CallbackQueryHandler(handle_back_or_change_questions, pattern="^(back_to_main|change_questions)$"),
                CallbackQueryHandler(handle_back_to_main_menu, pattern="^back_to_main_menu$"),
                CallbackQueryHandler(handle_create_1v1, pattern=r"^(create_1v1_|create_multiplayer_)"),

                MessageHandler(
                    (
                        filters.AUDIO | 
                        filters.VOICE |
                        filters.PHOTO |
                        filters.Document.ALL | 
                        filters.TEXT | 
                        filters.VIDEO |
                        filters.Sticker.ALL
                    ) & ~filters.COMMAND,
                    handle_content
                ),
],
            PROCESSING: [
                CallbackQueryHandler(process_content, pattern=r"^process_"),
                CallbackQueryHandler(handle_quiz_actions, pattern=r"^(start_quiz(?:_[a-f0-9\-]{36})?|quiz_[a-f0-9\-]{36})$"),
                CallbackQueryHandler(quiz_type_handler, pattern=r"^(mc|oe)$"),
                CallbackQueryHandler(handle_set_questions, pattern=r"^set_questions_\d+$"), 
                CallbackQueryHandler(handle_group_quiz_actions, pattern=r"^(start_group_quiz|next_question|finish_quiz)_"),                
                CallbackQueryHandler(handle_subscription_check, pattern="^check_subscription$"),
                CallbackQueryHandler(handle_back_or_change_questions, pattern="^(back_to_main|change_questions)$"),
                CallbackQueryHandler(handle_back_to_main_menu, pattern="^back_to_main_menu$"),
                CallbackQueryHandler(handle_set_quiz_time, pattern=r"^set_quiz_time_\d+$"),
                CallbackQueryHandler(handle_change_quiz_time, pattern="^change_quiz_time$"),
                CallbackQueryHandler(handle_language_detect_selection, pattern=r"^quiz_lang_(auto|uz|en|ru|de|fr|es|ar|ko|zh|hi|bn|ur)$"),
                CallbackQueryHandler(handle_back_to_language_select, pattern="^back_to_language_select$"),
                CallbackQueryHandler(handle_change_quiz_info, pattern="^change_quiz_info$"),
                CallbackQueryHandler(handle_skip_quiz_info, pattern="^skip_quiz_info$"),
                CallbackQueryHandler(handle_create_1v1, pattern=r"^(create_1v1_|create_multiplayer_)"),

                CommandHandler("start", start),
                # CommandHandler("settings", settings_command),
                CommandHandler("help", help_command),
                MessageHandler(
                    filters.AUDIO | 
                    filters.VOICE | 
                    filters.Document.ALL | 
                    filters.TEXT | 
                    filters.VIDEO & ~filters.COMMAND, 
                    handle_content
                ),
            ],
            ASK_QUIZ_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_main_quiz_info),
                CallbackQueryHandler(handle_skip_quiz_info, pattern="^skip_quiz_info$")
            ],


            
        },
        fallbacks=[CommandHandler("start", start)],
        name="main_conversation",
        persistent=False,
    )

    application.add_handler(conv_handler)

    menu_regex = f"^({'|'.join(map(re.escape, ALL_MENU_BUTTON_TEXTS))})$"
    
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(menu_regex),
        handle_orphaned_button
    ))


    application.add_handler(CommandHandler("stopquiz", stop_quiz_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("stats", admin_stats_command))
    application.add_handler(CallbackQueryHandler(handle_view_my_quiz, pattern=r"^view_my_quiz_"))
    application.add_handler(CallbackQueryHandler(handle_back_to_my_quizzes, pattern="^back_to_my_quizzes$"))
    application.add_handler(CallbackQueryHandler(handle_edit_quiz_info_button, pattern=r"^edit_quiz_info_"))
    application.add_handler(CallbackQueryHandler(
        lambda u, c: subscribe_command(u, c),
        pattern="^show_subscription_plans$"
    ))
    application.add_handler(CallbackQueryHandler(
        handle_view_quiz_results, 
        pattern=r"^view_quiz_results_"
    ))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CallbackQueryHandler(settings_button, pattern=r"^(settings_|lang_|mc$|oe$|quiz_type_.*|settings_quiz_time$|quiz_time_\d+$|quiz_questions_\d+$)"))
    application.add_handler(PollAnswerHandler(handle_poll_answer))
    application.add_handler(InlineQueryHandler(handle_inline_query))
    application.add_handler(MessageHandler(filters.POLL, handle_poll_update))  # For group quizzes
    application.add_handler(ChatMemberHandler(handle_my_chat_member, chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CallbackQueryHandler(leaderboard_callback_handler, pattern=r"^leaderboard_"))
    application.add_handler(CallbackQueryHandler(
        handle_group_quiz_actions,
        pattern=r"^(start_group_quiz|next_question|finish_quiz)_"
    ))
    application.add_handler(CallbackQueryHandler(handle_download_quiz, pattern=r"^download_quiz_"))
    application.add_handler(CallbackQueryHandler(handle_subscription_check, pattern="^check_subscription$"))
    application.add_handler(CallbackQueryHandler(
        handle_quiz_actions,
        pattern=r"^(start_quiz(_[0-9a-fA-F\-]{36})?|quiz_[0-9a-fA-F\-]{36})$"
    ))
    application.add_handler(CallbackQueryHandler(
            handle_continue_quiz, 
            pattern=r"^continue_quiz_-?\d+$"
        ))

    application.add_handler(CallbackQueryHandler(
        handle_stop_quiz_pause, 
        pattern=r"^stop_quiz_-?\d+$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        handle_continue_private_quiz, 
        pattern="^continue_private_quiz$"
    ))
    application.add_handler(CallbackQueryHandler(
        handle_stop_private_quiz, 
        pattern="^stop_private_quiz$"
    ))
    application.add_handler(CommandHandler("update_groups", admin_update_groups))
    application.add_handler(CommandHandler("daily", admin_daily_command))
    application.add_handler(CallbackQueryHandler(handle_create_1v1, pattern=r"^(create_1v1_|create_multiplayer_)"))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data_handler))
    application.add_handler(CommandHandler("monthly", admin_monthly_command))
    application.add_handler(CallbackQueryHandler(handle_my_quizzes_page, pattern=r"^my_quizzes_page_\d+$"))
    from handlers.my_quizzes_handlers import handle_quiz_time_menu, handle_quiz_time_set
    application.add_handler(CallbackQueryHandler(handle_quiz_time_menu, pattern=r"^qt_menu_"))
    application.add_handler(CallbackQueryHandler(handle_quiz_time_set, pattern=r"^qt_set_"))
    application.add_handler(TypeHandler(Update, free_users_only_gate), group=-2)
    application.add_handler(PollAnswerHandler(handle_group_poll_answer), group=3)

    from handlers.group_sharing import groupquiz_command
    application.add_handler(CommandHandler("groupquiz", groupquiz_command), group=1)
    logger.info("✅ /groupquiz handler registered")
    setup_payment_handlers(application)
    setup_share_handlers(application)
    setup_manual_payment_handlers(application)
    logger.info("Starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()