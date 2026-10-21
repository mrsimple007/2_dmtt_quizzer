from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.quiz_results import get_quiz_leaderboard, get_quiz_stats
from src.user_management import get_user_language
import logging

logger = logging.getLogger(__name__)

async def handle_view_quiz_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display quiz results/leaderboard."""
    query = update.callback_query
    await query.answer()
    
    quiz_id = query.data.replace('view_quiz_results_', '')
    user_id = query.from_user.id
    language = await get_user_language(user_id)
    
    # Get leaderboard and stats
    leaderboard = await get_quiz_leaderboard(quiz_id, limit=20)
    stats = await get_quiz_stats(quiz_id)
    
    if not leaderboard:
        no_results = {
            'en': "📊 <b>No Results Yet</b>\n\nNo one has completed this quiz yet.",
            'uz': "📊 <b>Hali natijalar yo'q</b>\n\nBu quizni hali hech kim yechmagan.",
            'ru': "📊 <b>Результатов пока нет</b>\n\nЭту викторину пока никто не решил."
        }
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back", callback_data=f"view_my_quiz_{quiz_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            no_results.get(language, no_results['en']),
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        return
    
    # Build leaderboard message
    headers = {
        'en': "📊 <b>Quiz Results Leaderboard</b>\n\n",
        'uz': "📊 <b>Quiz Natijalari</b>\n\n",
        'ru': "📊 <b>Таблица Результатов</b>\n\n"
    }
    
    message = headers.get(language, headers['en'])
    
    # Add stats if available
    if stats:
        stat_texts = {
            'en': (
                f"👥 <b>Total Participants:</b> {stats['unique_users']}\n"
                f"📝 <b>Total Attempts:</b> {stats['total_attempts']}\n"
                f"📊 <b>Avg Accuracy:</b> {stats['avg_accuracy']:.1f}%\n"
                f"⏱️ <b>Avg Time:</b> {int(stats['avg_time'])}s\n\n"
                f"<b>Top 20:</b>\n"
            ),
            'uz': (
                f"👥 <b>Jami ishtirokchilar:</b> {stats['unique_users']}\n"
                f"📝 <b>Jami urinishlar:</b> {stats['total_attempts']}\n"
                f"📊 <b>O'rtacha aniqlik:</b> {stats['avg_accuracy']:.1f}%\n"
                f"⏱️ <b>O'rtacha vaqt:</b> {int(stats['avg_time'])}s\n\n"
                f"<b>Top 20:</b>\n"
            ),
            'ru': (
                f"👥 <b>Всего участников:</b> {stats['unique_users']}\n"
                f"📝 <b>Всего попыток:</b> {stats['total_attempts']}\n"
                f"📊 <b>Средняя точность:</b> {stats['avg_accuracy']:.1f}%\n"
                f"⏱️ <b>Среднее время:</b> {int(stats['avg_time'])}s\n\n"
                f"<b>Топ 20:</b>\n"
            )
        }
        message += stat_texts.get(language, stat_texts['en'])
    
    # Add leaderboard entries
    for entry in leaderboard[:20]:
        rank = entry['rank']
        name = entry.get('first_name') or entry.get('username') or 'Anonymous'
        score = entry['score']
        total = entry['total_questions']
        time_spent = int(entry['time_spent'])
        accuracy = (score / total * 100) if total > 0 else 0
        
        # Medal emojis for top 3
        medal = ""
        if rank == 1:
            medal = "🥇 "
        elif rank == 2:
            medal = "🥈 "
        elif rank == 3:
            medal = "🥉 "
        
        message += f"{medal}<b>{rank}.</b> {name} - {score}/{total} ({accuracy:.0f}%) - {time_spent}s\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Back", callback_data=f"view_my_quiz_{quiz_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        message,
        parse_mode="HTML",
        reply_markup=reply_markup
    )