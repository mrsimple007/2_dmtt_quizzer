import asyncio
import gc
import logging
import os
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger("memguard")

USER_DATA_TTL = 2 * 3600          # drop a user's in-memory session after 2 h of silence
GROUP_STATE_TTL = 3 * 3600        # abandoned/paused group quizzes
JANITOR_EVERY = 600


async def touch_user(update, context):
    """Registered in group=-1: stamps every update so the janitor knows who is idle."""
    if context.user_data is not None:
        context.user_data['_ts'] = time.time()


async def janitor(application):
    from handlers.group_sharing import GROUP_QUIZ_STATE
    while True:
        await asyncio.sleep(JANITOR_EVERY)
        try:
            now = time.time()
            dropped = 0
            for uid, data in list(application.user_data.items()):
                if (now - data.get('_ts', 0) > USER_DATA_TTL
                        and not data.get('busy') and not data.get('generating')):
                    application.drop_user_data(uid)
                    dropped += 1

            gs = 0
            for chat_id, st in list(GROUP_QUIZ_STATE.items()):
                started = st.get("start_time")
                if started and (datetime.now(timezone.utc) - started).total_seconds() > GROUP_STATE_TTL:
                    GROUP_QUIZ_STATE.pop(chat_id, None)
                    gs += 1

            gc.collect()
            if dropped or gs:
                logger.info(f"janitor: dropped {dropped} idle user sessions, {gs} stale group quizzes")
        except Exception as e:
            logger.error(f"janitor error: {e}")


async def memory_monitor(application, every: int = 300):
    """One log line every 5 min: the evidence for WHAT is growing."""
    from handlers.group_sharing import GROUP_QUIZ_STATE
    from src.cache import cache_sizes
    try:
        import psutil
        proc = psutil.Process()
    except Exception:
        proc = None

    while True:
        await asyncio.sleep(every)
        try:
            rss = proc.memory_info().rss / 1e6 if proc else -1
            users = len(application.user_data)
            sample = list(application.user_data.values())[:200]
            sample_chars = sum(len(str(v)) for v in sample)
            small, heavy = cache_sizes()
            logger.warning(
                f"MEM rss={rss:.0f}MB | user_data={users} (avg {sample_chars // max(len(sample), 1)} chars/user) "
                f"| group_quizzes={len(GROUP_QUIZ_STATE)} | cache={small}+{heavy} "
                f"| tasks={len(asyncio.all_tasks())} | threads={threading.active_count()} "
                f"| gc_objects={len(gc.get_objects())}")
        except Exception as e:
            logger.error(f"memory monitor error: {e}")