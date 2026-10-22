from src.tables import TBL
from telegram import Update, Poll, Bot
from telegram.ext import ContextTypes
from datetime import datetime, timezone
import asyncio
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import ContextTypes, CommandHandler, PollAnswerHandler
from src.imports import *
from handlers.sharing_quiz import *
from src.user_management import *
from src.perf_timing import track_handler
from src.user_management import run_supabase, touch_user_activity

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global state for group quizzes
GROUP_QUIZ_STATE: Dict[int, Dict] = {}

ANTI_CHEAT_GROUP_IDS = {
    -1002824929840,
    -1001423407195,
    -5100337075,
    -5201011874
    # -5289906936
}


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.my_chat_member.chat
    new_status = update.my_chat_member.new_chat_member.status

    # Only save if bot was added (not removed)
    if chat.type in ["group", "supergroup"] and new_status in ["member", "administrator"]:
        try:
            await save_group_info(
                group_id=chat.id,
                title=chat.title,
                username=getattr(chat, "username", None),
                group_type=chat.type
            )
            logger.info(f"[GROUP INFO] Saved group info for chat {chat.id} ({chat.title})")
        except Exception as e:
            logger.error(f"[GROUP INFO] Failed to save group info: {e}")


async def _member_info(context, chat_id, user_ids, concurrency=8):
    """{user_id: (display_name, telegram_user_or_None)} fetched in parallel."""
    sem = asyncio.Semaphore(concurrency)

    async def one(uid):
        async with sem:
            try:
                m = await context.bot.get_chat_member(chat_id, uid)
                name = m.user.first_name or "Unknown"
                if m.user.username:
                    name += f" (@{m.user.username})"
                return uid, (name, m.user)
            except Exception:
                return uid, (f"User {uid}", None)

    return dict(await asyncio.gather(*(one(u) for u in user_ids)))


async def send_group_quiz_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    state = GROUP_QUIZ_STATE.get(chat_id)
    if not state or not state["active"]:
        logger.warning(f"[GROUP QUIZ] Cannot send question - no active state for chat {chat_id}")
        return

    quiz_data = state["quiz_data"]
    
    quiz_time = state.get("quiz_time")
    if quiz_time is None:
        quiz_time = quiz_data.get("quiz_time")
    if quiz_time is None:
        quiz_time = 30
    else:
        quiz_time = int(quiz_time)
    
    quiz_time = max(5, min(quiz_time, 600))
    
    idx = state["current_question"]
    if idx >= len(quiz_data["questions"]):
        logger.info(f"[GROUP QUIZ] All questions completed for chat {chat_id}, finishing quiz")
        await finish_group_quiz(context, chat_id)
        return

    q = quiz_data["questions"][idx]
    
    def truncate_option(text, max_length=100):
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    truncated_options = [truncate_option(opt) for opt in q["options"]]
    allows_multiple = bool(q.get("allows_multiple_answers", False))

    # Resolve correct option indices
    if allows_multiple:
        correct_answers = q.get("correct_answers", [])
        if not correct_answers:
            logger.error(f"[GROUP QUIZ] No correct answers for multi-answer question {idx + 1}")
            return

        correct_option_ids = []
        for ans in correct_answers:
            if isinstance(ans, int):
                correct_option_ids.append(ans)
            else:
                try:
                    correct_option_ids.append(q["options"].index(ans))
                except ValueError:
                    logger.error(f"[GROUP QUIZ] correct answer '{ans}' not found in options: {q['options']}")
                    return
        
        for opt_id in correct_option_ids:
            if opt_id >= len(truncated_options) or opt_id < 0:
                logger.error(f"[GROUP QUIZ] Invalid correct_option_id: {opt_id}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="❌ Error: Invalid question data. Skipping to next question."
                )
                state["current_question"] += 1
                await send_group_quiz_question(context, chat_id)
                return
    else:
        correct_answer = q.get("correct_answer")
        if isinstance(correct_answer, int):
            correct_option_id = correct_answer
        else:
            try:
                correct_option_id = q["options"].index(correct_answer)
            except ValueError:
                logger.error(f"[GROUP QUIZ] correct answer '{correct_answer}' not found in options: {q['options']}")
                return
        
        if correct_option_id >= len(truncated_options) or correct_option_id < 0:
            logger.error(f"[GROUP QUIZ] Invalid correct_option_id: {correct_option_id}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Error: Invalid question data. Skipping to next question."
            )
            state["current_question"] += 1
            await send_group_quiz_question(context, chat_id)
            return

    try:
        total_questions = len(quiz_data["questions"])
        question_number = idx + 1
        question_base = q['question']

        adjusted_quiz_time = quiz_time + 3

        await context.bot.send_message(
            chat_id=chat_id,
            text=format_question_message(question_number, total_questions, question_base, q["options"]),
            parse_mode="HTML",
        )
        question_text = f"{question_number}/{total_questions}"
        # Final safety check
        if len(question_text) > 300:
            question_text = question_text[:297] + "..."
            logger.warning(f"[SEND QUESTION] Final truncation applied to question_text")


        # ✅ CHECK IF THIS CHAT NEEDS ANTI-CHEAT MODE
        use_anti_cheat = chat_id in ANTI_CHEAT_GROUP_IDS

        if use_anti_cheat:
            # Anti-cheat mode: Use REGULAR poll (no instant answer reveal)
            logger.info(f"[ANTI-CHEAT] Using anti-cheat mode for chat {chat_id}")
            
            if allows_multiple:
                poll_message = await context.bot.send_poll(
                    chat_id=chat_id,
                    question=question_text,
                    options=truncated_options,
                    type=Poll.REGULAR,  # ✅ REGULAR poll - no instant reveal
                    allows_multiple_answers=True,
                    is_anonymous=False,
                    open_period=adjusted_quiz_time,
                )
            else:
                poll_message = await context.bot.send_poll(
                    chat_id=chat_id,
                    question=question_text,
                    options=truncated_options,
                    type=Poll.REGULAR,  # ✅ REGULAR poll - no instant reveal
                    allows_multiple_answers=False,
                    is_anonymous=False,
                    open_period=adjusted_quiz_time,
                )
        else:
            # Normal mode: Use QUIZ poll (instant answer reveal)
            logger.info(f"[NORMAL MODE] Using standard quiz mode for chat {chat_id}")
            if allows_multiple:
                poll_message = await context.bot.send_poll(
                    chat_id=chat_id,
                    question=question_text,
                    options=truncated_options,
                    type=Poll.QUIZ,
                    allows_multiple_answers=True,
                    correct_option_id=correct_option_ids,
                    is_anonymous=False,
                    open_period=adjusted_quiz_time,
                )
            else:
                poll_message = await context.bot.send_poll(
                    chat_id=chat_id,
                    question=question_text,
                    options=truncated_options,
                    type=Poll.QUIZ,
                    allows_multiple_answers=False,
                    correct_option_id=correct_option_id,
                    is_anonymous=False,
                    open_period=adjusted_quiz_time,
                )

        # Initialize state structures
        if "poll_ids" not in state:
            state["poll_ids"] = []
        if "poll_to_question" not in state:
            state["poll_to_question"] = {}
        if "answers" not in state:
            state["answers"] = {}
            
        poll_id = poll_message.poll.id
        state["poll_ids"].append(poll_id)
        
        question_start_time = datetime.now(timezone.utc)
        state["poll_to_question"][poll_id] = {
            "question_idx": idx,
            "correct_option_id": correct_option_ids if allows_multiple else correct_option_id,
            "start_time": question_start_time,
            "question_text": q['question'],
            "options": q["options"],
            "allows_multiple": allows_multiple,
            "use_anti_cheat": use_anti_cheat  
        }
        
        state["last_poll_message_id"] = poll_message.message_id
        state["last_poll_id"] = poll_id        
        
        asyncio.create_task(wait_and_proceed_to_next_question(context, chat_id, poll_id, quiz_time))
        
    except Exception as e:
        logger.error(f"[GROUP QUIZ] Error sending poll: {str(e)}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Error sending quiz question. Please try again."
        )
        return


async def wait_and_proceed_to_next_question(
    context: ContextTypes.DEFAULT_TYPE, 
    chat_id: int, 
    poll_id: str,
    quiz_time: int
) -> None:
    """Wait for the quiz time to expire and proceed to next question."""
    try:
        state = GROUP_QUIZ_STATE.get(chat_id)
        if not state or not state["active"]:
            return
        
        # ✅ WAIT FOR THE FULL QUIZ TIME
        await asyncio.sleep(quiz_time)
        
        state = GROUP_QUIZ_STATE.get(chat_id)
        if not state or not state["active"]:
            return

        poll_answered = False
        
        try:
            # ✅ STEP 1: Stop the poll first
            stopped_poll = await context.bot.stop_poll(
                chat_id=chat_id,
                message_id=state["last_poll_message_id"]
            )
            
            # ✅ STEP 2: Check if anyone voted (before calculating scores)
            for option in stopped_poll.options:
                if option.voter_count > 0:
                    poll_answered = True
                    break
            
            # ✅ STEP 3: Calculate scores (this also checks voter_ids)
            score_calculated = await calculate_scores(stopped_poll, state, context)
            poll_answered = poll_answered or score_calculated
            
            # ✅ STEP 4: Only reveal answer if anti-cheat mode AND poll was answered
            question_data = state.get("poll_to_question", {}).get(poll_id)
            if question_data and question_data.get("use_anti_cheat", False):
                await reveal_correct_answer(context, chat_id, poll_id, state)
                        
        except Exception as stop_error:
            if "Poll has already been closed" in str(stop_error):
                logger.info(f"[GROUP QUIZ] Poll {poll_id} was already closed naturally")
            else:
                logger.error(f"[GROUP QUIZ] Error stopping poll: {str(stop_error)}")
        
        # ✅ STEP 5: Track unanswered questions
        if not poll_answered:
            state["unanswered_count"] = state.get("unanswered_count", 0) + 1
            logger.info(f"[GROUP QUIZ] No one answered question {state['current_question'] + 1}. Unanswered count: {state['unanswered_count']}")
        else:
            state["unanswered_count"] = 0
            logger.info(f"[GROUP QUIZ] Question {state['current_question'] + 1} was answered. Reset unanswered count.")
        
        # ✅ STEP 6: Check pause condition
        if state.get("unanswered_count", 0) >= 2 and not state.get("paused", False):
            state["paused"] = True
            state["active"] = False
            
            logger.info(f"[GROUP QUIZ] Pausing quiz due to {state['unanswered_count']} unanswered questions")
            
            language = state.get("language", "en")
            texts = {
                'en': {
                    'paused': '⏸️ <b>Quiz Paused</b>\n\nNo one has answered the last 2 questions.\n\nDo you want to continue or stop the quiz?',
                    'continue': '▶️ Continue',
                    'stop': '🛑 Stop Quiz'
                },
                'uz': {
                    'paused': '⏸️ <b>Quiz to\'xtatildi</b>\n\nOxirgi 2 ta savolga hech kim javob bermadi.\n\nDavom ettirishni yoki to\'xtatishni xohlaysizmi?',
                    'continue': '▶️ Davom etish',
                    'stop': '🛑 To\'xtatish'
                },
                'ru': {
                    'paused': '⏸️ <b>Квиз приостановлена</b>\n\nНикто не ответил на последние 2 вопроса.\n\nПродолжить или остановить викторину?',
                    'continue': '▶️ Продолжить',
                    'stop': '🛑 Остановить'
                }
            }
            
            lang_texts = texts.get(language, texts['en'])
            
            keyboard = [
                [
                    InlineKeyboardButton(lang_texts['continue'], callback_data=f"continue_quiz_{chat_id}"),
                    InlineKeyboardButton(lang_texts['stop'], callback_data=f"stop_quiz_{chat_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=chat_id,
                text=lang_texts['paused'],
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            return
        
        # ✅ STEP 7: Proceed to next question
        state["current_question"] += 1
        
        if state["current_question"] < len(state["quiz_data"]["questions"]):
            await send_group_quiz_question(context, chat_id)
        else:
            await finish_group_quiz(context, chat_id)
            
    except Exception as e:
        logger.error(f"[GROUP QUIZ] Error in wait_and_proceed: {str(e)}")

async def reveal_correct_answer(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    poll_id: str,
    state: Dict
) -> None:
    """
    ✅ ANTI-CHEAT FEATURE: Reveal correct answer AFTER poll closes
    This prevents users from seeing answers before time expires
    """
    try:
        question_data = state.get("poll_to_question", {}).get(poll_id)
        if not question_data:
            logger.warning(f"[REVEAL] No question data for poll {poll_id}")
            return

        correct_option_id = question_data["correct_option_id"]
        question_idx = question_data["question_idx"]
        options = question_data.get("options", [])
        allows_multiple = question_data.get("allows_multiple", False)

        language = state.get("language", "en")
        
        reveal_texts = {
            'en': {
                'correct': '✅ <b>Correct Answer:</b>',
                'correct_multiple': '✅ <b>Correct Answers:</b>',
            },
            'uz': {
                'correct': '✅ <b>To\'g\'ri javob:</b>',
                'correct_multiple': '✅ <b>To\'g\'ri javoblar:</b>',
            },
            'ru': {
                'correct': '✅ <b>Правильный ответ:</b>',
                'correct_multiple': '✅ <b>Правильные ответы:</b>',
            }
        }
        
        lang_texts = reveal_texts.get(language, reveal_texts['en'])

        if allows_multiple:
            correct_answers_text = "\n".join([f"• {options[idx]}" for idx in correct_option_id])
            message = f"{lang_texts['correct_multiple']}\n{correct_answers_text}"
        else:
            message = f"{lang_texts['correct']}\n• {options[correct_option_id]}"

        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="HTML"
        )
        
        logger.info(f"[REVEAL] Revealed correct answer for question {question_idx + 1} in chat {chat_id}")
        
    except Exception as e:
        logger.error(f"[REVEAL] Error revealing answer: {str(e)}")



async def start_group_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id: int, quiz_id: str) -> None:
    """Initialize and start a new group quiz with a countdown using existing quiz from database."""
    try:
        # Check if there's already an active quiz in this group
        if chat_id in GROUP_QUIZ_STATE and GROUP_QUIZ_STATE[chat_id].get("active", False):
            logger.warning(f"[GROUP QUIZ] Quiz already active in chat {chat_id}, ignoring duplicate start request")
            return

        logger.info(f"[GROUP QUIZ] Starting quiz {quiz_id} in chat {chat_id}")

        # Validate that quiz_id is a valid UUID
        import uuid
        if isinstance(quiz_id, dict):
            logger.error(f"[GROUP QUIZ] Invalid quiz_id type: {type(quiz_id)}. Expected string.")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Invalid quiz ID. Please check the quiz link and try again."
            )
            return

        try:
            quiz_id = str(uuid.UUID(quiz_id))
        except ValueError:
            logger.error(f"[GROUP QUIZ] Invalid quiz_id: {quiz_id}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Invalid quiz ID. Please check the quiz link and try again."
            )
            return

        # Get the quiz data from database using the provided quiz_id
        quiz_row = await run_supabase(
            lambda: supabase.table(TBL.QUIZZES).select("*").eq("id", quiz_id).execute())
        if not quiz_row.data or len(quiz_row.data) == 0:
            logger.error(f"[GROUP QUIZ] Quiz {quiz_id} not found in database")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Quiz not found. Please check the quiz ID and try again."
            )
            return

        quiz_record = quiz_row.data[0]
        if not isinstance(quiz_record.get("quiz_data"), dict):
            logger.error(f"[GROUP QUIZ] Invalid quiz_data format: {quiz_record.get('quiz_data')}")
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Quiz data is corrupted. Please try another quiz."
            )
            return

        quiz_data = quiz_record["quiz_data"]

        quiz_time = quiz_data.get("quiz_time")
        
        if quiz_time is None:
            quiz_time = quiz_record.get("quiz_time")
            
        if quiz_time is None:
            creator_user_id = quiz_record.get("user_id") or quiz_record.get("creator_user_id")
            if creator_user_id:
                quiz_time = await get_user_quiz_time(creator_user_id)
            
        if quiz_time is None:
            quiz_time = 30
        else:
            quiz_time = int(quiz_time)

        logger.info(f"[GROUP QUIZ] Using quiz_time: {quiz_time} seconds for quiz {quiz_id}")

        # Initialize quiz state
        GROUP_QUIZ_STATE[chat_id] = {
            "active": True,
            "quiz_data": quiz_data,
            "current_question": 0,
            "scores": {},
            "start_time": datetime.now(timezone.utc),
            "poll_ids": [],
            "poll_to_question": {},
            "answers": {},
            "language": quiz_record.get("language", "en"),
            "num_questions": quiz_record.get("num_questions", len(quiz_data.get("questions", []))),
            "quiz_time": quiz_time,
            "starting": True,
            "unanswered_count": 0,
            "paused": False
        }
        
        # ✅ FIXED: Run countdown in background without blocking
        asyncio.create_task(
            _send_countdown_and_start_group_quiz(context, chat_id)
        )

    except Exception as e:
        logger.error(f"[GROUP QUIZ] Error starting quiz: {str(e)}")
        if chat_id in GROUP_QUIZ_STATE:
            del GROUP_QUIZ_STATE[chat_id]
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Error starting the quiz. Please try again."
        )


async def _send_countdown_and_start_group_quiz(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int
) -> None:
    """Send countdown in background without blocking other groups."""
    try:
        state = GROUP_QUIZ_STATE.get(chat_id)
        if not state:
            logger.error(f"[GROUP QUIZ] No state found for countdown in chat {chat_id}")
            return
        
        # Send countdown
        status_message = await context.bot.send_message(
            chat_id=chat_id,
            text="3️⃣ <b>Are you ready?</b>",
            parse_mode="HTML"
        )
        await asyncio.sleep(1)
        
        await status_message.edit_text("2️⃣ <b>Get set...</b>", parse_mode="HTML")
        await asyncio.sleep(1)
        
        await status_message.edit_text("1️⃣ <b>Go!</b>", parse_mode="HTML")
        await asyncio.sleep(1)
        
        try:
            await status_message.delete()
        except Exception as e:
            logger.error(f"Error deleting countdown message: {e}")

        # Remove the starting flag and send first question
        if chat_id in GROUP_QUIZ_STATE:
            GROUP_QUIZ_STATE[chat_id]["starting"] = False
            await send_group_quiz_question(context, chat_id)
            
    except Exception as e:
        logger.error(f"[GROUP QUIZ] Error in countdown for chat {chat_id}: {e}")
        if chat_id in GROUP_QUIZ_STATE:
            del GROUP_QUIZ_STATE[chat_id]


async def finish_group_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    try:
        state = GROUP_QUIZ_STATE.get(chat_id)
        if not state:
            logger.error(f"[GROUP QUIZ] No state found for chat {chat_id} when finishing quiz")
            return
            
        state["active"] = False
            
        logger.info(f"[GROUP QUIZ] Final scores: {state['scores']}")
        
        # Calculate individual user answer times
        user_times = {}
        if "user_answers" in state:
            for user_id, answers in state["user_answers"].items():
                total_time = 0
                
                for answer in answers:
                    if "time_spent" in answer and isinstance(answer["time_spent"], (int, float)) and answer["time_spent"] > 0:
                        total_time += answer["time_spent"]
                    elif "answer_time" in answer and isinstance(answer["answer_time"], (int, float)) and answer["answer_time"] > 0:
                        total_time += answer["answer_time"]
                
                user_times[user_id] = total_time
        else:
            logger.warning("[GROUP QUIZ] No user_answers available, using fallback time calculation")
            for user_id in state.get("scores", {}):
                user_times[user_id] = 0
        
        # Sort scores by score first, then by time (faster is better)
        def sort_key(item):
            user_id, score = item
            time_spent = user_times.get(user_id, float('inf'))
            return (-score, time_spent) 
        
        sorted_scores = sorted(state["scores"].items(), key=sort_key)
        
        # ✅ NEW: Launch BOTH tasks in background WITHOUT waiting
        asyncio.create_task(
            _process_quiz_participants_background(
                context=context,
                chat_id=chat_id,
                sorted_scores=sorted_scores
            )
        )
        
        asyncio.create_task(
            _send_leaderboard_background(
                context=context,
                chat_id=chat_id,
                state=state,
                sorted_scores=sorted_scores,
                user_times=user_times
            )
        )
        
        # ✅ Clean up state immediately - don't wait for anything
        if chat_id in GROUP_QUIZ_STATE:
            del GROUP_QUIZ_STATE[chat_id]
            logger.info(f"[GROUP QUIZ] Cleaned up state for chat {chat_id}")
        
    except Exception as e:
        logger.error(f"[GROUP QUIZ] ❌ Error finishing quiz: {str(e)}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Error displaying quiz results."
            )
        except:
            pass

async def _send_leaderboard_background(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    state: Dict,
    sorted_scores: List[Tuple[int, int]],
    user_times: Dict[int, float]
) -> None:
    """Send leaderboard message in background without blocking."""
    try:
        logger.info(f"[LEADERBOARD] Starting background leaderboard for chat {chat_id}")
        
        total_questions = len(state.get("quiz_data", {}).get("questions", []))

        # Get language
        language = "en"
        if sorted_scores:
            try:
                first_user_id = sorted_scores[0][0]
                language = await get_user_language(first_user_id)
            except Exception as e:
                logger.warning(f"Could not get user language: {e}")
                language = "en"

        texts = LEADERBOARD_TEXTS.get(language, LEADERBOARD_TEXTS["en"])

        if not sorted_scores:
            leaderboard = texts["no_participants"]
        else:
            quiz_title = state.get("quiz_data", {}).get("title", "Quiz")
            formatted_title = f'"{quiz_title}"'
            leaderboard = (
                f"{texts['results'].format(quiz_title=formatted_title)}\n\n"
                f"{texts['total_questions'].format(total=total_questions)}\n"
                f"{texts['participants'].format(count=len(sorted_scores))}\n\n"
            )

            # ✅ Build leaderboard with async user fetching
            for i, (user_id, score) in enumerate(sorted_scores[:35], 1):
                try:
                    member = await context.bot.get_chat_member(chat_id, user_id)
                    display_name = member.user.first_name or "Unknown"
                    if member.user.username:
                        display_name += f" (@{member.user.username})"
                except Exception as e:
                    logger.warning(f"Could not get user info for {user_id}: {e}")
                    display_name = f"User {user_id}"

                display_name = display_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

                user_time = user_times.get(user_id, 0)
                minutes = int(user_time // 60)
                seconds = int(user_time % 60)

                if user_time > 0:
                    if minutes > 0:
                        time_str = f"{minutes} {texts.get('minutes', 'min')} {seconds} {texts.get('seconds', 'sec')}"
                    else:
                        time_str = f"{seconds} {texts.get('seconds', 'sec')}"
                else:
                    time_str = "N/A"
                leaderboard += f"{medal} {display_name}: {score}/{total_questions} ({time_str})\n"

            # Add congratulations for the winner
            if sorted_scores:
                first_user_id, _ = sorted_scores[0]
                try:
                    first_member = await context.bot.get_chat_member(chat_id, first_user_id)
                    winner_name = first_member.user.first_name or "Unknown"
                except Exception:
                    winner_name = "The winner"
                
                congrats_text = texts.get('congrats', '🎉 Congratulations {winner}!')
                if '{winner}' in congrats_text:
                    leaderboard += f"\n{congrats_text.format(winner=winner_name)}"
                else:
                    leaderboard += f"\n🎉 Congratulations {winner_name}!"

        # Get quiz_id and create share button
        quiz_id = state.get("quiz_data", {}).get("id")
        reply_markup = None
                
        if quiz_id:
            try:
                bot_username = (await context.bot.get_me()).username
                keyboard = [
                    [InlineKeyboardButton("📤 Share Quiz", switch_inline_query=f"quiz_{quiz_id}")],
                    [InlineKeyboardButton("👥 Share to Group", url=f"https://t.me/{bot_username}?startgroup=groupquiz_{quiz_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                                
            except Exception as e:
                logger.error(f"[LEADERBOARD] ❌ Error creating share button: {e}")
                reply_markup = None
        else:
            logger.warning(f"[LEADERBOARD] ⚠️ No quiz_id found in state for chat {chat_id}")

        # Send message
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=leaderboard,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            
            logger.info(f"[LEADERBOARD] ✅ Sent for chat {chat_id}")
                
        except Exception as e:
            logger.error(f"[LEADERBOARD] ❌ Error sending: {e}")
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=leaderboard,
                    parse_mode="HTML"
                )
            except Exception as fallback_error:
                logger.error(f"[LEADERBOARD] ❌ Fallback failed: {fallback_error}")
                
    except Exception as e:
        logger.error(f"[LEADERBOARD] ❌ Error in background: {str(e)}")


async def _process_quiz_participants_background(context, chat_id, sorted_scores) -> None:
    """Only refresh activity of users who already started the bot. Never create users from a group."""
    try:
        ids = [uid for uid, _ in sorted_scores]
        sem = asyncio.Semaphore(8)

        async def one(uid):
            async with sem:
                if await check_user_exists(uid):          # cached profile lookup
                    await touch_user_activity(uid)

        await asyncio.gather(*(one(u) for u in ids), return_exceptions=True)
    except Exception as e:
        logger.error(f"[BACKGROUND USERS] error: {e}")


async def _send_leaderboard(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    state: Dict,
    sorted_scores: List[Tuple[int, int]],
    user_times: Dict[int, float]
) -> None:
    """Send leaderboard message."""
    try:
        total_questions = len(state.get("quiz_data", {}).get("questions", []))

        # Get language for any user in the group (fallback to English)
        language = "en"
        if sorted_scores:
            try:
                first_user_id = sorted_scores[0][0]
                language = await get_user_language(first_user_id)
            except Exception as e:
                logger.warning(f"Could not get user language: {e}")
                language = "en"

        texts = LEADERBOARD_TEXTS.get(language, LEADERBOARD_TEXTS["en"])

        if not sorted_scores:
            leaderboard = texts["no_participants"]
            logger.warning("[GROUP QUIZ] No scores found - possible issues with poll anonymity or score calculation")
        else:
            quiz_title = state.get("quiz_data", {}).get("title", "Quiz")
            formatted_title = f'"{quiz_title}"'
            leaderboard = (
                f"{texts['results'].format(quiz_title=formatted_title)}\n\n"
                f"{texts['total_questions'].format(total=total_questions)}\n"
                f"{texts['participants'].format(count=len(sorted_scores))}\n\n"
            )

            top = sorted_scores[:35]
            info = await _member_info(context, chat_id, [u for u, _ in top])

            for i, (user_id, score) in enumerate(top, 1):
                display_name = info[user_id][0]
                display_name = display_name.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                user_time = user_times.get(user_id, 0)
                minutes, seconds = int(user_time // 60), int(user_time % 60)
                if user_time > 0:
                    time_str = (f"{minutes} {texts.get('minutes', 'min')} {seconds} {texts.get('seconds', 'sec')}"
                                if minutes > 0 else f"{seconds} {texts.get('seconds', 'sec')}")
                else:
                    time_str = "N/A"
                leaderboard += f"{medal} {display_name}: {score}/{total_questions} ({time_str})\n"

            winner_name = info[top[0][0]][0].split(" (@")[0]
            congrats_text = texts.get('congrats', '🎉 Congratulations {winner}!')
            leaderboard += "\n" + (congrats_text.format(winner=winner_name)
                                   if '{winner}' in congrats_text else f"🎉 Congratulations {winner_name}!")
        # Get quiz_id and create share button
        quiz_id = state.get("quiz_data", {}).get("id")
        reply_markup = None
                
        if quiz_id:
            try:
                bot_username = (await context.bot.get_me()).username
                keyboard = [
                    [InlineKeyboardButton("📤 Share Quiz", switch_inline_query=f"quiz_{quiz_id}")],
                    [InlineKeyboardButton("👥 Share to Group", url=f"https://t.me/{bot_username}?startgroup=groupquiz_{quiz_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                                
            except Exception as e:
                logger.error(f"[GROUP QUIZ] ❌ Error creating share button: {e}")
                reply_markup = None
        else:
            logger.warning(f"[GROUP QUIZ] ⚠️ No quiz_id found in state for chat {chat_id}")

        # Send message with share button (if available)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=leaderboard,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            
            logger.info(f"[GROUP QUIZ] ✅ Leaderboard sent {'with' if reply_markup else 'without'} share button")
                
        except Exception as e:
            logger.error(f"[GROUP QUIZ] ❌ Error sending leaderboard message: {e}")
            # Fallback: send without markup
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=leaderboard,
                    parse_mode="HTML"
                )
                logger.info(f"[GROUP QUIZ] ✅ Fallback message sent without share button")
            except Exception as fallback_error:
                logger.error(f"[GROUP QUIZ] ❌ Error sending fallback message: {fallback_error}")
                
    except Exception as e:
        logger.error(f"[GROUP QUIZ] ❌ Error sending leaderboard: {str(e)}")




async def calculate_scores(poll_data: Poll, state: Dict, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Calculate and update scores based on poll results. Returns True if anyone voted."""
    try:
        if not poll_data or not state:
            logger.error("[GROUP QUIZ] Poll data or state is None in calculate_scores")
            return False

        # Get chat_id from state
        chat_id = None
        for chat, quiz_state in GROUP_QUIZ_STATE.items():
            if quiz_state.get("last_poll_id") == poll_data.id:
                chat_id = chat
                break
                
        if not chat_id:
            logger.error("[GROUP QUIZ] Could not find chat_id for poll")
            return False

        question_data = state.get("poll_to_question", {}).get(poll_data.id)
        if not question_data:
            logger.error(f"[GROUP QUIZ] No question_data for poll_id {poll_data.id}")
            return False

        correct_option = question_data["correct_option_id"]
        question_idx = question_data.get("question_idx", -1)
        
        # Initialize scores dict if not exists
        if "scores" not in state:
            state["scores"] = {}

        # FIXED: Check once if poll has voter_ids, log only once
        has_voter_ids = False
        anyone_voted = False  # Track if anyone actually voted
        
        for option in poll_data.options:
            if hasattr(option, 'voter_ids') and option.voter_ids is not None:
                has_voter_ids = True
                if option.voter_ids:  # Check if list is not empty
                    anyone_voted = True
                    break
        
        if not has_voter_ids:
            logger.warning(f"[GROUP QUIZ] Poll {poll_data.id} is anonymous or has no voter_ids - skipping score calculation")
            return False
        
        if not anyone_voted:
            logger.info(f"[GROUP QUIZ] Poll {poll_data.id} has voter_ids support but no one voted")
            return False

        # Process poll results for each option
        for idx, option in enumerate(poll_data.options):
            if not option.voter_ids:
                continue

            for user_id in option.voter_ids:
                try:
                    # Update scores
                    if user_id not in state["scores"]:
                        state["scores"][user_id] = 0
                    
                    is_correct = (idx == correct_option)
                    if is_correct:
                        state["scores"][user_id] += 1

                    # Track basic answer details
                    if "user_answers" not in state:
                        state["user_answers"] = {}
                    if user_id not in state["user_answers"]:
                        state["user_answers"][user_id] = []

                    # Only add answer if user hasn't already answered this question
                    existing_answer = None
                    for existing in state["user_answers"][user_id]:
                        if existing.get("question_idx") == question_idx:
                            existing_answer = existing
                            break
                    
                    if not existing_answer:
                        state["user_answers"][user_id].append({
                            "question_idx": question_idx,
                            "user_choice": idx,
                            "correct_option": correct_option,
                            "is_correct": is_correct,
                            "time_spent": 0,
                            "user_answer": poll_data.options[idx].text,
                            "correct_answer": poll_data.options[correct_option].text if isinstance(correct_option, int) else [poll_data.options[i].text for i in correct_option]
                        })

                except Exception as user_error:
                    logger.error(f"[GROUP QUIZ] Error processing user {user_id}: {str(user_error)}")

        # Save updated state back to global state
        GROUP_QUIZ_STATE[chat_id] = state
        logger.info(f"[GROUP QUIZ] Successfully updated scores for chat {chat_id}")
        
        return anyone_voted  # Return whether anyone actually voted
        
    except Exception as e:
        logger.error(f"[GROUP QUIZ] Error calculating scores: {str(e)}")
        return False

async def handle_poll_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        poll = update.poll
        if not poll or not poll.is_closed:
            return
            
        # Find which chat this poll belongs to
        chat_id = None
        for chat, state in GROUP_QUIZ_STATE.items():
            if poll.id in state.get("poll_ids", []):
                chat_id = chat
                break
                
        if chat_id:
            # Group quiz - check if anyone answered
            poll_answered = any(option.voter_count > 0 for option in poll.options)
            state = GROUP_QUIZ_STATE[chat_id]
            
            # FIXED: Only increment if NOT answered
            if not poll_answered:
                state["unanswered_count"] = state.get("unanswered_count", 0) + 1
                logger.info(f"[GROUP QUIZ] Poll closed with no answers, count: {state['unanswered_count']}")
            
            await calculate_scores(poll, state, context)
        else:
            # Private quiz
            poll_answered = any(option.voter_count > 0 for option in poll.options)
            if not poll_answered:
                context.user_data['unanswered_count'] = context.user_data.get('unanswered_count', 0) + 1
                logger.info(f"[PRIVATE QUIZ] Poll closed with no answer, count: {context.user_data['unanswered_count']}")
                    
    except Exception as e:
        logger.error(f"[POLL UPDATE] Error handling poll update: {str(e)}")

async def stop_group_quiz(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int = None) -> None:
    from handlers.main_commands import stop_t
    state = GROUP_QUIZ_STATE.get(chat_id)
    lang = (state or {}).get("language") or (await get_user_language(user_id) if user_id else None) or "en"
    t = stop_t(lang)
    try:
        if not state or not state.get("active", False):
            await context.bot.send_message(chat_id=chat_id, text=t["none"])
            return

        if "last_poll_message_id" in state:
            try:
                await context.bot.stop_poll(chat_id=chat_id, message_id=state["last_poll_message_id"])
            except Exception as e:
                logger.warning(f"[GROUP QUIZ] Could not stop poll: {e}")

        state["active"] = False
        if state.get("scores"):
            title = state.get("quiz_data", {}).get("title", "Quiz")
            message = t["stopped"].format(title=title)
        else:
            message = t["stopped_empty"]

        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
        GROUP_QUIZ_STATE.pop(chat_id, None)

    except Exception as e:
        logger.error(f"[GROUP QUIZ] Error stopping quiz: {e}")
        await context.bot.send_message(chat_id=chat_id, text=t["error"])

async def handle_continue_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.start_handler import send_next_question
    """Handle continue button for paused quizzes."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("continue_quiz_"):
        # Group quiz
        chat_id = int(query.data.split("_")[-1])
        state = GROUP_QUIZ_STATE.get(chat_id)
        
        if state:
            state["paused"] = False
            state["active"] = True
            state["unanswered_count"] = 0
            
            await query.edit_message_text(
                "▶️ <b>Quiz Resumed</b>\n\nContinuing with next question...",
                parse_mode="HTML"
            )
            
            await send_group_quiz_question(context, chat_id)
    
    elif query.data == "continue_private_quiz":
        # Private quiz
        context.user_data['quiz_paused'] = False
        context.user_data['unanswered_count'] = 0
        
        await query.edit_message_text(
            "▶️ <b>Quiz Resumed</b>\n\nContinuing with next question...",
            parse_mode="HTML"
        )
        
        quiz_data = context.user_data.get('current_quiz')
        question_idx = context.user_data.get('paused_at_question', 0)
        
        if quiz_data:
            await send_next_question(context, query.message.chat_id, quiz_data, question_idx)


async def handle_stop_quiz_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from handlers.main_commands import stop_t
    """Handle stop button for paused quizzes."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("stop_quiz_"):
        chat_id = int(query.data.split("_")[-1])
        lang = GROUP_QUIZ_STATE.get(chat_id, {}).get("language") or await get_user_language(query.from_user.id)
        await query.edit_message_text(stop_t(lang)["thanks"], parse_mode="HTML")
        GROUP_QUIZ_STATE.pop(chat_id, None)
    elif query.data == "stop_private_quiz":
        lang = await get_user_language(query.from_user.id)
        await query.edit_message_text(stop_t(lang)["thanks"], parse_mode="HTML")
        
        # Clean up user_data
        for key in ['current_quiz', 'quiz_paused', 'unanswered_count', 'paused_at_question']:
            context.user_data.pop(key, None)
        
        context.user_data['busy'] = False

@track_handler("group_actions")
async def handle_group_quiz_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle group quiz actions like starting, next question, finishing, and stopping."""
    try:
        query = update.callback_query
        if not query:
            logger.error("[GROUP QUIZ] No callback query in update")
            return CONTENT

        await query.answer()

        if not query.message or not query.message.chat:
            logger.error("[GROUP QUIZ] No valid chat in callback query message")
            await query.answer("This action must be performed in a group chat.", show_alert=True)
            return CONTENT

        chat_id = query.message.chat.id
        user_id = query.from_user.id
        logger.info(f"[GROUP QUIZ] Processing action in chat: {chat_id} by user: {user_id}")

        if not query.data:
            logger.error("[GROUP QUIZ] No callback data")
            return CONTENT

        action_data = query.data
        if action_data.startswith("start_group_quiz_"):
            action = "start_group_quiz"
            quiz_id = action_data[len("start_group_quiz_"):]
        elif action_data.startswith("next_question_"):
            action = "next_question"
            quiz_id = action_data[len("next_question_"):]
        elif action_data.startswith("finish_quiz_"):
            action = "finish_quiz"
            quiz_id = action_data[len("finish_quiz_"):]
        elif action_data.startswith("stop_quiz_"):
            action = "stop_quiz"
            quiz_id = action_data[len("stop_quiz_"):]
        elif action_data == "stop_quiz":
            action = "stop_quiz"
            quiz_id = None
        else:
            logger.error(f"[GROUP QUIZ] Invalid callback data format: {query.data}")
            return CONTENT

        logger.info(f"[GROUP QUIZ] Processing action: {action} for quiz: {quiz_id} in chat: {chat_id}")

        if action == "start_group_quiz":
            if isinstance(quiz_id, dict):
                logger.error(f"[GROUP QUIZ] Invalid quiz_id type: {type(quiz_id)}. Expected string.")
                await query.message.reply_text(
                    "❌ Invalid quiz ID. Please check the quiz link and try again.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT

            await start_group_quiz(context, chat_id, quiz_id)

        elif action == "next_question":
            state = GROUP_QUIZ_STATE.get(chat_id)
            if not state or not state["active"]:
                await query.message.reply_text(
                    "❌ No active quiz in this group.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT

            await send_group_quiz_question(context, chat_id)

        elif action == "finish_quiz":
            state = GROUP_QUIZ_STATE.get(chat_id)
            if not state or not state["active"]:
                await query.message.reply_text(
                    "❌ No active quiz to finish.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return CONTENT

            await finish_group_quiz(context, chat_id)

        elif action == "stop_quiz":
            await stop_group_quiz(context, chat_id, user_id)

        return CONTENT

    except Exception as e:
        logger.error(f"Error in handle_group_quiz_actions: {str(e)}")
        try:
            if update.callback_query and update.callback_query.message:
                await update.callback_query.message.reply_text(
                    "❌ An error occurred while handling the quiz action.",
                    parse_mode=ParseMode.MARKDOWN
                )
            elif update.callback_query:
                await update.callback_query.answer(
                    "❌ An error occurred while handling the quiz action.",
                    show_alert=True
                )
        except Exception as err:
            logger.error(f"Failed to send error message: {err}")
        return CONTENT
    


