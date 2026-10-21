from src.imports import *
from handlers.sharing_quiz import *
from src.user_management import *



async def settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    logger.info(f"Settings button pressed: {query.data} by user {user.id}")
    
    # Handle main settings menu
    if query.data == "settings_command":
        language = await get_user_language(user.id)
        
        current_quiz_type = await get_user_quiz_type(user.id)
        quiz_type_name = "Multiple Choice" if current_quiz_type == "mc" else "Open Ended"
        current_language = LANGUAGES.get(language, "English 🇺🇸")
        
        is_premium = await get_user_premium_status(user.id)
        quiz_time = await get_user_quiz_time(user.id)
        quiz_questions = await get_user_quiz_questions(user.id)
        
        settings_text = (
            f"⚙️ *Settings*\n\n"
            f"🎯 *Quiz Type:* {quiz_type_name}\n"
            f"🌐 *Language:* {current_language}\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("🎯 Quiz Type", callback_data="settings_quiz_type")],
            [InlineKeyboardButton("🌐 Language", callback_data="settings_lang")],
        ]
        
        if is_premium:
            settings_text += f"⏱️ *Quiz Time:* {quiz_time}s per question\n"
            settings_text += f"📝 *Questions:* {quiz_questions} per quiz\n"
            keyboard.extend([
                [InlineKeyboardButton("⏱️ Quiz Time", callback_data="settings_quiz_time")],
                [InlineKeyboardButton("📝 Questions", callback_data="settings_quiz_questions")]
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=settings_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return CONTENT
    
    # Handle back to main menu
    elif query.data == "back_to_main":
        language = await get_user_language(user.id)
        from handlers.start_handler import show_main_menu_with_welcome
        await show_main_menu_with_welcome(update, context, user, language or "en")
        return CONTENT
        
    if query.data == "settings_quiz_type":
        language = await get_user_language(user.id)
        quiz_type_info = QUIZ_TYPE_INFO.get(language, QUIZ_TYPE_INFO["en"])
        keyboard = [
            [InlineKeyboardButton("Multiple Choice ✍️", callback_data="mc")],
            [InlineKeyboardButton("Open Ended 📝", callback_data="oe")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=quiz_type_info,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        logger.info(f"QUIZ TYPE SELECTION DISPLAYED from settings for user {user.id}")
        return CONTENT
    
    if query.data == "settings_lang":
        keyboard = [
            [InlineKeyboardButton(text, callback_data=f"lang_{code}")]
            for code, text in LANGUAGES.items()
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            get_translation("en", "choose_language"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return LANGUAGE
    
    # Handle direct quiz type selection (mc/oe) and quiz_type_ prefixed callbacks
    if query.data in ["mc", "oe"] or query.data.startswith("quiz_type_"):
        quiz_type = query.data.split('_')[-1] if query.data.startswith("quiz_type_") else query.data
        user_id = query.from_user.id
        
        try:
            await update_user_quiz_type(user_id, quiz_type)
            quiz_type_name = "Multiple Choice" if quiz_type == "mc" else "Open Ended"
            language = await get_user_language(user_id)
            
            await query.edit_message_text(
                text=f"✅ *Quiz type updated to {quiz_type_name}*",
                parse_mode=ParseMode.MARKDOWN
            )

            await query.message.reply_text(
                get_translation(language, "send_document"),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error updating quiz type: {e}")
            await query.edit_message_text(
                text="❌ *Error updating quiz type. Please try again.*",
                parse_mode=ParseMode.MARKDOWN
            )
        
        return CONTENT
    
    elif query.data == "settings_quiz_time":
        # Check premium status
        is_premium = await get_user_premium_status(user.id)
        if not is_premium:
            return CONTENT
            
        keyboard = [
            [InlineKeyboardButton("15s", callback_data="quiz_time_15"),
             InlineKeyboardButton("30s", callback_data="quiz_time_30"),
             InlineKeyboardButton("45s", callback_data="quiz_time_45")],
            [InlineKeyboardButton("60s", callback_data="quiz_time_60"),
             InlineKeyboardButton("90s", callback_data="quiz_time_90"),
             InlineKeyboardButton("120s", callback_data="quiz_time_120")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Please select the time limit for each question:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return CONTENT

    elif query.data.startswith("quiz_time_"):
        is_premium = await get_user_premium_status(user.id)
        if not is_premium:
            return CONTENT
            
        time = int(query.data.split('_')[2])
        await update_user_quiz_time(user.id, time)
        await query.edit_message_text(
            text=f"✅ *Quiz time updated to {time} seconds*\n\n*Use /start to begin taking quizzes!*",
            parse_mode=ParseMode.MARKDOWN
        )
        return CONTENT
    
    elif query.data.startswith("quiz_questions_"):
        # Check premium status
        is_premium = await get_user_premium_status(user.id)
        if not is_premium:
            return CONTENT
            
        questions = int(query.data.split('_')[2])
        await update_user_quiz_questions(user.id, questions)
        await query.edit_message_text(
            text=f"✅ *Number of questions updated to {questions}*\n\n*Use /start to begin taking quizzes!*",
            parse_mode=ParseMode.MARKDOWN
        )
        return CONTENT
        
    elif query.data.startswith("lang_"):
        from handlers.start_handler import process_referral_bonus
        from handlers.subscribe import force_subscription_check
        language_code = query.data.split('_')[1]
        
        # Validate language code
        valid_languages = {'en', 'uz', 'ru'}
        if language_code not in valid_languages:
            logger.error(f"Invalid language selection: {language_code}, defaulting to 'uz'")
            language_code = 'uz'
        
        logger.info(f"Language selected: {language_code}")
        
        user = query.from_user
        user_exists = await check_user_exists(user.id)
        invited_by = context.user_data.get('invited_by')
        
        if not user_exists:
            # User doesn't exist - create them
            await create_new_user(
                user_id=user.id,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                username=user.username or "",
                language=language_code,
                quiz_time=30,
                quiz_questions=5,
                inviter_id=invited_by
            )
        else:
            # User exists - just update language
            await update_user_language(user.id, language_code)
            context.user_data["language"] = language_code
        
        # Language confirmation message
        language_messages = {
            "en": "✅ Perfect! English has been set as your language!",
            "ru": "✅ Отлично! Русский язык установлен!",
            "uz": "✅ Ajoyib! O'zbek tili o'rnatildi!"
        }
        
        language_message = language_messages.get(language_code, language_messages["en"])
        
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
        
        # IMMEDIATELY check subscription - this sends subscription message if not subscribed
        if not await force_subscription_check(update, context):
            if invited_by:
                context.user_data['pending_referral'] = {
                    'inviter_id': invited_by,
                    'invited_user_id': user.id,
                    'invited_user_language': language_code
                }
            return ConversationHandler.END
        
        # If subscribed, process referral if applicable
        if invited_by:
            await process_referral_bonus(user.id, invited_by, context, language_code)
            context.user_data.pop('invited_by', None)
        
        # Show main menu
        from handlers.start_handler import show_main_menu_with_welcome
        await show_main_menu_with_welcome(update, context, user, language_code)
        return CONTENT
    
    return None


def normalize_quiz_type(quiz_type: str) -> str:
    """Convert legacy/full quiz_type values to short codes."""
    mapping = {
        "multiple_choice": "mc",
        "open_ended": "oe",
        "mc": "mc",
        "oe": "oe"
    }
    return mapping.get(quiz_type, "mc")  




async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_chat_action("typing")
    
    language = await get_user_language(user.id)
    quiz_type = await get_user_quiz_type(user.id) 
    quiz_type = normalize_quiz_type(quiz_type)
    quiz_time = await get_user_quiz_time(user.id)
    is_premium = await get_user_premium_status(user.id)

    keyboard = [
        [InlineKeyboardButton(get_translation(language, "language"), callback_data="settings_lang")],
        [InlineKeyboardButton(get_translation(language, "quiz_type"), callback_data="settings_quiz_type")]
    ]
    
    if is_premium:
        keyboard.extend([
            [InlineKeyboardButton(f"⏱️ Quiz Time: {quiz_time}s", callback_data="settings_quiz_time")],
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Base message with common settings
    message = (
        f"{get_translation(language, 'settings')}:\n\n"
        f"{get_translation(language, 'current_language')} {LANGUAGES[language]}\n"
        f"{get_translation(language, 'current_quiz_type')} {QUIZ_TYPES[quiz_type]}"
    )
    
    # Add premium settings info only if user is premium
    if is_premium:
        message += f"\n⏱️ *Current quiz time:* {quiz_time} seconds\n"
    
    await update.message.reply_text(
        message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

