import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import ContextTypes
from telegram.error import TelegramError, Forbidden, BadRequest
import asyncio
from src.cache import cache_get, cache_set

SUB_OK_TTL = 3600

logger = logging.getLogger(__name__)

FORCE_SUBSCRIPTION_ENABLED = True 

REQUIRED_CHANNELS = [
    # {
    #     'id': '@SimpleLearnUz',  
    #     'name': 'Simple Learn AI',
    #     'url': 'https://t.me/SimpleLearnUz'
    # },
    # {
    #     'id': '@uzbek_europe',  
    #     'name': 'Yevropalik o\'zbek',
    #     'url': 'https://t.me/uzbek_europe'
    # },
    # {
    #     'id': '@Muslimbek_01',
    #     'name': 'Simple Quizzer | Official',
    #     'url': 'https://t.me/muslimbek_01'
    # },

        # {
        #     'id': '@talabaga_tezkor_yordam',  
        #     'name': 'Talabalarga sifatli yordam',
        #     'url': 'https://t.me/talabaga_tezkor_yordam'
        # },
        # {
        #     'id': '@studentlarga_kvartiral',  
        #     'name': 'Studentlarga kvartiralar | Maklersiz',
        #     'url': 'https://t.me/studentlarga_kvartiral'
        # },

        {
            'id': '@DMTT_attestat_HulkarIbragimova',  
            'name': 'Hulkar Ibragimova shaxsiy kanali',
            'url': 'https://t.me/DMTT_attestat_HulkarIbragimova'
        },

        {
            'id': '@MTT_direktorlari',  
            'name': 'MTT direktorlari',
            'url': 'https://t.me/MTT_direktorlari'
        },


    # {
    #     'id': '@Ai_zonez',
    #     'name': 'AI yangiliklari',
    #     'url': 'https://t.me/ai_zonez'
    # },
    # {
    #     'id': '@Intellektualyoshlar',
    #     'name': 'Simple Quizzer | Official',
    #     'url': 'https://t.me/intellektualyoshlar'
    # },
]


SUBSCRIPTION_MESSAGES = {
    "en": {
        "welcome_title": "🌟 <b>Welcome!</b>",
        "instruction": (
            "To use this bot, please subscribe to our partner channels below 👇\n\n"
            "📌 <i>This helps us keep the bot free and continuously improve it.</i>\n\n"
        ),
        "subscribe_btn": "📢 ",
        "check_btn": "✅ Check Subscription",
        "success": (
            "🎉 <b>Perfect!</b>\n\n"
            "You're all set and ready to go 🚀\n\n"
            "👉 Type /start to begin using the bot.\n\n"
            "💡 With /info you can learn more about us."
        ),
        "still_required": (
            "❌ <b>Almost there!</b>\n\n"
            "It looks like you haven't subscribed to all required channels yet.\n\n"
            "🔁 Please subscribe to all channels and tap <b>“I Subscribed”</b> again."
        ),
        "checking": (
            "🔍 <b>Checking your subscription...</b>\n\n"
            "⏳ This will only take a moment. Please wait."
        ),
        "error": (
            "❌ <b>Something went wrong</b>\n\n"
            "Please send /start again or try in a few seconds."
        )
    },

    "uz": {
        "welcome_title": "🌟 <b>Xush kelibsiz!</b>",
        "instruction": (
            "Botdan cheklovlarsiz foydalanish uchun quyidagi hamkor kanallarimizga obuna bo'ling 👇\n\n"
            "📌 <i>Bu bizga botni bepul va yanada sifatli qilishga yordam beradi.</i>\n\n"
        ),
        "subscribe_btn": "📢 ",
        "check_btn": "✅ Obunani Tekshirish",
        "success": (
            "🎉 <b>Ajoyib!</b>\n\n"
            "Hammasi tayyor ✅ Endi botdan hech qanday cheklovlarsiz foydalanishingiz mumkin. 👉 Boshlash uchun /start yuboring.\n\n"
            "💡 /info orqali biz haqimizda yanada ko‘proq bilib olishingiz mumkin."
        ),
        "still_required": (
            "❌ <b>Deyarli tayyor!</b>\n\n"
            "Siz hali barcha kerakli kanallarga obuna bo‘lmadingiz.\n\n"
            "🔁 Iltimos, barchasiga obuna bo‘lib, qayta tekshiring."
        ),
        "checking": (
            "🔍 <b>Obuna tekshirilmoqda...</b>\n\n"
            "⏳ Iltimos, biroz kuting."
        ),
        "error": (
            "❌ <b>Xatolik yuz berdi</b>\n\n"
            "Iltimos, /start ni qayta yuboring yoki birozdan so‘ng urinib ko‘ring."
        )
    },

    "ru": {
        "welcome_title": "🌟 <b>Добро пожаловать!</b>",
        "instruction": (
            "Чтобы пользоваться ботом, подпишитесь на наши партнерские каналы ниже 👇\n\n"
            "📌 <i>Это помогает нам поддерживать бот бесплатным и улучшать его.</i>\n\n"
        ),
        "subscribe_btn": "📢 ",
        "check_btn": "✅ Проверить подписку",
        "success": (
            "🎉 <b>Отлично!</b>\n\n"
            "Все готово ✅ Вы можете начать пользоваться ботом.\n\n"
            "👉 Напишите /start, чтобы продолжить.\n\n"
            "💡 С помощью /info вы можете узнать больше о нас."
        ),
        "still_required": (
            "❌ <b>Почти готово!</b>\n\n"
            "Вы подписались не на все обязательные каналы.\n\n"
            "🔁 Пожалуйста, подпишитесь на все каналы и попробуйте снова."
        ),
        "checking": (
            "🔍 <b>Проверяем подписку...</b>\n\n"
            "⏳ Пожалуйста, подождите немного."
        ),
        "error": (
            "❌ <b>Что-то пошло не так</b>\n\n"
            "Пожалуйста, отправьте /start еще раз или попробуйте позже."
        )
    }
}



async def create_subscription_keyboard(unsubscribed_channels: list, language: str = "uz") -> InlineKeyboardMarkup:
    """Create subscription keyboard with language support"""
    keyboard = []
    texts = SUBSCRIPTION_MESSAGES.get(language, SUBSCRIPTION_MESSAGES["uz"])
    
    # Add subscription buttons for each unsubscribed channel
    for channel in unsubscribed_channels:
        keyboard.append([
            InlineKeyboardButton(
                f"{texts['subscribe_btn']}{channel['name']}", 
                url=channel['url']
            )
        ])
    
    # Add check subscription button
    keyboard.append([
        InlineKeyboardButton(
            texts['check_btn'],
            callback_data="check_subscription"
        )
    ])
    
    return InlineKeyboardMarkup(keyboard)


async def handle_unsubscribed_user(update: Update, context: ContextTypes.DEFAULT_TYPE, unsubscribed_channels: list):
    """Handle user who is not subscribed to required channels - with language support"""
    from src.user_management import get_user_language
    
    user = update.effective_user
    
    # Get user's language (default to 'uz' if not set)
    language = await get_user_language(user.id) or 'uz'
    texts = SUBSCRIPTION_MESSAGES.get(language, SUBSCRIPTION_MESSAGES["uz"])
    
    # Build message
    message = f"{texts['welcome_title']}\n\n{texts['instruction']}"
    
    keyboard = await create_subscription_keyboard(unsubscribed_channels, language)
    
    try:
        if update.message:
            await update.message.reply_text(
                message,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        elif update.callback_query:
            await context.bot.send_message(
                chat_id=user.id,
                text=message,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"❌ Error sending subscription message to user {user.id}: {e}")


async def handle_subscription_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Optimized subscription check with language support"""
    from src.user_management import get_user_language
    
    query = update.callback_query
    if not query:
        return
    
    user = query.from_user
    if not user:
        return
    
    # Get user language
    language = await get_user_language(user.id) or 'uz'
    texts = SUBSCRIPTION_MESSAGES.get(language, SUBSCRIPTION_MESSAGES["uz"])
    
    try:
        await query.answer(texts['checking'], show_alert=False)
        await query.edit_message_text(texts['checking'], parse_mode='HTML')
    except Exception as e:
        logger.error(f"❌ Error showing checking message: {e}")
        return
    
    try:
        subscription_status = await check_user_subscriptions(user.id, context)
        
        if subscription_status['is_subscribed']:
            logger.info(f"🎉 User {user.id} is now subscribed to all channels!")
            
            # Check for pending referral
            pending_referral = context.user_data.get('pending_referral')
            if pending_referral:
                logger.info(f"✅ Processing pending referral bonus for user {user.id}")
                
                from handlers.start_handler import process_referral_bonus
                
                await process_referral_bonus(
                    invited_user_id=pending_referral['invited_user_id'],
                    inviter_id=pending_referral['inviter_id'],
                    context=context,
                    invited_user_language=pending_referral['invited_user_language']
                )
                
                context.user_data.pop('pending_referral', None)
                
                # Success message with bonus notification
                success_bonus = {
                    "en": texts['success'] + "\n\n🎉 <b>Referral bonus activated!</b>\nYour friend received their bonus!",
                    "ru": texts['success'] + "\n\n🎉 <b>Реферальный бонус активирован!</b>\nВаш друг получил бонус!",
                    "uz": texts['success'] + "\n\n🎉 <b>Referral bonusi faollashtirildi!</b>\nDo'stingiz bonusni oldi!"
                }
                success_text = success_bonus.get(language, success_bonus["uz"])
            else:
                success_text = texts['success']
            
            try:
                await query.edit_message_text(success_text, parse_mode='HTML')
            except Exception as e:
                logger.error(f"❌ Error editing success message: {e}")
            
            # Send /start instruction
            start_instruction = {
                "en": "👉 Type /start to begin!",
                "ru": "👉 Напишите /start чтобы начать!",
                "uz": "👉 Boshlash uchun /start yuboring!"
            }
            
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=start_instruction.get(language, start_instruction["uz"]),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"❌ Error sending start instruction: {e}")
        
        else:
            # Still not subscribed
            keyboard = await create_subscription_keyboard(
                subscription_status['unsubscribed_channels'], 
                language
            )
            
            try:
                await query.edit_message_text(
                    texts['still_required'],
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"❌ Error editing 'still not subscribed' message: {e}")
    
    except Exception as e:
        logger.error(f"❌ Subscription check error: {e}")
        try:
            await query.edit_message_text(texts['error'], parse_mode='HTML')
        except:
            pass



async def check_user_subscriptions(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Optimized parallel subscription check"""
    
    async def check_single_channel(channel):
        try:
            chat_member = await context.bot.get_chat_member(
                chat_id=channel['id'],
                user_id=user_id
            )
            is_subscribed = chat_member.status not in [ChatMember.LEFT, ChatMember.BANNED]
            return (channel, is_subscribed)
        except Exception as e:
            logger.error(f"Error checking {channel['id']}: {e}")
            return (channel, False)
    
    # Check all channels in parallel instead of sequentially
    results = await asyncio.gather(
        *[check_single_channel(ch) for ch in REQUIRED_CHANNELS],
        return_exceptions=True
    )
    
    unsubscribed_channels = []
    for result in results:
        if isinstance(result, Exception):
            continue
        channel, is_subscribed = result
        if not is_subscribed:
            unsubscribed_channels.append(channel)
    
    is_fully_subscribed = len(unsubscribed_channels) == 0
    
    return {
        'is_subscribed': is_fully_subscribed,
        'unsubscribed_channels': unsubscribed_channels
    }



async def force_subscription_check(update, context) -> bool:
    if not FORCE_SUBSCRIPTION_ENABLED:
        return True
    chat = update.effective_chat
    if chat and chat.type != "private":
        return True

    status = await check_user_subscriptions(user.id, context)
    if status['is_subscribed']:
        cache_set(("sub_ok", user.id), True, SUB_OK_TTL)
        return True

    await handle_unsubscribed_user(update, context, status['unsubscribed_channels'])
    return False


async def subscription_required_decorator(func):
    """Decorator to check subscription before executing function"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            logger.error("❌ No user found in decorator")
            return
        
        subscription_status = await check_user_subscriptions(user.id, context)
        
        if not subscription_status['is_subscribed']:
            await handle_unsubscribed_user(update, context, subscription_status['unsubscribed_channels'])
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


async def force_subscription_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Force check subscription and block if not subscribed"""
    user = update.effective_user
    if not user:
        logger.error("❌ No user found in force check")
        return False
    
    if user.id == 200713886:  
        return True

    logger.info(f"🔒 Force checking subscription for user {user.id}")
    subscription_status = await check_user_subscriptions(user.id, context)
    
    if not subscription_status['is_subscribed']:
        await handle_unsubscribed_user(update, context, subscription_status['unsubscribed_channels'])
        return False
    
    return True


def setup_subscription_handlers(application):
    from telegram.ext import CallbackQueryHandler
    # Add the callback query handler
    subscription_handler = CallbackQueryHandler(
        handle_subscription_check,
        pattern="^check_subscription$"
    )
    
    application.add_handler(subscription_handler)
    
    # Log all registered handlers for debugging
    logger.info(f"📋 Total handlers registered: {len(application.handlers)}")
    for group_id, handlers in application.handlers.items():
        logger.info(f"📋 Group {group_id}: {len(handlers)} handlers")
        for handler in handlers:
            logger.info(f"📋   - {type(handler).__name__}: {getattr(handler, 'pattern', 'No pattern')}")


async def validate_bot_configuration(context: ContextTypes.DEFAULT_TYPE) -> bool:
    logger.info("🔍 Validating bot configuration for subscription checking...")
    
    for channel in REQUIRED_CHANNELS:
        try:
            chat = await context.bot.get_chat(channel['id'])
            
            try:
                bot_member = await context.bot.get_chat_member(channel['id'], context.bot.id)
                if bot_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                    logger.info(f"✅ Bot is admin in channel: {chat.title}")
                else:
                    logger.warning(f"⚠️ Bot is not admin in channel: {chat.title}. Some features may not work properly.")
            except Exception as e:
                logger.warning(f"⚠️ Could not check bot admin status in {chat.title}: {e}")
                
        except Exception as e:
            logger.error(f"❌ Bot cannot access channel {channel['id']}: {e}")
            return False
    
    return True