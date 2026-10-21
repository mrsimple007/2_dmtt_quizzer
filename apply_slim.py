"""
Run from the project root:   python3 apply_slim.py
Removes startup memory you don't need (exact-text patches, safe to re-run):
  1. langchain_google_genai: imported at startup but never actually used -> import made lazy
  2. openpyxl (Excel reading): loaded only when someone sends an Excel file
  3. bs4 (web pages): loaded only when someone sends a link
  4. SIMPLEQUIZ_MESSAGE -> SIMPLEQUIZ_message: wrong upper/lower case in imports. Works on a Mac,
     CRASHES on a Linux server (broadcast feature).
"""
import pathlib, re, sys

problems = []


def edit(path, old, new, count=1, applied=None):
    p = pathlib.Path(path)
    if not p.exists():
        problems.append(f"{path}: file not found"); return
    s = p.read_text(encoding="utf-8")
    if applied and applied in s:
        print(f"  skip (already applied) {path}"); return
    n = s.count(old)
    if n != count:
        problems.append(f"{path}: expected {count} match(es), found {n} for {old[:60]!r}"); return
    p.write_text(s.replace(old, new), encoding="utf-8")
    print(f"  ok   {path}: {n} change(s)")


# 1. langchain -----------------------------------------------------------------
edit("src/imports.py", "from langchain_google_genai import ChatGoogleGenerativeAI\n", "",
     applied="# (langchain imported lazily)")
edit("src/imports.py",
     '    api_key, key_num = get_api_key_for_user(user_id=None)\n    \n    try:\n        os.environ["GOOGLE_API_KEY"] = api_key\n        llm = ChatGoogleGenerativeAI(',
     '    # (langchain imported lazily)\n    from langchain_google_genai import ChatGoogleGenerativeAI\n    api_key, key_num = get_api_key_for_user(user_id=None)\n    \n    try:\n        os.environ["GOOGLE_API_KEY"] = api_key\n        llm = ChatGoogleGenerativeAI(',
     applied="# (langchain imported lazily)\n    from langchain")
edit("src/imports.py",
     '    os.environ["GOOGLE_API_KEY"] = api_key\n    return ChatGoogleGenerativeAI(',
     '    os.environ["GOOGLE_API_KEY"] = api_key\n    from langchain_google_genai import ChatGoogleGenerativeAI\n    return ChatGoogleGenerativeAI(',
     applied="from langchain_google_genai import ChatGoogleGenerativeAI\n    return Chat")
_ip = pathlib.Path("src/image_processing.py")
if _ip.exists() and "from langchain_google_genai import ChatGoogleGenerativeAI\n" in _ip.read_text(encoding="utf-8"):
    _ip.write_text(_ip.read_text(encoding="utf-8").replace("from langchain_google_genai import ChatGoogleGenerativeAI\n", "", 1), encoding="utf-8")
    print("  ok   src/image_processing.py: unused import removed")
else:
    print("  skip (already applied) src/image_processing.py")

# 2. openpyxl ------------------------------------------------------------------
p = pathlib.Path("src/document_processing.py")
s = p.read_text(encoding="utf-8")
if "from openpyxl import load_workbook\n" in s.split("def ", 1)[0]:
    s = s.replace("from openpyxl import load_workbook\n", "", 1)
    # add a lazy import as the first line of every function that uses load_workbook
    def add_lazy(m):
        return m.group(0) + "    from openpyxl import load_workbook   # lazy: only when an Excel file arrives\n"
    s, n = re.subn(r"^(?:async )?def [^\n]*\n(?=(?:(?!^(?:async )?def ).)*?load_workbook\()", add_lazy, s, flags=re.M | re.S)
    p.write_text(s, encoding="utf-8")
    print(f"  ok   src/document_processing.py: openpyxl lazy in {n} function(s)")
else:
    print("  skip (already applied) src/document_processing.py")

# 3. bs4 -----------------------------------------------------------------------
p = pathlib.Path("src/web_processing.py")
s = p.read_text(encoding="utf-8")
if s.startswith("") and "from bs4 import BeautifulSoup\n" in s.split("def ", 1)[0]:
    s = s.replace("from bs4 import BeautifulSoup\n", "", 1)
    s, n = re.subn(r"^(\s*)soup = BeautifulSoup\(html, 'html.parser'\)",
                   r"\1from bs4 import BeautifulSoup   # lazy: only when a link is sent\n\1soup = BeautifulSoup(html, 'html.parser')",
                   s, flags=re.M)
    p.write_text(s, encoding="utf-8")
    print(f"  ok   src/web_processing.py: bs4 lazy ({n} place(s))")
else:
    print("  skip (already applied) src/web_processing.py")

# 4. filename case -------------------------------------------------------------
edit("auto_message_sender.py", "SIMPLEQUIZ_MESSAGE", "SIMPLEQUIZ_message", count=7,
     applied="from SIMPLEQUIZ_message import fetch_users, fetch_groups")

print()
if problems:
    print("PROBLEMS:\n" + "\n".join("  - " + x for x in problems)); sys.exit(1)
print("Done.")