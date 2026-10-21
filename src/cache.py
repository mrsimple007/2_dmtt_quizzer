import asyncio
import time
from collections import OrderedDict

_store = OrderedDict()          # small, short-lived values (profiles, language, flags)
_heavy = OrderedDict()          # big values (quizzes): hard cap
_MAX = 20_000
_HEAVY_MAX = 300
_HEAVY_NAMESPACES = {"quiz"}


def _pick(key):
    return _heavy if (isinstance(key, tuple) and key and key[0] in _HEAVY_NAMESPACES) else _store


def cache_get(key):
    d = _pick(key)
    hit = d.get(key)
    if hit is None:
        return None
    if hit[0] < time.monotonic():
        d.pop(key, None)
        return None
    d.move_to_end(key)
    return hit[1]


def cache_set(key, value, ttl: float):
    d = _pick(key)
    d[key] = (time.monotonic() + ttl, value)
    d.move_to_end(key)
    limit = _HEAVY_MAX if d is _heavy else _MAX
    while len(d) > limit:
        d.popitem(last=False)           # evict the oldest


def cache_del(*keys):
    for k in keys:
        _store.pop(k, None)
        _heavy.pop(k, None)


def cache_sizes():
    return len(_store), len(_heavy)


async def cache_sweeper(every: int = 60):
    """Expired entries are removed even if nobody reads them again."""
    while True:
        await asyncio.sleep(every)
        now = time.monotonic()
        for d in (_store, _heavy):
            for k in [k for k, v in d.items() if v[0] < now]:
                d.pop(k, None)