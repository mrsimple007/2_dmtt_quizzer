from src.tables import TBL
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction
from supabase import create_client, Client
from src.user_management import get_user_language
from src.imports import *
import asyncio

from zoneinfo import ZoneInfo  
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")

logger = logging.getLogger(__name__)

LEADERBOARD_MESSAGES = {
    'en': {
        'title': '🏆 *Leaderboard*',
        'period_month': '📊 *Most Active Users (This Month)*\n\nCalculated from *{} to {}*',
        'no_data': 'No active users found for this period.',
        'user_format': '{}. {} - {} quizzes ({})',
        'your_rank': '\n🎯 *Your Position:* #{} - {} quizzes ({})',
        'not_ranked': '\n🎯 *Your Position:* Not ranked yet',
        'buttons': {
            'refresh': '🔄 Refresh',
            'back': '🔙 Back'
        }
    },
    'ru': {
        'title': '🏆 *Таблица лидеров*',
        'period_month': '📊 *Самые активные пользователи (Этот месяц)*\n\nРассчитано с *{} по {}*',
        'no_data': 'Активные пользователи за этот период не найдены.',
        'user_format': '{}. {} - {} викторин ({})',
        'your_rank': '\n🎯 *Ваша позиция:* #{} - {} викторин ({})',
        'not_ranked': '\n🎯 *Ваша позиция:* Еще не в рейтинге',
        'buttons': {
            'refresh': '🔄 Обновить',
            'back': '🔙 Назад'
        }
    },
    'uz': {
        'title': '🏆 *Liderlar jadvali*',
        'period_month': '📊 *Eng faol foydalanuvchilar (Bu oy)*\n\n*{} dan {} gacha hisoblangan*',
        'no_data': 'Bu davr uchun faol foydalanuvchilar topilmadi.',
        'user_format': '{}. {} - {} viktorina ({})',
        'your_rank': '\n🎯 *Sizning pozitsiyangiz:* #{} - {} viktorina ({})',
        'not_ranked': '\n🎯 *Sizning pozitsiyangiz:* Hali reytingda emas',
        'buttons': {
            'refresh': '🔄 Yangilash',
            'back': '🔙 Orqaga'
        }
    }
}

_leaderboard_cache = {
    'data': None,
    'timestamp': None,
    'month_start': None
}

CACHE_DURATION = 300

def get_current_month_range() -> Tuple[datetime, datetime]:
    now = datetime.now(TASHKENT_TZ)
    # Always use 23:59 as the cutoff time
    start_of_month = now.replace(day=7, hour=23, minute=59, second=59, microsecond=999999)
    
    # If we're before the 7th at 23:59, use previous month's 7th at 23:59 as start
    if now.day < 7 or (now.day == 7 and now.hour < 23) or (now.day == 7 and now.hour == 23 and now.minute < 59):
        if now.month == 1:
            start_of_month = start_of_month.replace(year=now.year - 1, month=12)
        else:
            start_of_month = start_of_month.replace(month=now.month - 1)
    
    # Calculate end date (7th of next month at 23:59)
    if start_of_month.month == 12:
        next_month = start_of_month.replace(year=start_of_month.year + 1, month=1)
    else:
        next_month = start_of_month.replace(month=start_of_month.month + 1)
    # Set end time to 23:59:59
    end_of_month = next_month.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    return start_of_month, end_of_month

async def get_all_users_data() -> List[Tuple[int, str, int, datetime]]:
    try:
        response = supabase.table(TBL.USERS).select(
            'user_id, username, first_name, last_name, total_quizzes, last_interaction'
        ).gt('total_quizzes', 0).execute()
        
        if not response.data:
            return []
        
        all_users = []
        for user in response.data:
            user_id = user['user_id']
            
            if str(user_id) == "999932510":
                continue
            
            display_name = ""
            if user.get('first_name'):
                display_name = user['first_name']
                if user.get('last_name'):
                    display_name += f" {user['last_name']}"
            elif user.get('username'):
                display_name = f"@{user['username']}"
            else:
                display_name = f"User {user_id}"
            
            quiz_count = user.get('total_quizzes', 0)
            last_interaction_str = user.get('last_interaction')
            
            if last_interaction_str:
                last_interaction = datetime.fromisoformat(last_interaction_str.replace('Z', '+00:00')).astimezone(TASHKENT_TZ)
            else:
                last_interaction = datetime.now(timezone.utc)
            
            if quiz_count > 0:
                all_users.append((user_id, display_name, quiz_count, last_interaction))
        
        sorted_users = sorted(all_users, key=lambda x: (-x[2], -x[3].timestamp()))
        return sorted_users
    
    except Exception as e:
        logger.error(f"Error getting all users data: {e}")
        return []

async def get_monthly_active_users(start_date: datetime, end_date: datetime) -> List[Tuple[int, str, int, datetime]]:
    try:
        # Get all files created within the date range
        response = supabase.table(TBL.FILES).select(
            'user_id, created_at'
        ).gte('created_at', start_date.isoformat()).lt('created_at', end_date.isoformat()).execute()
        
        if not response.data:
            return []
        
        # Count quizzes per user for this period
        user_quiz_counts = {}
        user_last_interaction = {}
        
        for file in response.data:
            user_id = file['user_id']
            created_at = datetime.fromisoformat(file['created_at'].replace('Z', '+00:00')).astimezone(TASHKENT_TZ)
            
            if str(user_id) == "999932510":
                continue
            
            user_quiz_counts[user_id] = user_quiz_counts.get(user_id, 0) + 1
            
            if user_id not in user_last_interaction or created_at > user_last_interaction[user_id]:
                user_last_interaction[user_id] = created_at
        
        # Get ALL user details in ONE query instead of N queries
        user_ids = list(user_quiz_counts.keys())
        user_response = supabase.table(TBL.USERS).select(
            'user_id, username, first_name, last_name'
        ).in_('user_id', user_ids).execute()
        
        # Create a lookup dict for O(1) access
        user_details = {user['user_id']: user for user in user_response.data} if user_response.data else {}
        
        # Build the monthly_users list
        monthly_users = []
        for user_id, quiz_count in user_quiz_counts.items():
            user = user_details.get(user_id)
            if user:
                display_name = ""
                if user.get('first_name'):
                    display_name = user['first_name']
                    if user.get('last_name'):
                        display_name += f" {user['last_name']}"
                elif user.get('username'):
                    display_name = f"@{user['username']}"
                else:
                    display_name = f"User {user_id}"
                
                monthly_users.append((user_id, display_name, quiz_count, user_last_interaction[user_id]))
        
        # Sort by quiz count (desc) then by last interaction (desc)
        sorted_users = sorted(monthly_users, key=lambda x: (-x[2], -x[3].timestamp()))
        return sorted_users
    
    except Exception as e:
        logger.error(f"Error getting monthly active users: {e}")
        return []

async def get_leaderboard_data(force_refresh: bool = False) -> Tuple[List[Tuple[int, str, int, datetime]], List[Tuple[int, str, int, datetime]], datetime, datetime]:
    try:
        now = datetime.now(TASHKENT_TZ)
        start_date, end_date = get_current_month_range()
        
        if (not force_refresh and 
            _leaderboard_cache['data'] is not None and 
            _leaderboard_cache['timestamp'] is not None and
            _leaderboard_cache['month_start'] == start_date and
            (now - _leaderboard_cache['timestamp']).seconds < CACHE_DURATION):
            return _leaderboard_cache['data']
        
        all_users = await get_all_users_data()
        monthly_users = await get_monthly_active_users(start_date, end_date)  # Pass dates
        
        result = (all_users, monthly_users, start_date, end_date)
        _leaderboard_cache['data'] = result
        _leaderboard_cache['timestamp'] = now
        _leaderboard_cache['month_start'] = start_date
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting leaderboard data: {e}")
        start_date, end_date = get_current_month_range()
        return ([], [], start_date, end_date)

async def send_final_leaderboard_to_admin(context: ContextTypes.DEFAULT_TYPE):
    try:
        # Get leaderboard data for the just-ended period
        all_users, monthly_users, start_date, end_date = await get_leaderboard_data(force_refresh=True)
        # Use English for admin, or set your preferred language
        language = "en"
        message = format_leaderboard_message(
            monthly_users, language, start_date, end_date
        )
        admin_id = int(os.environ.get("ADMIN_ID", "999932510"))
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"🏁 *Final Leaderboard for the Month*\n\n{message}",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"Final leaderboard sent to admin {admin_id}")
    except Exception as e:
        logger.error(f"Error sending final leaderboard to admin: {e}")


def get_user_position_in_ranking(user_id: int, monthly_users: List[Tuple[int, str, int, datetime]], start_date: datetime, end_date: datetime) -> Tuple[int, int, datetime]:
    for rank, (uid, _, quiz_count, last_interaction) in enumerate(monthly_users, 1):
        if uid == user_id:
            return rank, quiz_count, last_interaction
    
    try:
        response = supabase.table(TBL.FILES).select(
            'created_at'
        ).eq('user_id', user_id).gte('created_at', start_date.isoformat()).lt('created_at', end_date.isoformat()).execute()
        
        quiz_count = len(response.data) if response.data else 0
        
        if quiz_count > 0 and response.data:
            last_created = max(datetime.fromisoformat(f['created_at'].replace('Z', '+00:00')).astimezone(TASHKENT_TZ) 
                             for f in response.data)
            rank = len([u for u in monthly_users if u[2] > quiz_count]) + 1
            return rank, quiz_count, last_created
        
        return 0, 0, datetime.now(TASHKENT_TZ)
    except Exception as e:
        logger.error(f"Error getting user data for ranking: {e}")
        return 0, 0, datetime.now(TASHKENT_TZ)

def format_date_for_display(date: datetime, language: str = 'en') -> str:
    if language == 'ru':
        months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн',
                 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
        return f"{date.day} {months[date.month-1]}"
    elif language == 'uz':
        months = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
                 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr']
        return f"{date.day} {months[date.month-1]}"
    else:
        return date.strftime("%b %d")

def format_time_for_display(dt: datetime, language: str = 'en') -> str:
    if language == 'uz':
        return dt.strftime("%d.%m %H:%M")
    elif language == 'ru':
        return dt.strftime("%d.%m %H:%M")
    else:
        return dt.strftime("%m/%d %H:%M")

def format_leaderboard_message(monthly_users: List[Tuple[int, str, int, datetime]], language: str, 
                              start_date: datetime, end_date: datetime, user_rank: int = 0, 
                              user_quiz_count: int = 0, user_last_interaction: datetime = None,
                              is_refresh: bool = False) -> str:
    messages = LEADERBOARD_MESSAGES[language]
    
    start_str = format_date_for_display(start_date, language)
    end_str = format_date_for_display(end_date, language)
    
    title = messages['period_month'].format(start_str, end_str)
    
    if not monthly_users:
        message = f"{title}\n\n{messages['no_data']}"
    else:
        message = f"{title}\n\n"
        
        for rank, (user_id, display_name, quiz_count, last_interaction) in enumerate(monthly_users[:15], 1):
            time_str = format_time_for_display(last_interaction, language)
            message += f"{rank}. *{display_name}* - {quiz_count} quizzes ({time_str})\n"
    
    if user_last_interaction:
        time_str = format_time_for_display(user_last_interaction, language)
        if user_rank > 0:
            message += messages['your_rank'].format(user_rank, user_quiz_count, time_str)
        else:
            if language == 'en':
                message += f"\n🎯 *Your Position:* Unranked - {user_quiz_count} quizzes ({time_str})"
            elif language == 'ru':
                message += f"\n🎯 *Ваша позиция:* Не в рейтинге - {user_quiz_count} викторин ({time_str})"
            elif language == 'uz':
                message += f"\n🎯 *Sizning pozitsiyangiz:* Reytingda emas - {user_quiz_count} viktorina ({time_str})"
    
    if is_refresh:
        refresh_time = datetime.now().strftime("%H:%M:%S")
        if language == 'uz':
            message += f"\n\n🔄 Yangilandi: {refresh_time}"
        elif language == 'ru':
            message += f"\n\n🔄 Обновлено: {refresh_time}"
        else:
            message += f"\n\n🔄 Refreshed: {refresh_time}"
    
    return message

def get_leaderboard_keyboard(language: str) -> InlineKeyboardMarkup:
    messages = LEADERBOARD_MESSAGES[language]['buttons']
    
    create_presentation_text = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("create_quiz", "🎯 Create Quiz")
    balance_text = TRANSLATIONS.get(language, TRANSLATIONS["en"]).get("balance", "💰 Balance")

    keyboard = [
        [
            InlineKeyboardButton(messages['refresh'], callback_data='leaderboard_refresh')
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)

async def preload_leaderboard_data():
    try:
        await get_leaderboard_data()
    except Exception as e:
        logger.error(f"Error preloading leaderboard data: {e}")

# async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     context.user_data['busy'] = False
#     try:
#         await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        
#         user_id = update.effective_user.id
#         language = await get_user_language(user_id)
        
#         all_users, monthly_users, start_date, end_date = await get_leaderboard_data()
#         user_rank, user_quiz_count, user_last_interaction = get_user_position_in_ranking(user_id, monthly_users, start_date, end_date)
        
#         message = format_leaderboard_message(monthly_users, language, start_date, end_date, 
#                                            user_rank, user_quiz_count, user_last_interaction)
#         keyboard = get_leaderboard_keyboard(language)
        
#         await update.message.reply_text(
#             message,
#             parse_mode=ParseMode.MARKDOWN
#         )
        
#     except Exception as e:
#         logger.error(f"Error in leaderboard command: {e}")
#         await update.message.reply_text("An error occurred while fetching the leaderboard.")



async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redirect users to the activity bot for leaderboard."""
    user_id = update.effective_user.id
    language = await get_user_language(user_id) or 'en'
    
    leaderboard_messages = {
        'uz': "🏆 Konkurs boshqa botimizda davom etmoqda!\n\n"
              "📊 O'z reytingingizni tekshiring: @uzbek_activity_bot da /leaderboard deb yozing\n\n"
              "Sizda 400 000 so'm yutib olish imkoni mavjud!",
        'ru': "🏆 Конкурс проводится в другом боте!\n\n"
              "📊 Проверьте свой рейтинг: напишите /leaderboard в @uzbek_activity_bot\n\n"
              "У вас есть шанс выиграть 400 000 сум!",
        'en': "🏆 Contest is held in the different bot!\n\n"
              "📊 Check your ranking: type /leaderboard in @uzbek_activity_bot\n\n"
              "You have a chance to win 400,000 UZS!"
    }
    
    text = leaderboard_messages.get(language, leaderboard_messages['en'])
    await update.message.reply_text(text)


async def leaderboard_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data != 'leaderboard_refresh':
            return
        
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
        
        user_id = update.effective_user.id
        language = await get_user_language(user_id)
        
        all_users, monthly_users, start_date, end_date = await get_leaderboard_data(force_refresh=True)
        user_rank, user_quiz_count, user_last_interaction = get_user_position_in_ranking(user_id, monthly_users, start_date, end_date)

        
        message = format_leaderboard_message(monthly_users, language, start_date, end_date, 
                                           user_rank, user_quiz_count, user_last_interaction, 
                                           is_refresh=True)
        
        keyboard = get_leaderboard_keyboard(language)
        
        await query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
                
    except Exception as e:
        logger.error(f"Error in leaderboard callback handler: {e}")
        try:
            await query.edit_message_text("An error occurred while fetching the leaderboard.")
        except:
            pass

__all__ = ['leaderboard_command', 'leaderboard_callback_handler', 'preload_leaderboard_data']