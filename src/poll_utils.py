"""
poll_utils.py - Telegram poll option helper.

Telegram limits a poll option to 100 characters and the options of one poll must be unique.
Long answers used to be cut to 97 chars + "..." (so they were not readable, and two long
answers with the same beginning even became duplicates -> sendPoll error).

poll_options():
  * all options <= 100 chars  -> returned unchanged
  * otherwise                 -> EVERY option gets its letter:  "A) text...", "B) text..."
    The full text of every answer is already sent in the question message right above the
    poll, so the letter is what the learner needs to match the button with the full text.
The ORDER never changes, so correct_option_id stays valid.
"""
from typing import List

MAX_POLL_OPTION = 100


def poll_options(options: List[str], limit: int = MAX_POLL_OPTION) -> List[str]:
    options = [str(o) for o in options]
    if all(len(o) <= limit for o in options):
        return options
    result = []
    for i, o in enumerate(options):
        prefix = f"{chr(65 + i)}) "
        room = limit - len(prefix)
        text = o if len(o) <= room else o[:room - 1].rstrip() + "…"
        result.append(prefix + text)
    return result