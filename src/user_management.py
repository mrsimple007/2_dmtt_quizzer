from src.tables import TBL
from datetime import datetime, timezone, timedelta
from src.prompts_summarize import TRANSLATIONS, LANGUAGES, QUIZ_TYPES, QUIZ_TYPE_INFO
import os
import logging
from supabase import create_client, Client
import uuid
import json
from src.imports import *
from typing import Dict, List, Optional
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    CallbackQueryHandler, filters, ContextTypes, PollAnswerHandler, InlineQueryHandler
)
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ContextTypes, ChatMemberHandler
from telegram import ChatMemberUpdated
from telegram.constants import ChatMemberStatus


logger = logging.getLogger(__name__)
SUPABASE_URL = os.environ.get("QUIZ_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("QUIZ_SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ──────────────────────────────────────────────────────────────────────────
# CRITICAL FIX: supabase-py's .execute() is a BLOCKING/synchronous network
# call. Calling it directly inside an `async def` function does NOT make it
# non-blocking — it freezes the entire asyncio event loop for the duration
# of the HTTP request, which means EVERY other user's update (across the
# whole bot) is stuck waiting. With 10-15 concurrent /start requests, each
# doing several sequential DB calls, this serializes everything and the bot
# appears to "just stop working".
#
# Fix: run every blocking supabase call in a dedicated thread pool via
# run_in_executor, so the event loop stays free to handle other users while
# the DB request is in flight.
#
# Dedicated executor (not the default one) so DB I/O doesn't compete with
# other executor usage (e.g. file downloads) and so we can size it for our
# expected concurrency.
_DB_EXECUTOR = ThreadPoolExecutor(max_workers=32, thread_name_prefix="supabase")

import sys
import time
from src.cache import cache_get, cache_set, cache_del
from src.perf_timing import record

_DB_EXECUTOR = ThreadPoolExecutor(max_workers=32, thread_name_prefix="supabase")


async def run_supabase(query_fn):
    caller = sys._getframe(1).f_code.co_name
    loop = asyncio.get_running_loop()
    submitted = time.perf_counter()
    started = {}

    def wrapped():
        started["t"] = time.perf_counter()
        return query_fn()

    try:
        return await loop.run_in_executor(_DB_EXECUTOR, wrapped)
    finally:
        end = time.perf_counter()
        run_ms = (end - started.get("t", end)) * 1000
        wait_ms = (started.get("t", end) - submitted) * 1000
        record(f"DB {caller} (run {run_ms:.0f} + pool-wait {wait_ms:.0f})", (end - submitted) * 1000)

_PROFILE_FIELDS = "language,quiz_type,quiz_time,quiz_questions,first_name,username"


async def get_user_profile(user_id, fresh: bool = False):
    """
    Cached SETTINGS only (language, quiz_type, quiz_time, quiz_questions).
    NEVER use it for balance or counters, those come from get_account_snapshot().
    Returns None if the user doesn't exist, raises on DB errors.
    """
    uid = int(user_id)
    key = ("profile", uid)
    if not fresh:
        hit = cache_get(key)
        if hit is not None:
            return hit
    r = await run_supabase(
        lambda: supabase.table(TBL.USERS)
            .select(_PROFILE_FIELDS).eq('user_id', str(uid)).limit(1).execute()
    )
    if not r.data:
        return None
    p = r.data[0]
    cache_set(key, p, 600)
    if p.get("language"):
        cache_set(("lang", uid), p["language"], 3600)
    return p


def invalidate_user_cache(user_id):
    uid = int(user_id)
    cache_del(("profile", uid), ("lang", uid))


async def get_account_snapshot(user_id) -> dict:
    """Fresh full row (balance, total_quizzes, is_premium...). One query, never cached."""
    r = await run_supabase(
        lambda: supabase.table(TBL.USERS)
            .select('*').eq('user_id', str(int(user_id))).limit(1).execute()
    )
    return r.data[0] if r.data else {}


async def touch_user_activity(user_id, username=None, first_name=None, last_name=None) -> None:
    """update_user_activity at most once per 5 minutes per user."""
    key = ("touched", int(user_id))
    if cache_get(key):
        return
    cache_set(key, True, 300)
    await update_user_activity(user_id=user_id, username=username,
                               first_name=first_name, last_name=last_name)


async def get_invited_users_count_cached(user_id: int) -> int:
    key = ("invited", int(user_id))
    hit = cache_get(key)
    if hit is not None:
        return hit
    n = await get_invited_users_count(user_id)
    cache_set(key, n, 60)
    return n


async def refund_balance(user_id: int, amount: int) -> bool:
    from src.imports import is_free_user
    if is_free_user(user_id):
        return False         # never charged -> nothing to give back (and no 'refunded' message)
    snap = await get_account_snapshot(user_id)
    return await update_user_balance(user_id, (snap.get('balance') or 0) + amount)




async def check_user_exists(user_id: int) -> bool:
    try:
        return (await get_user_profile(user_id)) is not None
    except Exception as e:
        logger.error(f"Error checking user existence: {e}")
        return False



async def create_new_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None, language: str = "en", quiz_time: int = 30, quiz_questions: int = 5, inviter_id: str = None) -> bool:
    try:
        from src.imports import INITIAL_BALANCE_UZS  # Import at function level

        user_data = {
            'user_id': str(user_id),
            'first_name': first_name or "",
            'last_name': last_name or "",
            'username': username or "",
            'language': language,
            'quiz_type': 'mc',
            'quiz_time': quiz_time,
            'quiz_questions': quiz_questions,
            'total_quizzes': 0,
            'is_premium': False,
            'balance': INITIAL_BALANCE_UZS * 100,
            'total_correct_answers': 0,
            'total_payments': 0,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'last_interaction': datetime.now(timezone.utc).isoformat()
        }

        if inviter_id:
            user_data['invited_by'] = str(inviter_id)

        response = await run_supabase(
            lambda: supabase.table(TBL.USERS).insert(user_data).execute()
        )

        logger.info(f"Created new user with ID {user_id}, quiz_type: mc, quiz_time: {quiz_time}, quiz_questions: {quiz_questions}, balance: {INITIAL_BALANCE_UZS * 100}")
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error creating new user: {e}")
        return False


async def update_user_activity(user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> None:
    try:
        if not isinstance(user_id, int):
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                logger.error(f"Invalid user_id type: {type(user_id)}, value: {user_id}")
                return

        update_data = {
            'last_interaction': datetime.now(timezone.utc).isoformat(),
            'quiz_type': 'mc'
        }

        if username is not None:
            update_data['username'] = username
        if first_name is not None:
            update_data['first_name'] = first_name
        if last_name is not None:
            update_data['last_name'] = last_name

        await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .update(update_data)
                .eq('user_id', str(user_id))
                .execute()
        )

        logger.info(f"Successfully updated user activity for user {user_id} ")

    except Exception as e:
        logger.error(f"Error updating user activity for user {user_id}: {e}")


def get_translation(lang: str, key: str) -> str:
    """Get translation for a key in specified language, fallback to English."""
    try:
        if lang in TRANSLATIONS and key in TRANSLATIONS[lang]:
            return TRANSLATIONS[lang][key]
        return TRANSLATIONS["en"][key]
    except Exception as e:
        logger.error(f"Translation error for lang: {lang}, key: {key} - {e}")
        try:
            return TRANSLATIONS["en"][key]
        except:
            return f"Translation missing: {key}"


async def get_user_language(user_id) -> str:
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return "en"
    lang = cache_get(("lang", uid))
    if lang:
        return lang
    try:
        p = await get_user_profile(uid)
        if p and p.get("language"):
            return p["language"]
    except Exception as e:
        logger.error(f"Error getting user language: {e}")
    return "en"



async def get_user_quiz_type(user_id: int) -> str:
    try:
        p = await get_user_profile(user_id)
        if p and p.get("quiz_type"):
            return p["quiz_type"]
    except Exception as e:
        logger.error(f"Error getting user quiz type: {e}")
    return "mc"



async def update_user_language(user_id: int, language: str) -> None:
    try:
        valid_languages = ['en', 'uz', 'ru']
        if language not in valid_languages:
            logger.error(f"Invalid language code '{language}' for user {user_id}, defaulting to 'uz'")
            language = 'uz'

        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('user_id')
                .eq('user_id', user_id)
                .execute()
        )

        if response.data and len(response.data) > 0:
            await run_supabase(
                lambda: supabase.table(TBL.USERS)
                    .update({'language': language})
                    .eq('user_id', user_id)
                    .execute()
            )
        else:
            await run_supabase(
                lambda: supabase.table(TBL.USERS).insert({
                    'user_id': user_id,
                    'language': language,
                    'quiz_type': 'mc',
                    'created_at': datetime.now().isoformat(),
                    'last_interaction': datetime.now().isoformat()
                }).execute()
            )

        logger.info(f"Updated language to {language} for user {user_id}")
    except Exception as e:
        logger.error(f"Error updating user language: {e}")


async def update_user_quiz_type(user_id: int, quiz_type: str) -> None:
    try:
        if quiz_type not in QUIZ_TYPES:
            logger.error(f"Invalid quiz type: {quiz_type}")
            return

        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('user_id')
                .eq('user_id', user_id)
                .execute()
        )

        if response.data and len(response.data) > 0:
            await run_supabase(
                lambda: supabase.table(TBL.USERS)
                    .update({'quiz_type': quiz_type})
                    .eq('user_id', user_id)
                    .execute()
            )
        else:
            await run_supabase(
                lambda: supabase.table(TBL.USERS).insert({
                    'user_id': user_id,
                    'language': 'en',
                    'quiz_type': quiz_type,
                    'created_at': datetime.now().isoformat(),
                    'last_interaction': datetime.now().isoformat()
                }).execute()
            )

        logger.info(f"Updated quiz type to {quiz_type} for user {user_id}")
    except Exception as e:
        logger.error(f"Error updating user quiz type: {e}")


async def get_user_premium_status(user_id: int) -> bool:
    from handlers.premium import parse_subscription
    return bool(parse_subscription(await get_account_snapshot(user_id)).get("is_active"))

async def get_user_quizzes_light(user_id: int, limit: int = 50) -> List[Dict]:
    try:
        r = await run_supabase(
            lambda: supabase.table(TBL.QUIZZES)
                .select('id,title,created_at,question_count')
                .eq('user_id', str(user_id))
                .order('created_at', desc=True)
                .limit(limit)
                .execute()
        )
        return r.data or []
    except Exception as e:
        logger.error(f"Error getting user quizzes: {e}")
        return []


async def get_admin_stats():
    """The 5 dashboard numbers, cached for 2 minutes."""
    hit = cache_get(("admin_stats",))
    if hit:
        return hit
    res = await asyncio.gather(
        get_total_users(), get_total_processed_files(), get_todays_active_users(),
        get_total_groups(), get_success_rate())
    cache_set(("admin_stats",), res, 120)
    return res



async def update_user_premium_status(user_id: int, is_premium: bool) -> None:
    """Update user's premium status in the database."""
    try:
        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('user_id')
                .eq('user_id', user_id)
                .execute()
        )

        if response.data and len(response.data) > 0:
            await run_supabase(
                lambda: supabase.table(TBL.USERS).update({
                    'is_premium': is_premium,
                    'last_interaction': datetime.now().isoformat()
                }).eq('user_id', user_id).execute()
            )
        else:
            await run_supabase(
                lambda: supabase.table(TBL.USERS).insert({
                    'user_id': user_id,
                    'language': 'en',
                    'quiz_type': 'mc',
                    'is_premium': is_premium,
                    'created_at': datetime.now().isoformat(),
                    'last_interaction': datetime.now().isoformat()
                }).execute()
            )

        logger.info(f"Updated premium status to {is_premium} for user {user_id}")
    except Exception as e:
        logger.error(f"Error updating user premium status: {e}")


async def update_user_quiz_time(user_id: int, time: int) -> None:
    try:
        is_premium = await get_user_premium_status(user_id)
        if not is_premium:
            logger.error(f"User {user_id} is not premium, cannot change quiz time")
            return

        if not 15 <= time <= 120:
            logger.error(f"Invalid quiz time: {time}")
            return

        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('user_id')
                .eq('user_id', user_id)
                .execute()
        )

        if response.data and len(response.data) > 0:
            await run_supabase(
                lambda: supabase.table(TBL.USERS)
                    .update({'quiz_time': time})
                    .eq('user_id', user_id)
                    .execute()
            )
        else:
            await run_supabase(
                lambda: supabase.table(TBL.USERS).insert({
                    'user_id': user_id,
                    'language': 'en',
                    'quiz_type': 'mc',
                    'quiz_time': time,
                    'quiz_questions': 5,
                    'created_at': datetime.now().isoformat(),
                    'last_interaction': datetime.now().isoformat()
                }).execute()
            )

        logger.info(f"Updated quiz time to {time} seconds for user {user_id}")
    except Exception as e:
        logger.error(f"Error updating user quiz time: {e}")


async def update_user_quiz_questions(user_id: int, questions: int) -> None:
    try:
        is_premium = await get_user_premium_status(user_id)
        if not is_premium:
            logger.error(f"User {user_id} is not premium, cannot change number of questions")
            return

        if not 3 <= questions <= 10:
            logger.error(f"Invalid number of questions: {questions}")
            return

        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('user_id')
                .eq('user_id', user_id)
                .execute()
        )

        if response.data and len(response.data) > 0:
            await run_supabase(
                lambda: supabase.table(TBL.USERS)
                    .update({'quiz_questions': questions})
                    .eq('user_id', user_id)
                    .execute()
            )
        else:
            await run_supabase(
                lambda: supabase.table(TBL.USERS).insert({
                    'user_id': user_id,
                    'language': 'en',
                    'quiz_type': 'mc',
                    'quiz_time': 30,
                    'quiz_questions': questions,
                    'created_at': datetime.now().isoformat(),
                    'last_interaction': datetime.now().isoformat()
                }).execute()
            )

        logger.info(f"Updated number of questions to {questions} for user {user_id}")
    except Exception as e:
        logger.error(f"Error updating user quiz questions: {e}")


async def update_quiz_stats(user_id: int, correct: bool) -> None:
    """Update user's quiz statistics."""
    try:
        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('total_quizzes, correct_answers')
                .eq('user_id', str(user_id))
                .execute()
        )

        if response.data and len(response.data) > 0:
            current_stats = response.data[0]
            total_quizzes = (current_stats.get('total_quizzes') or 0) + 1
            correct_answers = (current_stats.get('correct_answers') or 0) + (1 if correct else 0)

            await run_supabase(
                lambda: supabase.table(TBL.USERS).update({
                    'total_quizzes': total_quizzes,
                    'correct_answers': correct_answers
                }).eq('user_id', str(user_id)).execute()
            )

            logger.info(f"Updated quiz stats for user {user_id}: total={total_quizzes}, correct={correct_answers}")
    except Exception as e:
        logger.error(f"Error updating quiz stats: {e}")


async def get_user_stats(user_id: int) -> dict:
    """Get user's quiz statistics."""
    try:
        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('total_quizzes, correct_answers')
                .eq('user_id', user_id)
                .execute()
        )

        if response.data and len(response.data) > 0:
            stats = response.data[0]
            return {
                'total_quizzes': stats['total_quizzes'],
                'correct_answers': stats['correct_answers'],
                'accuracy': (stats['correct_answers'] / stats['total_quizzes'] * 100) if stats['total_quizzes'] > 0 else 0
            }
        return {'total_quizzes': 0, 'correct_answers': 0, 'accuracy': 0}
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {'total_quizzes': 0, 'correct_answers': 0, 'accuracy': 0}


async def get_invited_users_count(user_id: int) -> int:
    r = await run_supabase(lambda: supabase.table(TBL.USERS)
        .select('user_id', count='exact').eq('invited_by', str(user_id)).limit(1).execute())
    return r.count or 0


async def get_user_balance(user_id: int) -> int:
    from src.imports import INITIAL_BALANCE_UZS
    try:
        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('balance')
                .eq('user_id', str(user_id))
                .execute()
        )

        if not response.data or len(response.data) == 0:
            await create_new_user(
                user_id=user_id,
                first_name="",
                last_name="",
                username="",
                language="uz",
                quiz_time=30,
                quiz_questions=5
            )
            return INITIAL_BALANCE_UZS * 100

        balance = response.data[0].get('balance')

        if balance is None:
            balance = INITIAL_BALANCE_UZS * 100
            await update_user_balance_direct(user_id, balance)
            logger.warning(f"Fixed NULL balance for user {user_id}, set to {balance}")

        return balance
    except Exception as e:
        logger.error(f"Error getting user balance: {e}")
        return 0


async def update_user_balance_direct(user_id: int, balance: int) -> bool:
    """Directly set user balance without validation (for fixing NULL values)."""
    try:
        await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .update({'balance': balance})
                .eq('user_id', str(user_id))
                .execute()
        )
        return True
    except Exception as e:
        logger.error(f"Error updating user balance directly: {e}")
        return False


async def get_user_quiz_time(user_id: int) -> int:
    try:
        p = await get_user_profile(user_id)
        if p and p.get("quiz_time") is not None:
            return int(p["quiz_time"])
    except Exception as e:
        logger.error(f"Error getting user quiz time for user {user_id}: {e}")
    return 30


async def get_user_quiz_questions(user_id: int) -> int:
    try:
        p = await get_user_profile(user_id)
        if p and p.get("quiz_questions"):
            return p["quiz_questions"]
    except Exception as e:
        logger.error(f"Error getting user quiz questions: {e}")
    return 5


async def get_total_users() -> int:
    r = await run_supabase(lambda: supabase.table(TBL.USERS)
                           .select('user_id', count='exact').limit(1).execute())
    return r.count or 0


async def get_todays_active_users() -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    r = await run_supabase(lambda: supabase.table(TBL.USERS)
                           .select('user_id', count='exact').gte('last_interaction', start).limit(1).execute())
    return r.count or 0


async def get_total_processed_files() -> int:
    r = await run_supabase(lambda: supabase.table(TBL.FILES)
                           .select('id', count='exact').limit(1).execute())
    return r.count or 0


async def get_success_rate() -> float:
    total, ok = await asyncio.gather(
        run_supabase(lambda: supabase.table(TBL.FILES).select('id', count='exact').limit(1).execute()),
        run_supabase(lambda: supabase.table(TBL.FILES).select('id', count='exact').eq('status', 'success').limit(1).execute()),
    )
    return (ok.count / total.count * 100) if total.count else 0.0

async def save_file_info(file_info: dict) -> None:
    """Save file information to the database."""
    try:
        await run_supabase(
            lambda: supabase.table(TBL.FILES).insert(file_info).execute()
        )
        logger.info(f"Saved file info for user {file_info['user_id']}")
    except Exception as e:
        logger.error(f"Error saving file info: {e}")


_fallback_bot = None


async def save_shared_quiz(quiz_data: Dict, owner_id: int, bot=None) -> str:
    global _fallback_bot
    from telegram import Bot
    from src.imports import BOT_TOKEN

    language = await get_user_language(owner_id)            # cached
    quiz_time = await get_user_quiz_time(owner_id)          # cached
    quiz_questions = await get_user_quiz_questions(owner_id)  # cached

    title = quiz_data.get("title", "")
    summary = quiz_data.get("summary", "")
    quiz_id = str(uuid.uuid4())
    quiz_data["user_id"] = owner_id

    author = quiz_data.get("author") or cache_get(("author", owner_id))
    if not author:
        try:
            b = bot
            if b is None:
                if _fallback_bot is None:
                    _fallback_bot = Bot(token=BOT_TOKEN)
                b = _fallback_bot
            user = await b.get_chat(owner_id)
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            author = f"{name} (@{user.username})" if user.username else name
            cache_set(("author", owner_id), author, 86400)
        except Exception as e:
            logger.error(f"Error getting user info for author: {e}")
            author = "Unknown"

    await run_supabase(
        lambda: supabase.table(TBL.QUIZZES).insert({
            "id": quiz_id, "user_id": owner_id, "quiz_data": quiz_data,
            "title": title, "summary": summary, "language": language,
            "quiz_time": quiz_time, "num_questions": quiz_questions, "author": author
        }).execute()
    )
    return quiz_id


async def get_shared_quiz(quiz_id: str) -> Optional[Dict]:
    key = ("quiz", quiz_id)
    hit = cache_get(key)
    if hit is not None:
        return hit
    resp = await run_supabase(
        lambda: supabase.table(TBL.QUIZZES).select("*").eq("id", quiz_id).limit(1).execute()
    )
    if resp.data:
        data = resp.data[0]["quiz_data"]
        cache_set(key, data, 600)
        return data
    return None
 
async def get_quiz_owner_id(quiz_id: str) -> Optional[int]:    
    result = await run_supabase(
        lambda: supabase.table(TBL.QUIZZES).select("user_id").eq("id", quiz_id).execute()
    )
    if result.data:
        return result.data[0]["user_id"]
    return None


def extract_status_change(chat_member_update: ChatMemberUpdated) -> tuple[bool, bool]:
    """Extract member status change from ChatMemberUpdated."""
    try:
        status_change = chat_member_update.difference().get("status")
        old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

        if status_change is None:
            return None

        old_status, new_status = status_change
        was_member = old_status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        ] or (old_status == ChatMemberStatus.RESTRICTED and old_is_member is True)

        is_member = new_status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        ] or (new_status == ChatMemberStatus.RESTRICTED and new_is_member is True)

        return was_member, is_member

    except Exception as e:
        logger.error(f"Error extracting status change: {e}")
        return None


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat = update.effective_chat
        if chat is None or chat.type not in ("group", "supergroup", "channel"):
            return      # private chat: the user started/blocked the bot, not a group

        result = extract_status_change(update.my_chat_member)
        if result is None:
            return
        was_member, is_member = result
        user = update.effective_user
        chat = update.effective_chat

        if not was_member and is_member:
            logger.info(
                f"Bot added to group {chat.title} (ID: {chat.id}) "
                f"by user {user.id}, {user.full_name}"
            )

            try:
                total_members = await context.bot.get_chat_member_count(chat.id)
            except Exception as e:
                logger.warning(f"Could not get member count for {chat.id}: {e}")
                total_members = None

            await save_group_info(
                group_id=chat.id,
                title=chat.title,
                username=chat.username,
                group_type=chat.type,
                added_by_user_id=user.id,
                added_by_first_name=user.first_name,
                added_by_last_name=user.last_name,
                added_by_username=user.username,
                total_members=total_members
            )

    except Exception as e:
        logger.error(f"Error handling chat member update: {e}")


async def save_group_info(
    group_id,
    title,
    username,
    group_type,
    added_by_user_id=None,
    added_by_first_name=None,
    added_by_last_name=None,
    added_by_username=None,
    total_members=None
):
    """Save or update group info in Supabase."""
    try:
        data = {
            "id": group_id,
            "title": title,
            "username": username,
            "type": group_type,
            "last_interaction": datetime.now(timezone.utc).isoformat()
        }

        if added_by_user_id is not None:
            data["added_by_user_id"] = added_by_user_id
        if added_by_first_name is not None:
            data["added_by_first_name"] = added_by_first_name
        if added_by_last_name is not None:
            data["added_by_last_name"] = added_by_last_name
        if added_by_username is not None:
            data["added_by_username"] = added_by_username
        if total_members is not None:
            data["total_members"] = total_members

        existing = await run_supabase(
            lambda: supabase.table(TBL.GROUPS).select("id").eq("id", group_id).execute()
        )
        if not existing.data:
            data["added_at"] = datetime.now(timezone.utc).isoformat()

        await run_supabase(
            lambda: supabase.table(TBL.GROUPS).upsert(data).execute()
        )
        logger.info(f"Group info saved: {title} (ID: {group_id})")

    except Exception as e:
        logger.error(f"Error saving group info: {e}")


async def get_total_members_in_groups():
    """Return the total number of members across all groups."""
    try:
        resp = await run_supabase(
            lambda: supabase.table(TBL.GROUPS).select("total_members").execute()
        )
        if resp.data:
            total = sum(group.get("total_members", 0) or 0 for group in resp.data)
            return total
        return 0
    except Exception as e:
        logger.error(f"Error getting total members in groups: {e}")
        return 0


async def update_existing_groups_member_count(context: ContextTypes.DEFAULT_TYPE):
    """Update member counts for all existing groups (run once)."""
    try:
        resp = await run_supabase(
            lambda: supabase.table(TBL.GROUPS).select("id, title").execute()
        )
        groups = resp.data

        logger.info(f"Starting to update member counts for {len(groups)} groups...")

        updated_count = 0
        failed_count = 0

        for group in groups:
            group_id = group["id"]
            try:
                total_members = await context.bot.get_chat_member_count(group_id)

                await run_supabase(
                    lambda gid=group_id, tm=total_members: supabase.table(TBL.GROUPS)
                        .update({"total_members": tm})
                        .eq("id", gid)
                        .execute()
                )

                updated_count += 1
                logger.info(f"Updated group {group.get('title', 'Unknown')} ({group_id}): {total_members} members")

                await asyncio.sleep(0.1)

            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to update group {group_id}: {e}")

        logger.info(f"Finished updating groups. Success: {updated_count}, Failed: {failed_count}")
        return updated_count, failed_count

    except Exception as e:
        logger.error(f"Error in update_existing_groups_member_count: {e}")
        return 0, 0


async def create_user_with_balance(user_id: int, balance: int) -> None:
    """Create new user with initial balance."""
    try:
        await run_supabase(
            lambda: supabase.table(TBL.USERS).insert({
                'user_id': str(user_id),
                'balance': balance,
                'is_premium': False,
                'created_at': datetime.now().isoformat()
            }).execute()
        )
    except Exception as e:
        logger.error(f"Error creating user with balance: {e}")


async def update_user_balance(user_id: int, new_balance: int) -> bool:
    """Update user balance to the specified amount (not adding, just setting)."""
    try:
        if new_balance < 0:
            return False  # Insufficient balance

        await run_supabase(
            lambda: supabase.table(TBL.USERS).update({
                'balance': new_balance,
                'last_interaction': datetime.now().isoformat()
            }).eq('user_id', str(user_id)).execute()
        )

        return True
    except Exception as e:
        logger.error(f"Error updating user balance: {e}")
        return False


async def deduct_ppt_cost(user_id: int) -> bool:
    from src.imports import PPT_COST_UZS
    cost = PPT_COST_UZS * 100
    return await update_user_balance(user_id, -cost)


async def get_or_create_user(user) -> dict:
    """
    NOTE: converted to `async def` and fixed to use `await` instead of
    `loop.run_until_complete(...)`, which crashes if called from inside a
    running event loop (which it always is, since this bot is fully async).
    Callers must now `await get_or_create_user(user)`.
    """
    try:
        user_id = user.id
        response = await run_supabase(
            lambda: supabase.table(TBL.USERS).select('*').eq('user_id', str(user_id)).execute()
        )
        if response.data and len(response.data) > 0:
            user_data = response.data[0]
            return {
                "id": user_id,
                "language": user_data.get("language", "en"),
                "first_name": user_data.get("first_name", user.first_name if hasattr(user, "first_name") else ""),
                "last_name": user_data.get("last_name", user.last_name if hasattr(user, "last_name") else ""),
                "username": user_data.get("username", user.username if hasattr(user, "username") else ""),
                "quiz_type": user_data.get("quiz_type", "mc"),
                "quiz_time": user_data.get("quiz_time", 30),
                "quiz_questions": user_data.get("quiz_questions", 5),
                "balance": user_data.get("balance", 0),
                "is_premium": user_data.get("is_premium", False)
            }
        else:
            language = getattr(user, "language_code", "en")
            first_name = getattr(user, "first_name", "")
            last_name = getattr(user, "last_name", "")
            username = getattr(user, "username", "")

            await create_new_user(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                username=username,
                language=language
            )
            return {
                "id": user_id,
                "language": language,
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "quiz_type": "mc",
                "quiz_time": 30,
                "quiz_questions": 5,
                "balance": 400000,
                "is_premium": False
            }
    except Exception as e:
        logger.error(f"Error in get_or_create_user: {e}")
        return {
            "id": getattr(user, "id", None),
            "language": getattr(user, "language_code", "en"),
            "first_name": getattr(user, "first_name", ""),
            "last_name": getattr(user, "last_name", ""),
            "username": getattr(user, "username", ""),
            "quiz_type": "mc",
            "quiz_time": 30,
            "quiz_questions": 5,
            "balance": 400000,
            "is_premium": False
        }


async def record_quiz_payment(
    user_id: int,
    amount: int,
    payment_type: str = "quiz_generation",
    payment_method: str = "balance_deduction",
    transaction_id: str = None,
    status: str = "completed",
    metadata: dict = None
) -> bool:
    """Record a payment in quiz history and update total_payments."""
    try:
        payment_data = {
            "user_id": str(user_id),
            "amount": amount,
            "payment_type": payment_type,
            "payment_method": payment_method,
            "transaction_id": transaction_id,
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        if metadata:
            payment_data["metadata"] = metadata

        await run_supabase(
            lambda: supabase.table(TBL.PAYMENT_HISTORY).insert(payment_data).execute()
        )

        if status == "completed":
            current_total = await get_user_total_quiz_payments(user_id)
            new_total = current_total + amount

            await run_supabase(
                lambda: supabase.table(TBL.USERS)
                    .update({'total_payments': new_total})
                    .eq('user_id', str(user_id))
                    .execute()
            )

        logger.info(f"Recorded quiz payment for user {user_id}: {amount} kopecks, type: {payment_type}")
        return True
    except Exception as e:
        logger.error(f"Error recording quiz payment: {e}")
        return False


async def record_subscription_payment(
    user_id: int,
    plan_key: str,
    amount: int,
    payment_method: str = "manual",
    transaction_id: str = None
) -> bool:
    """Record subscription payment and activate subscription"""
    try:
        from handlers.premium import activate_subscription, SUBSCRIPTION_PLANS

        success = await activate_subscription(user_id, plan_key, payment_method)

        if not success:
            return False

        plan = SUBSCRIPTION_PLANS.get(plan_key)
        if not plan:
            return False

        payment_data = {
            "user_id": str(user_id),
            "amount": amount,
            "payment_type": "subscription",
            "payment_method": payment_method,
            "transaction_id": transaction_id,
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {
                "subscription_type": plan_key,
                "duration_months": plan["duration_months"]
            }
        }

        await run_supabase(
            lambda: supabase.table(TBL.PAYMENT_HISTORY).insert(payment_data).execute()
        )

        current_total = await get_user_total_quiz_payments(user_id)
        new_total = current_total + amount

        await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .update({'total_payments': new_total})
                .eq('user_id', str(user_id))
                .execute()
        )

        logger.info(f"Recorded subscription payment for user {user_id}: {amount} kopecks, plan: {plan_key}")
        return True
    except Exception as e:
        logger.error(f"Error recording subscription payment: {e}")
        return False


async def get_user_total_quiz_payments(user_id: int) -> int:
    """Get total payments made by user in kopecks."""
    try:
        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('total_payments')
                .eq('user_id', str(user_id))
                .execute()
        )

        if response.data and len(response.data) > 0:
            return response.data[0].get('total_payments', 0)
        return 0
    except Exception as e:
        logger.error(f"Error getting user total quiz payments: {e}")
        return 0


async def get_top_paying_quiz_users(limit: int = 15):
    """Get users with highest total payments including their details."""
    try:
        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('user_id, total_payments, first_name, username')
                .order('total_payments', desc=True)
                .limit(limit)
                .execute()
        )

        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error getting top paying quiz users: {e}")
        return []


async def get_monthly_quiz_revenue(year: int = None, month: int = None):
    """Get total quiz revenue for a specific month."""
    try:
        if year is None or month is None:
            now = datetime.now()
            year, month = now.year, now.month

        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        response = await run_supabase(
            lambda: supabase.table(TBL.PAYMENT_HISTORY)
                .select('amount')
                .eq('status', 'completed')
                .gte('created_at', start_date.isoformat())
                .lt('created_at', end_date.isoformat())
                .execute()
        )

        total = sum(payment['amount'] for payment in response.data) if response.data else 0
        return total
    except Exception as e:
        logger.error(f"Error getting monthly quiz revenue: {e}")
        return 0


async def get_total_quiz_revenue():
    """Get total quiz revenue all time."""
    try:
        response = await run_supabase(
            lambda: supabase.table(TBL.PAYMENT_HISTORY)
                .select('amount')
                .eq('status', 'completed')
                .execute()
        )

        total = sum(payment['amount'] for payment in response.data) if response.data else 0
        return total
    except Exception as e:
        logger.error(f"Error getting total quiz revenue: {e}")
        return 0


async def get_subscription_status(user_id: int) -> tuple[bool, datetime, datetime]:
    """Get user's subscription status and dates from database."""
    try:
        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('is_premium, subscription_start, subscription_end')
                .eq('user_id', str(user_id))
                .execute()
        )

        if not response.data or len(response.data) == 0:
            return False, None, None

        user_data = response.data[0]
        is_premium = user_data.get('is_premium', False)

        if not is_premium:
            return False, None, None

        start_date = datetime.fromisoformat(user_data.get('subscription_start')) if user_data.get('subscription_start') else None
        end_date = datetime.fromisoformat(user_data.get('subscription_end')) if user_data.get('subscription_end') else None

        return True, start_date, end_date
    except Exception as e:
        logger.error(f"Error getting subscription status: {e}")
        return False, None, None


async def get_total_groups():
    """Return the total number of groups."""
    resp = await run_supabase(
        lambda: supabase.table(TBL.GROUPS).select("id", count="exact").execute()
    )
    return resp.count or 0


async def get_user_quizzes(user_id: int, limit: int = 50) -> List[Dict]:
    """Get quizzes created by a specific user."""
    try:
        response = await run_supabase(
            lambda: supabase.table(TBL.QUIZZES)
                .select('*')
                .eq('user_id', str(user_id))
                .order('created_at', desc=True)
                .limit(limit)
                .execute()
        )

        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error getting user quizzes: {e}")
        return []


async def log_quiz_activity(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Log quiz creation to activity tracker bot's database"""
    try:
        from src.imports import supabase, POINTS_FOR_QUIZ, supabase_activity

        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('username, first_name')
                .eq('user_id', str(user_id))
                .execute()
        )

        username = None
        first_name = None

        if response.data and len(response.data) > 0:
            user_data = response.data[0]
            username = user_data.get('username')
            first_name = user_data.get('first_name')

        timestamp = datetime.now(timezone.utc).isoformat()

        activity_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'activity_type': 'quiz',
            'points': POINTS_FOR_QUIZ,
            'timestamp': timestamp,
            'post_id': None,
            'post_timestamp': None
        }

        await run_supabase(
            lambda: supabase_activity.table('activity_log').insert(activity_data).execute()
        )
        logger.info(f"✅ Logged quiz activity for user {user_id}: +{POINTS_FOR_QUIZ} points")

    except Exception as e:
        logger.error(f"❌ Error logging quiz activity: {e}")


async def get_user_referral_count(user_id: int) -> int:
    """Get the number of referrals a user has made."""
    try:
        response = await run_supabase(
            lambda: supabase.table(TBL.USERS)
                .select('user_id')
                .eq('invited_by', str(user_id))
                .execute()
        )

        return len(response.data) if response.data else 0
    except Exception as e:
        logger.error(f"Error getting user referral count: {e}")
        return 0


async def get_daily_revenue(date: datetime = None):
    """Get total revenue for a specific day."""
    try:
        if date is None:
            date = datetime.now(timezone.utc)

        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)

        response = await run_supabase(
            lambda: supabase.table(TBL.PAYMENT_HISTORY)
                .select('amount')
                .eq('status', 'completed')
                .eq('payment_type', 'balance_topup')
                .gte('created_at', start_date.isoformat())
                .lt('created_at', end_date.isoformat())
                .execute()
        )

        total = sum(payment['amount'] for payment in response.data) if response.data else 0
        return total
    except Exception as e:
        logger.error(f"Error getting daily revenue: {e}")
        return 0