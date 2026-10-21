from src.tables import TBL
from src.imports import *
from src.user_management import get_user_language, supabase
import logging

logger = logging.getLogger(__name__)

async def save_quiz_attempt(
    quiz_id: str,
    user_id: int,
    username: str,
    first_name: str,
    score: int,
    total_questions: int,
    time_spent: float
) -> bool:
    """Save a quiz attempt to the database."""
    try:
        supabase.table(TBL.QUIZ_ATTEMPTS).insert({
            'quiz_id': quiz_id,
            'user_id': user_id,
            'username': username or '',
            'first_name': first_name or 'Anonymous',
            'score': score,
            'total_questions': total_questions,
            'time_spent': time_spent
        }).execute()
        
        logger.info(f"Saved quiz attempt: quiz_id={quiz_id}, user={user_id}, score={score}/{total_questions}")
        return True
    except Exception as e:
        logger.error(f"Error saving quiz attempt: {e}")
        return False


async def get_quiz_leaderboard(quiz_id: str, limit: int = 50):
    """Get leaderboard for a specific quiz."""
    try:
        # Get all attempts for this quiz
        response = supabase.table(TBL.QUIZ_ATTEMPTS) \
            .select('*') \
            .eq('quiz_id', quiz_id) \
            .order('score', desc=True) \
            .order('time_spent', desc=False) \
            .limit(limit) \
            .execute()
        
        if not response.data:
            return []
        
        # Add rank manually since Supabase doesn't support window functions directly
        leaderboard = []
        for idx, row in enumerate(response.data, start=1):
            row['rank'] = idx
            leaderboard.append(row)
        
        return leaderboard
    except Exception as e:
        logger.error(f"Error fetching quiz leaderboard: {e}")
        return []


async def get_quiz_owner(quiz_id: str) -> int:
    """Get the user_id of who created this quiz."""
    try:
        response = supabase.table(TBL.QUIZZES) \
            .select('user_id') \
            .eq('id', quiz_id) \
            .execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]['user_id']
        return None
    except Exception as e:
        logger.error(f"Error fetching quiz owner: {e}")
        return None


async def get_quiz_stats(quiz_id: str):
    """Get statistics for a quiz."""
    try:
        response = supabase.table(TBL.QUIZ_ATTEMPTS) \
            .select('*') \
            .eq('quiz_id', quiz_id) \
            .execute()
        
        if not response.data:
            return None
        
        attempts = response.data
        total_attempts = len(attempts)
        unique_users = len(set(a['user_id'] for a in attempts))
        
        # Calculate averages
        total_accuracy = 0
        total_time = 0
        
        for attempt in attempts:
            accuracy = (attempt['score'] / attempt['total_questions'] * 100) if attempt['total_questions'] > 0 else 0
            total_accuracy += accuracy
            total_time += attempt['time_spent']
        
        avg_accuracy = total_accuracy / total_attempts if total_attempts > 0 else 0
        avg_time = total_time / total_attempts if total_attempts > 0 else 0
        
        return {
            'total_attempts': total_attempts,
            'unique_users': unique_users,
            'avg_accuracy': avg_accuracy,
            'avg_time': avg_time
        }
    except Exception as e:
        logger.error(f"Error fetching quiz stats: {e}")
        return None


async def notify_quiz_owner(
    context,
    quiz_id: str,
    participant_id: int,
    participant_name: str,
    score: int,
    total_questions: int,
    time_spent: float
):
    """Notify quiz owner when someone completes their quiz."""
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        owner_id = await get_quiz_owner(quiz_id)
        
        # Don't notify if owner solved their own quiz
        if not owner_id or owner_id == participant_id:
            return
        # FIXED: Get complete participant info
        try:
            participant_info = await context.bot.get_chat(participant_id)
            first_name = participant_info.first_name or ""
            last_name = participant_info.last_name or ""
            username = participant_info.username
            
            # Format: "First Last (username)" or "First Last" or "First (username)"
            if username:
                participant_display = f"{first_name} {last_name} (@{username})".strip()
            else:
                participant_display = f"{first_name} {last_name}".strip()
            
            # Fallback if empty
            if not participant_display:
                participant_display = f"User {participant_id}"
        except Exception as e:
            logger.error(f"Error fetching participant info: {e}")
            participant_display = participant_name or f"User {participant_id}"
        
        # Get quiz title
        response = supabase.table(TBL.QUIZZES) \
            .select('title') \
            .eq('id', quiz_id) \
            .execute()
        
        quiz_title = response.data[0]['title'] if response.data else 'Quiz'


        # Get quiz title
        response = supabase.table(TBL.QUIZZES) \
            .select('title') \
            .eq('id', quiz_id) \
            .execute()
        
        quiz_title = response.data[0]['title'] if response.data else 'Quiz'
        
        # Get owner language
        owner_language = await get_user_language(owner_id)
        
        accuracy = (score / total_questions * 100) if total_questions > 0 else 0
        
        # Format time nicely
        minutes = int(time_spent // 60)
        seconds = int(time_spent % 60)
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        
        notifications = {
            'en': (
                f"🎯 <b>Your quiz is solved!</b>\n\n"
                f"<b>Quiz:</b> {quiz_title}\n"
                f"<b>Solver:</b> {participant_display}\n"
                f"<b>Score:</b> {score}/{total_questions} ({accuracy:.1f}%)\n"
                f"<b>Time:</b> {time_str}\n\n"
                f"View full results in My Quizzes → Results"
            ),
            'uz': (
                f"🎯 <b>Sizning quizingiz yechildi!</b>\n\n"
                f"<b>Quiz:</b> {quiz_title}\n"
                f"<b>Yechuvchi:</b> {participant_display}\n"
                f"<b>Ball:</b> {score}/{total_questions} ({accuracy:.1f}%)\n"
                f"<b>Vaqt:</b> {time_str}\n\n"
                f"To'liq natijalarni ko'rish: Mening Quizlarim → Natijalar"
            ),
            'ru': (
                f"🎯 <b>Кто-то решил вашу викторину!</b>\n\n"
                f"<b>Викторина:</b> {quiz_title}\n"
                f"<b>Решил:</b> {participant_display}\n"
                f"<b>Счет:</b> {score}/{total_questions} ({accuracy:.1f}%)\n"
                f"<b>Время:</b> {time_str}\n\n"
                f"Полные результаты: Мои Викторины → Результаты"
            )
        }
        
        message = notifications.get(owner_language, notifications['en'])
        
        # Add button to view results
        keyboard = [
            [InlineKeyboardButton("📊 View Results", callback_data=f"view_quiz_results_{quiz_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=owner_id,
            text=message,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        
        logger.info(f"Sent notification to quiz owner {owner_id} about participant {participant_id}")
        
    except Exception as e:
        logger.error(f"Error notifying quiz owner: {e}")