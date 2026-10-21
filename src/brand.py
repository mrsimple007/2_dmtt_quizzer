"""
Branding in ONE place (put this file at src/brand.py).

Switched on by  TABLE_SET=dmtt  (or BRAND=dmtt) in .env.
Anything else = your original SimpleQuizzer texts, untouched.
"""
import os
import re

_SWITCH = (os.environ.get("BRAND") or os.environ.get("TABLE_SET") or "").strip().lower()
IS_DMTT = _SWITCH == "dmtt"

# Name shown in "Welcome to ..." / help texts. Change in .env: BOT_BRAND=...
BOT_BRAND = os.environ.get("BOT_BRAND", "DMTT Quiz" if IS_DMTT else "SimpleQuizzer")

TEACHER_USERNAME = "@Hulkar_Ibragimova"
TEACHER_URL = "https://t.me/Hulkar_Ibragimova"
CHANNEL_ATTESTAT = ("DMTT_attestat_HulkarIbragimova", "https://t.me/DMTT_attestat_HulkarIbragimova")
CHANNEL_DIRECTORS = ("MTT_direktorlari", "https://t.me/MTT_direktorlari")
SUPPORT_USERNAME = "@SimpleLearn_main_admin"      # technical help

ROLES = [
    "MTT tarbiyachi",
    "MTT direktori",
    "MTT psixolog (ped mahorat)",
    "MTT til o'qituvchi (ped mahorat)",
    "MTT yoriqchi (ped mahorat)",
    "MTT logoped (ped mahorat)",
    "MTT DEFEKTOLOG",
]

_BRAND_RX = re.compile(r"(?<![@/])SimpleQuizzer(?!_bot)")


def apply_brand(obj):
    """Replace the visible name 'SimpleQuizzer' inside nested dicts/lists/strings.
    Leaves @SimpleQuizzer_bot and t.me/SimpleQuizzer_bot links alone."""
    if isinstance(obj, str):
        return _BRAND_RX.sub(BOT_BRAND, obj)
    if isinstance(obj, dict):
        return {k: apply_brand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [apply_brand(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(apply_brand(v) for v in obj)
    return obj


# ---- Markdown block appended to the /start welcome message -------------------
# (Markdown-safe: no bare underscores, handles are inside [text](url) links)
_ROLES_MD = "\n".join(f"• {r}" for r in ROLES)
_WELCOME_MD = {
    "uz": ("\n\n👩‍🏫 *HULKAR IBRAGIMOVA bilan birga*\n" + _ROLES_MD +
           f"\n\n📢 [DMTT attestat kanali]({CHANNEL_ATTESTAT[1]}) | [MTT direktorlari]({CHANNEL_DIRECTORS[1]})"
           f"\n📩 [Hulkar Ibragimova]({TEACHER_URL})"),
    "ru": ("\n\n👩‍🏫 *Вместе с HULKAR IBRAGIMOVA*\n" + _ROLES_MD +
           f"\n\n📢 [Канал DMTT attestat]({CHANNEL_ATTESTAT[1]}) | [MTT direktorlari]({CHANNEL_DIRECTORS[1]})"
           f"\n📩 [Hulkar Ibragimova]({TEACHER_URL})"),
    "en": ("\n\n👩‍🏫 *Together with HULKAR IBRAGIMOVA*\n" + _ROLES_MD +
           f"\n\n📢 [DMTT attestat channel]({CHANNEL_ATTESTAT[1]}) | [MTT direktorlari]({CHANNEL_DIRECTORS[1]})"
           f"\n📩 [Hulkar Ibragimova]({TEACHER_URL})"),
}
WELCOME_BLOCK_MD = _WELCOME_MD

# ---- /info text (HTML) --------------------------------------------------------
_ROLES_HTML = "\n".join(f"• {r}" for r in ROLES)


def _info(title: str, channels: str, contact: str, support: str) -> str:
    return (
        f"👩‍🏫 <b>{title}</b>\n{_ROLES_HTML}\n\n"
        f"📢 <b>{channels}</b>\n"
        f"• <a href='{CHANNEL_ATTESTAT[1]}'>@{CHANNEL_ATTESTAT[0]}</a>\n"
        f"• <a href='{CHANNEL_DIRECTORS[1]}'>@{CHANNEL_DIRECTORS[0]}</a>\n\n"
        f"📩 <b>{contact}</b> <a href='{TEACHER_URL}'>{TEACHER_USERNAME}</a>\n"
        f"🛠 <b>{support}</b> {SUPPORT_USERNAME}"
    )


INFO_TEXTS_DMTT = {
    "uz": _info("HULKAR IBRAGIMOVA bilan birga", "Kanallarimiz:", "Murojaat:", "Texnik yordam:"),
    "ru": _info("Вместе с HULKAR IBRAGIMOVA", "Наши каналы:", "Связь:", "Техподдержка:"),
    "en": _info("Together with HULKAR IBRAGIMOVA", "Our channels:", "Contact:", "Support:"),
}