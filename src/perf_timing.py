import asyncio
import contextlib
import contextvars
import functools
import logging
import os
import time

perf_logger = logging.getLogger("perf")
perf_logger.setLevel(getattr(logging, os.getenv("PERF_LEVEL", "INFO").upper(), logging.INFO))

_MIN_MS = float(os.getenv("PERF_MIN_MS", "0"))                  # print handler summary only if slower than this
_SLOW_EVENT_MS = float(os.getenv("PERF_SLOW_EVENT_MS", "800"))  # always warn about one call slower than this
_BG_MS = float(os.getenv("PERF_BG_MS", "300"))                  # background (untracked) calls: log if slower

_trace = contextvars.ContextVar("perf_trace", default=None)


class _Trace:
    __slots__ = ("t0", "events", "closed")

    def __init__(self):
        self.t0 = time.perf_counter()
        self.events = []
        self.closed = False


def record(label, ms):
    tr = _trace.get()
    if tr is not None and not tr.closed:
        end = (time.perf_counter() - tr.t0) * 1000
        tr.events.append((max(end - ms, 0.0), ms, label))
        if ms >= _SLOW_EVENT_MS:
            perf_logger.warning("🐢 slow call: %s took %.0f ms", label, ms)
    elif ms >= _BG_MS:
        perf_logger.info("⏱  (background) %s: %.0f ms", label, ms)


@contextlib.contextmanager
def timed(label):
    t = time.perf_counter()
    try:
        yield
    finally:
        record(label, (time.perf_counter() - t) * 1000)


def track_handler(name):
    """Decorator for async PTB handlers: logs one summary per update."""
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(update, context, *args, **kwargs):
            tr = _Trace()
            token = _trace.set(tr)
            user = getattr(update, "effective_user", None)
            uid = user.id if user else "?"
            msg = getattr(update, "message", None)
            lag = None
            if msg is not None and getattr(msg, "date", None) is not None:
                lag = max((time.time() - msg.date.timestamp()) * 1000, 0)
            try:
                return await fn(update, context, *args, **kwargs)
            finally:
                total = (time.perf_counter() - tr.t0) * 1000
                tr.closed = True
                _trace.reset(token)
                if total >= _MIN_MS:
                    head = f"🏁 [{name}] user={uid} TOTAL {total:.0f} ms"
                    if lag is not None:
                        head += f" | telegram→bot delay {lag:.0f} ms"
                    lines = [head]
                    for start, ms, label in sorted(tr.events):
                        lines.append(f"      +{start:6.0f}  {ms:6.0f} ms  {label}")
                    perf_logger.info("\n".join(lines))
        return wrapper
    return decorator


async def loop_lag_monitor(interval=0.25, warn_ms=250):
    """Warns when something blocks the event loop."""
    loop = asyncio.get_running_loop()
    expected = loop.time() + interval
    while True:
        await asyncio.sleep(interval)
        now = loop.time()
        lag = (now - expected) * 1000
        if lag > warn_ms:
            perf_logger.warning("🐌 EVENT LOOP BLOCKED for ~%.0f ms", lag)
        expected = now + interval


_patched = False


def patch_telegram_http():
    """Times every Bot API call (except long-polling getUpdates)."""
    global _patched
    if _patched:
        return
    try:
        from telegram.request import HTTPXRequest
    except Exception:
        return
    orig = HTTPXRequest.do_request

    async def do_request(self, url, method, *a, **kw):
        t = time.perf_counter()
        try:
            return await orig(self, url, method, *a, **kw)
        finally:
            api = str(url).rsplit("/", 1)[-1]
            if api != "getUpdates":
                record(f"TG API {api}", (time.perf_counter() - t) * 1000)

    HTTPXRequest.do_request = do_request
    _patched = True