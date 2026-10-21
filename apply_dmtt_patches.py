"""
Run from the project root AFTER apply_dmtt_tables.py:   python3 apply_dmtt_patches.py

Applies, with exact-text matching (it stops with a clear message if your code differs):
  A. FREE_USER_IDS / is_free_user  (src/imports.py)
  B. free users are never gated or charged (main.py, payment_integration_new.py,
     src/user_management.py, handlers/quiz_split_handlers.py)
  C. referral links use the REAL bot username (handlers/start_handler.py)
  D. branding: /start welcome + /info + "SimpleQuizzer" name (start_handler.py, prompts_summarize.py)
  E. payment-admin handle and BOT_NAME (prompts_summarize.py, handlers/manual_payment.py)
Needs src/brand.py (copy it next to tables.py first).
"""
import pathlib, re, sys

problems = []


def patch(path, old, new, count=1, regex=False, flags=0, applied=None):
    p = pathlib.Path(path)
    if not p.exists():
        problems.append(f"{path}: file not found")
        return
    s = p.read_text(encoding="utf-8")
    if (applied and applied in s) or (not regex and new in s):
        print(f"  skip (already applied) {path}: {old[:50]!r}")
        return
    if regex:
        s2, n = re.subn(old, new, s, flags=flags)
    else:
        n = s.count(old)
        s2 = s.replace(old, new)
    if n != count:
        problems.append(f"{path}: expected {count} match(es), found {n} for {old[:60]!r}")
        return
    p.write_text(s2, encoding="utf-8")
    print(f"  ok   {path}: {n} change(s)")


# ---- A. imports.py ----------------------------------------------------------
patch("src/imports.py",
      "from collections import defaultdict\n",
      '''from collections import defaultdict

# Users who never pay (comma separated Telegram IDs in .env). Empty = nobody.
# Defined this early on purpose: other modules import from here in a circle.
FREE_USER_IDS = {int(x) for x in os.environ.get("FREE_USER_IDS", "").replace(" ", "").split(",") if x.isdigit()}


def is_free_user(user_id) -> bool:
    try:
        return int(user_id) in FREE_USER_IDS
    except (TypeError, ValueError):
        return False

''')

# ---- B. never gate / charge / refund free users -----------------------------
patch("main.py",
      '''    try:
        with timed("gate: account snapshot"):''',
      '''    from src.imports import is_free_user
    if is_free_user(user_id):
        return gate          # blocked=False: free users are never asked for balance

    try:
        with timed("gate: account snapshot"):''')
patch("main.py",
      "        from payment_integration_new import deduct_balance\n        from handlers.premium import use_daily_free_quiz\n",
      "        from payment_integration_new import deduct_balance\n        from handlers.premium import use_daily_free_quiz\n        from src.imports import is_free_user\n")
patch("main.py",
      '        if gate["total_quizzes"] >= FREE_QUIZZES_BEFORE_PAYMENT:\n            used_free = False',
      '        if not is_free_user(user.id) and gate["total_quizzes"] >= FREE_QUIZZES_BEFORE_PAYMENT:\n            used_free = False')
patch("payment_integration_new.py",
      "async def deduct_balance(user_id: int, amount: int) -> bool:\n    from src.user_management import get_user_balance, update_user_balance\n",
      "async def deduct_balance(user_id: int, amount: int) -> bool:\n    from src.imports import is_free_user\n    if is_free_user(user_id):\n        return True          # free user: nothing to deduct\n    from src.user_management import get_user_balance, update_user_balance\n")
patch("src/user_management.py",
      "async def refund_balance(user_id: int, amount: int) -> bool:\n    snap = await get_account_snapshot(user_id)\n",
      "async def refund_balance(user_id: int, amount: int) -> bool:\n    from src.imports import is_free_user\n    if is_free_user(user_id):\n        return False         # never charged -> nothing to give back (and no 'refunded' message)\n    snap = await get_account_snapshot(user_id)\n")
patch("handlers/quiz_split_handlers.py",
      "logger = logging.getLogger(__name__)\n",
      '''logger = logging.getLogger(__name__)


def is_free_user(user_id) -> bool:
    from src.imports import is_free_user as _is_free_user   # lazy: avoids a circular import
    return _is_free_user(user_id)
''')
patch("handlers/quiz_split_handlers.py",
      r"if user_balance < split_price \* 100:",
      "if not is_free_user(update.effective_user.id) and user_balance < split_price * 100:",
      count=2, regex=True, applied="if not is_free_user(update.effective_user.id) and user_balance")
patch("handlers/quiz_split_handlers.py",
      r'^(\s*)text \+= "\\n\\n" \+ get_translation\(language, "price_label", price=split_price\)$',
      r'\1if not is_free_user(update.effective_user.id):\n\1    text += "\\n\\n" + get_translation(language, "price_label", price=split_price)',
      count=2, regex=True, flags=re.M, applied="if not is_free_user(update.effective_user.id):\n")
patch("handlers/quiz_split_handlers.py",
      "        split_price = context.user_data.get('split_price', 0)\n",
      "        split_price = 0 if is_free_user(user_id) else context.user_data.get('split_price', 0)\n")

# ---- C. referral links: real bot username -----------------------------------
patch("handlers/start_handler.py",
      "            # Still notify the invited user they joined via referral\n            joining_messages = {",
      "            # Still notify the invited user they joined via referral\n            bot_username = context.bot.username\n            joining_messages = {")
patch("handlers/start_handler.py",
      '        user_referral_link = f"https://t.me/simplequizzer_bot?start=ref_{invited_user_id}"',
      '        user_referral_link = f"https://t.me/{context.bot.username}?start=ref_{invited_user_id}"')
patch("handlers/start_handler.py", "https://t.me/simplequizzer_bot?start=ref_{invited_user_id}",
      "https://t.me/{bot_username}?start=ref_{invited_user_id}", count=3)

# ---- D. branding ---------------------------------------------------------------
patch("handlers/start_handler.py",
      "def sanitize_name(name: str) -> str:",
      '''# --- DMTT branding: teacher info under the welcome text, no ads for other bots ---
from src.brand import IS_DMTT, WELCOME_BLOCK_MD
if IS_DMTT:
    for _lang, _t in MAIN_MENU_TRANSLATIONS.items():
        _t["welcome_message"] += WELCOME_BLOCK_MD.get(_lang, WELCOME_BLOCK_MD["uz"])
        _t["contest_message"] = ""      # was an ad for another of your bots


def sanitize_name(name: str) -> str:''')
patch("src/prompts_summarize.py", "@SimpleLearn_admin", "@SimpleLearn_main_admin", count=9)
p = pathlib.Path("src/prompts_summarize.py")
if p.exists() and "from src.brand import" not in p.read_text(encoding="utf-8"):
    with p.open("a", encoding="utf-8") as f:
        f.write('''

# --- DMTT branding (on when TABLE_SET=dmtt / BRAND=dmtt) ---
from src.brand import IS_DMTT, apply_brand, INFO_TEXTS_DMTT
if IS_DMTT:
    TRANSLATIONS = apply_brand(TRANSLATIONS)
    INFO_TEXTS = INFO_TEXTS_DMTT
''')
    print("  ok   src/prompts_summarize.py: branding block appended")

# ---- E. manual_payment: bot display name ------------------------------------------
patch("handlers/manual_payment.py",
      'BOT_ID = os.getenv("BOT_ID", "simplequizzer")  # or "simpleppt"\n',
      'BOT_ID = os.getenv("BOT_ID", "simplequizzer")  # or "simpleppt"\n'
      'BOT_NAME = os.getenv("BOT_NAME", "SimpleQuizzer" if BOT_ID == "simplequizzer" '
      'else ("DMTT Quiz" if BOT_ID.startswith("dmtt") else "SimplePPT"))\n')
patch("handlers/manual_payment.py",
      'bot_name = "SimpleQuizzer" if BOT_ID == "simplequizzer" else "SimplePPT"',
      "bot_name = BOT_NAME", count=2)

print()
if problems:
    print("PROBLEMS (nothing was changed for these - your code differs from what I patched):")
    print("\n".join("  - " + x for x in problems))
    sys.exit(1)
print("All patches applied.")