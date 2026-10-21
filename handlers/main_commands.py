import os
import logging
from datetime import datetime, timezone
import asyncio
import re
import uuid
import json
import random
import time
import threading
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, filters, ContextTypes, PollAnswerHandler, InlineQueryHandler
)
from telegram.constants import ParseMode


STOP_TEXTS = {
    "en": {
        "none": "❌ No active quiz to stop in this group.",
        "stopped": "🛑 <b>Quiz Stopped</b>\n\nQuiz: \"{title}\"\n\n<b>Thank You for participating!</b>",
        "stopped_empty": "🛑 <b>Quiz Stopped</b>\n\nNo answers were recorded.",
        "error": "❌ Error stopping the quiz.",
        "group_only": "❌ This command only works in groups.",
        "thanks": "🛑 <b>Quiz Stopped</b>\n\nThank you for participating!",
    },
    "uz": {
        "none": "❌ Bu guruhda to'xtatish uchun faol quiz yo'q.",
        "stopped": "🛑 <b>Quiz to'xtatildi</b>\n\nQuiz: \"{title}\"\n\n<b>Ishtirok etganingiz uchun rahmat!</b>",
        "stopped_empty": "🛑 <b>Quiz to'xtatildi</b>\n\nHech qanday javob qayd etilmadi.",
        "error": "❌ Quizni to'xtatishda xatolik.",
        "group_only": "❌ Bu buyruq faqat guruhlarda ishlaydi.",
        "thanks": "🛑 <b>Quiz to'xtatildi</b>\n\nIshtirok etganingiz uchun rahmat!",
    },
    "ru": {
        "none": "❌ В этой группе нет активной викторины.",
        "stopped": "🛑 <b>Квиз остановлен</b>\n\nКвиз: \"{title}\"\n\n<b>Спасибо за участие!</b>",
        "stopped_empty": "🛑 <b>Квиз остановлен</b>\n\nОтветов не зафиксировано.",
        "error": "❌ Ошибка при остановке квиза.",
        "group_only": "❌ Эта команда работает только в группах.",
        "thanks": "🛑 <b>Квиз остановлен</b>\n\nСпасибо за участие!",
    },
}


def stop_t(lang: str) -> dict:
    return STOP_TEXTS.get(lang, STOP_TEXTS["en"])


async def stop_quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from handlers.group_sharing import stop_group_quiz
    """Handle /stopquiz command."""
    if not update.message or not update.message.chat:
        return
        
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    
    if update.message.chat.type not in ["group", "supergroup"]:
        from src.user_management import get_user_language
        lang = await get_user_language(user_id)
        await update.message.reply_text(stop_t(lang)["group_only"])
        return
    
    await stop_group_quiz(context, chat_id, user_id)

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.user_management import get_user_language
    from src.prompts_summarize import INFO_TEXTS
    
    user_id = update.effective_user.id
    language = await get_user_language(user_id) or 'en'  # ✅ Added await
    text = INFO_TEXTS.get(language, INFO_TEXTS['en'])
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.imports import ADMIN_CHAT_ID
    logger = logging.getLogger(__name__)
    """Show admin statistics for Simple Quizzer."""
    from src.user_management import (
        get_top_paying_quiz_users, 
        get_monthly_quiz_revenue, 
        get_total_quiz_revenue
    )
    
    AUTHORIZED_ADMINS = ["8437026582", "999932510", ADMIN_CHAT_ID]
    if str(update.effective_user.id) not in AUTHORIZED_ADMINS:
        await update.message.reply_text("❌ Unauthorized")
        return
    
    try:
        now = datetime.now()
        monthly_revenue = await get_monthly_quiz_revenue(now.year, now.month)
        total_revenue = await get_total_quiz_revenue()
        top_payers = await get_top_paying_quiz_users(limit=10)
        
        message = f"""📊 <b>Simple Quizzer Statistics</b>
━━━━━━━━━━━━━━━━━━━━━━

💰 <b>Revenue</b>
- This month: {monthly_revenue / 100:,.0f} UZS
- All time: {total_revenue / 100:,.0f} UZS

👑 <b>Top 10 Paying Users</b>
"""
        
        if not top_payers:
            message += "\nNo payment data yet."
        else:
            for idx, user in enumerate(top_payers, 1):
                user_id = user['user_id']
                total_paid = user.get('total_payments', 0) / 100
                first_name = user.get('first_name', 'Unknown')
                username = user.get('username', '')
                
                user_display = f"{first_name}"
                if username:
                    user_display += f" @{username}"
                
                message += f"{idx}. {user_display}\n"
                message += f"   ID: <code>{user_id}</code> - {total_paid:,.0f} UZS\n"
        
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error in admin_stats_command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")



async def handle_orphaned_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.imports import logger
    from src.user_management import get_user_language
    from telegram import KeyboardButton, ReplyKeyboardMarkup
    """Handle orphaned keyboard buttons when bot restarts or conversation ends."""
    user = update.message.from_user
    text = update.message.text.strip()
    
    logger.info(f"Orphaned button pressed by user {user.id}: {text}")
    
    # Get user language
    language = await get_user_language(user.id) or 'en'
    
    # Prepare restart message
    restart_messages = {
        'uz': "🔄 Iltimos, botni qayta ishga tushiring.\n\nViktorina yaratishni boshlash uchun /start buyrug'ini yuboring.",
        'ru': "🔄 Пожалуйста, перезапустите бота.\n\nОтправьте команду /start, чтобы начать создание викторины.",
        'en': "🔄 Please restart the bot.\n\nSend /start command to begin creating a quiz."
    }
    
    restart_msg = restart_messages.get(language, restart_messages['en'])
    
    # Send restart message with /start button
    keyboard = [[KeyboardButton("/start")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        restart_msg,
        reply_markup=reply_markup
    )
    
    # Clear any existing user data
    context.user_data.clear()
    
    return ConversationHandler.END


# Add this list before the main() function to collect all menu button texts
ALL_MENU_BUTTON_TEXTS = [
    # English
    '🎯 Create Quiz',
    '⚙️ Settings',
    '❓ Help',
    '💰 Balance',
    '🔗 Share & Earn',
    
    '📂 Split Quiz Hemis',
    
    # Uzbek
    '🎯 Quiz yaratish',
    '⚙️ Sozlamalar',
    '❓ Yordam',
    '💰 Balans',
    '🔗 Ulashing va bepul quiz',
    '📂 Hemis quizni bo\'lish',
    
    # Russian
    '🎯 Создать викторину',
    '⚙️ Настройки',
    '❓ Помощь',
    '💰 Баланс',
    '🔗 Поделиться и заработать',
    '📂 Разделить квиз Hemis',
    "↩️ Back to Menu",
    "↩️ Menyuga Qaytish", 
    "↩️ Вернуться в меню",

            "📚 My Quizzes",
            "📚 Mening Quizlarim",
            "📚 Мои Викторины",
]


async def admin_update_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from src.user_management import update_existing_groups_member_count
    """Admin command to update member counts for all groups."""
    user = update.effective_user
    
    if str(user.id) != "999932510":
        await update.message.reply_text("⛔ Unauthorized access.")
        return
    
    await update.message.reply_text("🔄 Starting to update member counts for all groups...")
    
    updated, failed = await update_existing_groups_member_count(context)
    
    await update.message.reply_text(
        f"✅ Update complete!\n\n"
        f"✓ Successfully updated: {updated}\n"
        f"✗ Failed: {failed}"
    )

from datetime import timedelta

async def admin_daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.imports import ADMIN_CHAT_ID, logger
    from src.user_management import get_daily_revenue
    """Show today's revenue statistics."""
    # Check if user is authorized admin
    AUTHORIZED_ADMINS = ["8437026582", "999932510", ADMIN_CHAT_ID]
    if str(update.effective_user.id) not in AUTHORIZED_ADMINS:
        await update.message.reply_text("❌ Unauthorized")
        return
    
    try:
        # Get today's revenue
        today = datetime.now(timezone.utc)
        daily_revenue = await get_daily_revenue(today)
        
        # Get yesterday's revenue for comparison
        yesterday = today - timedelta(days=1)
        yesterday_revenue = await get_daily_revenue(yesterday)
        
        # Calculate change
        if yesterday_revenue > 0:
            change_percent = ((daily_revenue - yesterday_revenue) / yesterday_revenue) * 100
            change_emoji = "📈" if change_percent > 0 else "📉" if change_percent < 0 else "➡️"
            change_text = f"{change_emoji} {change_percent:+.1f}% from yesterday"
        else:
            change_text = "📊 No data from yesterday"
        
        message = f"""📅 <b>Daily Revenue Report</b>
━━━━━━━━━━━━━━━━━━━━━━

📆 <b>Date:</b> {today.strftime('%B %d, %Y')}

💰 <b>Today's Revenue:</b> {daily_revenue / 100:,.0f} UZS
💵 <b>Yesterday's Revenue:</b> {yesterday_revenue / 100:,.0f} UZS

{change_text}
"""
        
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Error in admin_daily_command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def admin_monthly_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from src.imports import ADMIN_CHAT_ID, logger
    from src.user_management import get_monthly_quiz_revenue

    AUTHORIZED_ADMINS = ["8437026582", "999932510", ADMIN_CHAT_ID]
    if str(update.effective_user.id) not in AUTHORIZED_ADMINS:
        await update.message.reply_text("❌ Unauthorized")
        return

    try:
        now = datetime.now(timezone.utc)

        # Current and previous month revenue
        current_revenue = await get_monthly_quiz_revenue(now.year, now.month)

        # Calculate previous month
        if now.month == 1:
            prev_year, prev_month = now.year - 1, 12
        else:
            prev_year, prev_month = now.year, now.month - 1

        prev_revenue = await get_monthly_quiz_revenue(prev_year, prev_month)

        # Calculate change
        if prev_revenue > 0:
            change_percent = ((current_revenue - prev_revenue) / prev_revenue) * 100
            change_emoji = "📈" if change_percent > 0 else "📉" if change_percent < 0 else "➡️"
            change_text = f"{change_emoji} {change_percent:+.1f}% from last month"
        else:
            change_text = "📊 No data from last month"

        month_name = now.strftime('%B %Y')
        prev_month_name = datetime(prev_year, prev_month, 1).strftime('%B %Y')

        message = f"""📅 <b>Monthly Revenue Report</b>
━━━━━━━━━━━━━━━━━━━━━━

📆 <b>Month:</b> {month_name}

💰 <b>This Month:</b> {current_revenue / 100:,.0f} UZS
💵 <b>Last Month ({prev_month_name}):</b> {prev_revenue / 100:,.0f} UZS

{change_text}
"""

        await update.message.reply_text(message, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in admin_monthly_command: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")