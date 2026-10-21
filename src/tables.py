import re, pathlib


"""
Table names in ONE place (put this file at src/tables.py).

TABLE_SET=dmtt   -> Hulkar's DMTT bot uses the dmtt_* tables
(anything else)  -> your original bot keeps its original table names

So both bots run the SAME code; only the .env differs.
"""
import os

_DMTT = os.environ.get("TABLE_SET", "dmtt").strip().lower() == "dmtt"


class TBL:
    USERS = "dmtt_users" if _DMTT else "simplequizzer_users"
    QUIZZES = "dmtt_quizzes" if _DMTT else "quizzes_simplequiz"
    QUIZ_ATTEMPTS = "dmtt_quiz_attempts" if _DMTT else "quiz_attempts"
    GROUPS = "dmtt_groups" if _DMTT else "groups_simplequiz"
    FILES = "dmtt_files" if _DMTT else "simplequizzer_files"
    PAYMENT_HISTORY = "dmtt_payment_history" if _DMTT else "quiz_payments_history"
    PAYMENT_TOKENS = "dmtt_payment_tokens" if _DMTT else "payment_tokens"
    SUBSCRIPTION_HISTORY = "dmtt_subscription_history" if _DMTT else "subscription_history"
    ADMIN_SETTINGS = "dmtt_admin_settings" if _DMTT else "admin_settings"



MAP = {
    "simplequizzer_users": "USERS",
    "quizzes_simplequiz": "QUIZZES",
    "quiz_attempts": "QUIZ_ATTEMPTS",
    "groups_simplequiz": "GROUPS",
    "simplequizzer_files": "FILES",
    "quiz_payments_history": "PAYMENT_HISTORY",
    "payment_tokens": "PAYMENT_TOKENS",
    "subscription_history": "SUBSCRIPTION_HISTORY",
    "admin_settings": "ADMIN_SETTINGS",
}
PAT = re.compile(r"""\.table\(\s*(['"])(%s)\1\s*\)""" % "|".join(MAP))
IMPORT_LINE = "from src.tables import TBL\n"
SKIP = {".git", "__pycache__", "venv", ".venv", "node_modules"}
OWN = ("apply_dmtt_tables.py", "tables.py")

changed = {}
for path in pathlib.Path(".").rglob("*.py"):
    if SKIP & set(path.parts) or path.name in OWN:
        continue
    text = path.read_text(encoding="utf-8")
    new, n = PAT.subn(lambda m: f".table(TBL.{MAP[m.group(2)]})", text)
    if n == 0:
        continue
    if IMPORT_LINE not in new:
        lines = new.splitlines(keepends=True)
        for i, l in enumerate(lines):
            if re.match(r"(import |from )", l) and not l.startswith("from __future__"):
                lines.insert(i, IMPORT_LINE)
                break
        else:
            lines.insert(0, IMPORT_LINE)
        new = "".join(lines)
    path.write_text(new, encoding="utf-8")
    changed[str(path)] = n

for f, n in sorted(changed.items()):
    print(f"{n:3d} replaced in {f}")
print(f"TOTAL: {sum(changed.values())} in {len(changed)} files")