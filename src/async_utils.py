import asyncio
import logging

logger = logging.getLogger(__name__)
_bg = set()


def fire_and_forget(coro):
    task = asyncio.create_task(coro)
    _bg.add(task)

    def _done(t):
        _bg.discard(t)
        if not t.cancelled() and t.exception():
            logger.error("background task failed: %r", t.exception())

    task.add_done_callback(_done)
    return task