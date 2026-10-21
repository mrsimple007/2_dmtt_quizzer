import asyncio
import logging
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode
from src.user_management import get_user_language, get_invited_users_count_cached
from src.async_utils import fire_and_forget
from src.perf_timing import track_handler
from src.prompts_summarize import TRANSLATIONS

logger = logging.getLogger(__name__)


REFERRAL_REWARD_UZS = 2000      # used to be 2000 in share_main and 3000 in share_and_earn. Set the real value
MAX_REFERRALS = 200

logger = logging.getLogger(__name__)

# Translations for share messages in HTML format (for bot display)
SHARE_TRANSLATIONS = {
    "en": {
        "share_text_plain": """🎉 Creating amazing quizzes has never been this easy!
🪄 Convert text, documents, audio or video into professional quizzes in just seconds!
📎 No complexity - just upload and it's ready!
👫 For every friend who joins through your link - 1 presentation FREE!
📈 No limit on invitations - more friends, more opportunities!
🚀 Join me and start for free right now!""",
        
        "share_text_intro": "- This is my referral link 👉",
        "share_message": """🔗 <b>Share and get 1 free quiz</b>

Your referral link:
<code>{referral_link}</code>

<b>How it works:</b>
• Share this link with your friends
• When they join through your link, you can create 1 free presentation
• You can invite up to 200 friends

<b>Your statistics:</b>
• Invited friends: <b>{invited_count}</b>
• Total earned: <b>{earned_amount} UZS</b>""",
        "share_telegram": "📱 Share on Telegram",
        "back_to_menu": "🔙 Back to Menu"
    },
    "ru": {
        "share_text_plain": """🎉 Создание потрясающих квиззов никогда не было таким простым!
🪄 Превращайте текст, документы, аудио или видео в профессиональные квизы всего за секунды!
📎 Никаких сложностей - просто загрузите и готово!
👫 За каждого друга, присоединившегося по вашей ссылке - 1 презентация БЕСПЛАТНО!
📈 Нет ограничений на приглашения - больше друзей, больше возможностей!
🚀 Присоединяйтесь ко мне и начинайте бесплатно прямо сейчас!""",
        
        "share_text_intro": "- Это моя реферальная ссылка 👉",
        "share_message": """🔗 <b>Поделитесь и получите 1 бесплатный квиз</b>

Ваша реферальная ссылка:
<code>{referral_link}</code>

<b>Как это работает:</b>
• Поделитесь этой ссылкой с друзьями
• Когда они присоединятся по вашей ссылке, вы сможете создать 1 бесплатную презентацию
• Вы можете приглашать до 200 друзей

<b>Ваша статистика:</b>
• Приглашенных друзей: <b>{invited_count}</b>
• Всего заработано: <b>{earned_amount} UZS</b>""",
        "share_telegram": "📱 Поделиться в Telegram",
        "back_to_menu": "🔙 Назад в меню"
    },
    "uz": {   
        "share_text_plain": """🎉 Ajoyib quizlar yaratish hech qachon bu qadar oson bo'lmagan!
🪄 Matn, hujjat, audio yoki videoni atigi bir necha soniyada professional quizlarga aylantiring!
📎 Hech qanday murakkablik yo'q - faqat yuklang va tayyor!
👫 Har bir do'stingiz sizning havolangiz orqali qo'shilsa - 1 ta quiz BEPUL!
📈 Takliflar cheklanmagan - ko'proq do'st, ko'proq imkoniyatlar!
🚀 Men bilan qo'shiling va hoziroq bepul boshlang!""",
        
        "share_text_intro": "- Bu mening referral linkim 👉",
        "share_message": """🔗 <b>Ulashing va 1 ta bepul quiz yarating</b>

Sizning referral havolangiz:
<code>{referral_link}</code>

<b>Qanday ishlaydi:</b>
• Ushbu havolangizni do'stlaringiz bilan ulashing
• Ular sizning havolangiz orqali qo'shilganda, siz 1 ta bepul prezentatsiya yarata olasiz
• Siz 200 tagacha do'st taklif qilishingiz mumkin

<b>Sizning statistikangiz:</b>
• Taklif qilingan do'stlar: <b>{invited_count}</b>
• Jami ishlangan: <b>{earned_amount} UZS</b>""",
        "share_telegram": "📱 Telegram'da ulashish",
        "back_to_menu": "🔙 Menyuga qaytish"
    }
}


_LIMIT_MESSAGES = {
    "en": """🎉 <b>Maximum Referral Limit Reached!</b>

Your referral link:
<code>{referral_link}</code>

<b>Your statistics:</b>
- Invited friends: <b>{invited_count}/200 (MAX)</b>
- Total earned: <b>{earned_amount} UZS</b>

🏆 You've reached the maximum referral limit! You cannot earn more referral bonuses, but you can top up your balance anytime.

Thank you for your amazing support! 🙏""",
    "ru": """🎉 <b>Достигнут максимальный лимит рефералов!</b>

Ваша реферальная ссылка:
<code>{referral_link}</code>

<b>Ваша статистика:</b>
- Приглашенных друзей: <b>{invited_count}/200 (МАКС)</b>
- Всего заработано: <b>{earned_amount} UZS</b>

🏆 Вы достигли максимального лимита рефералов! Вы больше не можете зарабатывать реферальные бонусы, но можете пополнить баланс в любое время.

Спасибо за вашу потрясающую поддержку! 🙏""",
    "uz": """🎉 <b>Maksimal referral limitga erishildi!</b>

Sizning referral havolangiz:
<code>{referral_link}</code>

<b>Sizning statistikangiz:</b>
- Taklif qilingan do'stlar: <b>{invited_count}/200 (MAKS)</b>
- Jami ishlangan: <b>{earned_amount} UZS</b>

🏆 Siz maksimal referral limitga yetdingiz (200 ta)! Endi referral orqali bonuslar ishlay olmaysiz, lekin balansni istalgan vaqtda to'ldirishingiz mumkin.

Botimizni qo'llab-quvvatlaganingiz uchun rahmat! 🙏""",
}

_PROGRESS = {
    "en": "\n\n📊 <b>Progress:</b> {n}/200 referrals",
    "ru": "\n\n📊 <b>Прогресс:</b> {n}/200 рефералов",
    "uz": "\n\n📊 <b>Limit:</b> {n}/200 referal",
}

@track_handler("share")
async def share_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # stop the button spinner immediately; no awaited typing indicator
    if update.callback_query:
        fire_and_forget(update.callback_query.answer())

    language, invited_count = await asyncio.gather(
        get_user_language(user.id),
        get_invited_users_count_cached(user.id),      # cached 60 s, and it's a COUNT query now
        return_exceptions=True,
    )
    if isinstance(language, Exception) or not language:
        language = "en"
    if isinstance(invited_count, Exception):
        invited_count = 0

    tr = SHARE_TRANSLATIONS.get(language, SHARE_TRANSLATIONS["en"])
    bot_username = context.bot.username or "simplequizzer_bot"
    referral_link = f"https://t.me/{bot_username}?start=ref_{user.id}"      # no trailing space any more
    earned = invited_count * REFERRAL_REWARD_UZS

    if invited_count >= MAX_REFERRALS:
        share_message = _LIMIT_MESSAGES.get(language, _LIMIT_MESSAGES["en"]).format(
            referral_link=referral_link, invited_count=invited_count, earned_amount=earned)
    else:
        share_message = tr["share_message"].format(
            referral_link=referral_link, invited_count=invited_count, earned_amount=earned)
        share_message += _PROGRESS.get(language, _PROGRESS["en"]).format(n=invited_count)

    share_text_full = f"{tr['share_text_plain']}\n\n{tr['share_text_intro']} {referral_link}"
    share_url = ("https://t.me/share/url?url=" + urllib.parse.quote(referral_link)
                 + "&text=" + urllib.parse.quote(share_text_full))

    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(tr["share_telegram"], url=share_url)],
        [InlineKeyboardButton(tr["back_to_menu"], callback_data="back_to_main")],
    ])

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                share_message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        except Exception:
            await update.callback_query.message.reply_text(
                share_message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(
            share_message, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


# the second, near-duplicate implementation was inconsistent (3000 vs 2000 per friend)
share_and_earn = share_main


async def back_to_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.start_handler import start
    await start(update, context)


def setup_share_handlers(application):
    application.add_handler(CommandHandler("share", share_main))
    application.add_handler(CallbackQueryHandler(back_to_main_callback, pattern="^back_to_main$"))
