"""
quiz_splitter.py
================
Parser for attestation-style test files (MTT / DMTT).

Public API (kept compatible with handlers/quiz_split_handlers.py):

    QuizSplitter.parse_quiz_file(content, correct_marker='#') -> list[dict]
    QuizSplitter.get_split_options()                          -> list[int]
    QuizSplitter.calculate_batches(total, size)               -> (num_batches, last_batch_size)
    QuizSplitter.split_quizzes(quizzes, size)                 -> list[list[dict]]
    validate_quiz_structure(quiz)                             -> bool

Every parsed quiz is a dict:

    {
        "question": str,                 # full text (scenario / matching lists included)
        "options": [str, ...],           # option letters "A)" are STRIPPED -> shuffling is safe
        "correct_answer": int | None,    # index into options (None = answer not found)
        "allows_multiple_answers": False,
    }

Supported layouts (all can be mixed in one file):

  1. "N. Question?"  A) B) C) D)  + "✅ Javob: X"                       (DMTT best-answer)
  2. "Savol: ..." + concepts + "a) b) c) d)" + "A) 1-d, 2-c ..." + ✅    (matching)
  3. "N-SAVOL" / scenario / "Savol: ..." / A) B) C) D) / "To'g'ri javob: X"  (situational)
  4. "NN. Test type name" / stem / A) B) C) D) / "Javob: X"             (pasted 5-type format)
  5. Sequence tests: options like "2-3-4-1"
  6. "N-test" / "Savol:" / "Tushunchalar:" / "Mazmunlar:" / "Javob variantlari:"
     with the correct option marked by a leading arrow:  "► C) 1-b, 2-a, 3-c"

The correct answer is taken from either an answer line ("Javob: X",
"To'g'ri javob: X", with or without ✅) or from a marker (✅ ✔ ☑ ✓ ► ▶ ➤ ...) placed
in front of / behind the option itself.
"""

import logging
import math
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MAX_POLL_QUESTION = 300   # Telegram poll limits (informational, used for stats only)
MAX_POLL_OPTION = 100

# --------------------------------------------------------------------------- #
#  Character helpers
# --------------------------------------------------------------------------- #
_AP = "'’ʻʼ‘`´ʹ"                      # every apostrophe variant seen in Uzbek text
_MARKS = "✅✔✔️☑✓\ufe0f►▶▸➤➜➔"           # "correct" markers
_RE_MARKS = re.compile("[" + _MARKS + "]")
_RE_LEAD_MARK = re.compile("^[\\s" + _MARKS + "]+")      # markers standing in front of a line

# Cyrillic look-alikes that people type by accident in "А) В) С)"
_CYR = {"А": "A", "В": "B", "С": "C", "Е": "E", "а": "a", "с": "c", "е": "e"}


def _norm_letter(ch: str) -> str:
    return _CYR.get(ch, ch)


def _strip_marks(text: str) -> Tuple[str, bool]:
    found = bool(_RE_MARKS.search(text))
    return _RE_MARKS.sub("", text).strip(), found


# --------------------------------------------------------------------------- #
#  Regular expressions
# --------------------------------------------------------------------------- #
# "Javob: A", "✅ Javob: A", "To'g'ri javob: A", "To‘g‘ri javob – A"
_RE_ANS = re.compile(
    r"^\W*(?:to[" + _AP + r"]?g[" + _AP + r"]?ri\s+)?javob\s*[:：\-–—]\s*\(?\s*([A-Fa-fАВСЕасе])\b",
    re.IGNORECASE,
)

# Options use CAPITAL letters, matching items use lowercase.  "." is only accepted
# when followed by whitespace (protects "e.g." and initials).
_RE_OPT = re.compile(r"^\(?\s*([A-FАВСЕ])\s*([\)\]]|\.(?=\s))\s*(.*)$")
_RE_ITEM = re.compile(r"^\(?\s*([a-fасе])\s*([\)\]]|\.(?=\s))\s*(.*)$")

_RE_SAVOL = re.compile(r"^\s*savol\s*\d*\s*[:：]\s*(.*)$", re.IGNORECASE)
_RE_NSAVOL = re.compile(r"^\s*(\d{1,4})\s*[-–.]?\s*savol\s*[:.]?\s*$", re.IGNORECASE)      # "31-SAVOL"
_RE_NTEST = re.compile(r"^\s*(\d{1,4})\s*[-–]\s*test\s*$", re.IGNORECASE)                  # "13-test" (noise)
_RE_TYPE_HDR = re.compile(                                                                 # "12. Murakkab moslashtirish testi"
    r"^\s*(\d{1,4})\s*[\.\)]\s*([^?:]{3,70}?\btest(?:i)?)\s*$", re.IGNORECASE)
_RE_NUMQ = re.compile(r"^\s*(\d{1,4})\s*[\.\)]\s+(\S.*)$")                                 # "7. Question?"
_RE_LABEL = re.compile(r"^[^\W\d][^:]{1,38}:$")                                            # "Mazmunlar:"
_RE_GLUED_LABEL = re.compile(
    r"\s+(tu[sh]?h?unchalar|kompetensiyalar|tamoyillar|bosqichlar|jarayonlar|atamalar)\s*:\s*$",
    re.IGNORECASE)

_RE_PAIRS_NOISE = re.compile(r"^(?:\d\s*[-–—]\s*[a-fA-F]\s*[,;]?\s*){3,}$")                # stray "1-d, 2-a, 3-b, 4-c"
_RE_MATCH_OPT = re.compile(r"^\d\s*[-–—]\s*[a-fA-F](?:\s*[,;]?\s*\d\s*[-–—]\s*[a-fA-F])+$")  # option of a matching test
_RE_SEQ_OPT = re.compile(r"^\d(?:\s*[-–—→>,;]\s*\d){2,}$")                                 # option of a sequence test "2–3–4–1"
_RE_VARIANTS = re.compile(r"^javob\s+variantlari\s*:?$|^variantlar\s*:?$", re.IGNORECASE)
_RE_PATH = re.compile(r"(/Users/|Library/Containers|^\S+\.docx?$)", re.IGNORECASE)
_RE_FILLER = re.compile(r"^[-=+_*~#.\s]{3,}$")

_KNOWN_LABELS = {
    "tushunchalar", "tuhunchalar", "mazmunlar", "tavsiflar", "natijalar", "kompetensiyalar",
    "tamoyillar", "bosqichlar", "jarayonlar", "atamalar", "mazmuni", "xususiyatlar",
}
_RE_LIST_INTRO = re.compile(r"moslashtir|joylashtir|tartib|ketma-ket", re.IGNORECASE)


# --------------------------------------------------------------------------- #
#  Internal block (one question while it is being collected)
# --------------------------------------------------------------------------- #
class _Block:
    __slots__ = ("parts", "items", "options", "correct", "ans_letter",
                 "closed", "num", "last_listed")

    def __init__(self, num: Optional[int] = None):
        self.parts: List[Tuple[str, str]] = []   # (kind, text): text | savol | list | label
        self.items: List[str] = []               # lowercase a) b) c) d) items (matching tests)
        self.options: List[str] = []             # A) B) C) D) option texts
        self.correct: Optional[int] = None       # from a marker on an option
        self.ans_letter: Optional[str] = None    # from "Javob: X"
        self.closed = False                      # answer line already consumed
        self.num = num
        self.last_listed: Optional[int] = None   # last typed "1. 2. 3." concept number


# --------------------------------------------------------------------------- #
#  QuizSplitter
# --------------------------------------------------------------------------- #
class QuizSplitter:
    last_warnings: List[str] = []
    last_stats: Dict[str, int] = {}

    # ------------------------------ public API ------------------------------ #
    @classmethod
    def parse_quiz_file(cls, content: str, correct_marker: str = "#") -> List[Dict]:
        cls.last_warnings = []
        cls.last_stats = {"questions": 0, "long_questions": 0, "long_options": 0, "no_answer": 0}
        try:
            return cls._parse(content or "", correct_marker or "")
        except Exception as e:  # never crash the bot because of a weird file
            logger.error(f"[QuizSplitter] parse failed: {e}", exc_info=True)
            return []

    @staticmethod
    def get_split_options() -> List[int]:
        return [10, 20, 25, 30, 40, 50, 100]

    @staticmethod
    def calculate_batches(total: int, size: int) -> Tuple[int, int]:
        if total <= 0:
            return 0, 0
        if size <= 0 or size > total:
            size = total
        num = math.ceil(total / size)
        last = total - (num - 1) * size
        return num, last

    @staticmethod
    def split_quizzes(quizzes: List[Dict], size: int) -> List[List[Dict]]:
        """Consecutive chunks - the original order is kept (important for learning)."""
        if not quizzes:
            return []
        if size <= 0 or size > len(quizzes):
            size = len(quizzes)
        return [quizzes[i:i + size] for i in range(0, len(quizzes), size)]

    # ------------------------------ parsing core ---------------------------- #
    @classmethod
    def _parse(cls, content: str, marker: str) -> List[Dict]:
        text = content.replace("\r\n", "\n").replace("\r", "\n")
        quizzes: List[Dict] = []
        cur: Optional[_Block] = None

        def flush():
            nonlocal cur
            if cur is not None:
                q = cls._build(cur, len(quizzes) + 1)
                if q:
                    quizzes.append(q)
            cur = None

        def start(num: Optional[int] = None) -> _Block:
            nonlocal cur
            flush()
            cur = _Block(num)
            return cur

        for raw in text.split("\n"):
            ln = cls._clean(raw)
            if not ln:
                continue

            # 1) answer line ------------------------------------------------
            m = _RE_ANS.match(ln)
            if m:
                if cur is not None and cur.options:
                    cur.ans_letter = _norm_letter(m.group(1)).upper()
                    cur.closed = True
                continue

            # 1b) marker in FRONT of an option:  "► C) ...", "✅ B) ..."  --------
            lead_marked = False
            lm = _RE_LEAD_MARK.match(ln)
            if lm and lm.end() > 0 and _RE_MARKS.search(lm.group(0)):
                rest = ln[lm.end():]
                if _RE_OPT.match(rest):
                    ln, lead_marked = rest, True

            # 2) block headers ("31-SAVOL", "12. Murakkab ... testi") ---------
            m = _RE_NSAVOL.match(ln)
            if m:
                start(int(m.group(1)))
                continue
            m = _RE_TYPE_HDR.match(ln)
            if m:
                start(int(m.group(1)))
                continue

            # 3) option  A) B) C) D) ------------------------------------------
            m = _RE_OPT.match(ln)
            if m:
                letter = _norm_letter(m.group(1))
                sep = m.group(2)
                n_opts = len(cur.options) if cur is not None else 0
                expected = chr(65 + n_opts)
                accept = False
                if letter == expected and (sep != "." or n_opts > 0):
                    accept = True
                    if cur is None:
                        cur = _Block()
                elif letter == "A" and n_opts > 0 and sep != ".":
                    start()                       # options of a new, stem-less question
                    accept = True
                if accept:
                    body, has_mark = _strip_marks(m.group(3))
                    has_mark = has_mark or lead_marked
                    if marker and body.startswith(marker):
                        body, has_mark = body[len(marker):].strip(), True
                    cur.options.append(body)
                    if has_mark:
                        cur.correct = len(cur.options) - 1
                    continue
                # else: not a real option -> falls through as plain text

            # 4) "Savol: ..." ---------------------------------------------------
            m = _RE_SAVOL.match(ln)
            if m:
                body = m.group(1).strip()
                if (cur is None or cur.options or cur.items
                        or any(k == "savol" for k, _ in cur.parts)):
                    start()
                glued = _RE_GLUED_LABEL.search(body)
                if glued:
                    label = glued.group(1)
                    body = body[:glued.start()].rstrip()
                    if body:
                        cur.parts.append(("savol", body))
                    cur.parts.append(("label", label))
                else:
                    cur.parts.append(("savol", body))
                continue

            # 5) lowercase matching item  a) b) c) d) --------------------------
            m = _RE_ITEM.match(ln)
            if m and cur is not None and not cur.options:
                letter = _norm_letter(m.group(1))
                sep = m.group(2)
                if letter == chr(97 + len(cur.items)) and (sep != "." or cur.items):
                    cur.items.append(_strip_marks(m.group(3))[0])
                    continue

            # 6) numbered line "7. ..."  (new question OR typed concept list) --
            m = _RE_NUMQ.match(ln)
            if m:
                num, body = int(m.group(1)), _strip_marks(m.group(2))[0]
                if cur is None or cur.options or cur.items or not cls._is_listed(cur, num):
                    blk = start(num)
                    blk.parts.append(("text", body))
                else:
                    cur.parts.append(("list", body))
                    cur.last_listed = num
                continue

            # 7) label line ("Mazmunlar:", "Tushunchalar:") ---------------------
            if _RE_LABEL.match(ln):
                if cur is None:
                    start()
                if not cur.options and not cur.items:
                    cur.parts.append(("label", ln[:-1].strip()))
                continue

            # 8) plain text ------------------------------------------------------
            if cur is None:
                start().parts.append(("text", _strip_marks(ln)[0]))
                continue
            if cur.options:
                if cur.closed or (cur.correct is not None and len(cur.options) >= 4):
                    start().parts.append(("text", _strip_marks(ln)[0]))   # next question, no header
                else:                                                    # wrapped option text
                    body, has_mark = _strip_marks(ln)
                    cur.options[-1] = (cur.options[-1] + " " + body).strip()
                    if has_mark:
                        cur.correct = len(cur.options) - 1
                continue
            if cur.items:                                                # wrapped item text
                cur.items[-1] = (cur.items[-1] + " " + _strip_marks(ln)[0]).strip()
                continue
            cur.parts.append(("text", _strip_marks(ln)[0]))

        flush()
        cls.last_stats["questions"] = len(quizzes)
        return quizzes

    # ------------------------------ helpers --------------------------------- #
    @staticmethod
    def _clean(raw: str) -> Optional[str]:
        """Return a cleaned line, or None for empty / noise lines."""
        ln = raw.replace("\u00a0", " ").replace("\u200b", "").replace("\t", " ").strip()
        if not ln:
            return None
        if ln.startswith(">"):                                  # pasted Telegram quote: "> IHulkar:"
            ln = ln.lstrip("> ").strip()
            if not ln:
                return None
            if re.fullmatch(r"[\w .@]{1,32}:", ln) and ln[:-1].strip().lower() not in _KNOWN_LABELS:
                return None
        if _RE_PATH.search(ln):
            return None
        if (_RE_NTEST.match(ln) or _RE_PAIRS_NOISE.match(ln) or _RE_SEQ_OPT.match(ln)
                or _RE_FILLER.match(ln) or _RE_VARIANTS.match(ln)):
            return None
        return re.sub(r"[ ]{2,}", " ", ln)

    @staticmethod
    def _is_listed(cur: _Block, num: int) -> bool:
        """Is this numbered line a typed concept (1. 2. 3.) of the current stem?"""
        if not cur.parts:
            return False
        kind, text = cur.parts[-1]
        if kind == "label":
            return True
        if kind == "list" and cur.last_listed is not None and num == cur.last_listed + 1:
            return True
        if kind in ("text", "savol") and (text.endswith(":") or _RE_LIST_INTRO.search(text)):
            return True
        return False

    # ------------------------------ building -------------------------------- #
    @classmethod
    def _build(cls, blk: _Block, idx: int) -> Optional[Dict]:
        opts = [o.strip() for o in blk.options]
        has_savol = any(k == "savol" for k, _ in blk.parts)

        if len(opts) < 2:
            if has_savol or blk.num is not None or blk.items:
                cls.last_warnings.append(f"#{idx}: skipped, fewer than 2 options")
            return None

        # ---- correct answer ----
        correct = blk.correct
        if blk.ans_letter:
            from_line = ord(blk.ans_letter) - 65
            if correct is not None and correct != from_line:
                cls.last_warnings.append(
                    f"#{idx}: marker on option {chr(65 + correct)} but answer line says {blk.ans_letter} (answer line used)")
            correct = from_line
        if correct is None or not (0 <= correct < len(opts)):
            cls.last_warnings.append(f"#{idx}: correct answer not found")
            cls.last_stats["no_answer"] += 1
            correct = None

        # Telegram needs unique poll options.  Some files repeat the correct option under
        # two letters ("C) 1-c, 2-a, 3-b" and "► D) 1-c, 2-a, 3-b") -> merge identical options
        # and keep the marked one, so the answer stays unambiguous.
        keep: List[int] = []
        pos: Dict[str, int] = {}
        for i, o in enumerate(opts):
            key = re.sub(r"\s+", " ", o).casefold()
            if key in pos:
                if i == correct:
                    keep[pos[key]] = i
                continue
            pos[key] = len(keep)
            keep.append(i)
        if len(keep) != len(opts):
            cls.last_warnings.append(f"#{idx}: {len(opts) - len(keep)} duplicate option(s) merged")
            cls.last_stats["duplicate_options"] = cls.last_stats.get("duplicate_options", 0) + 1
            correct = keep.index(correct) if correct in keep else None
            opts = [opts[i] for i in keep]
            if len(opts) < 2:
                return None

        question = cls._compose_question(blk, opts)
        if not question:
            cls.last_warnings.append(f"#{idx}: empty question text")
            return None

        if len(question) > MAX_POLL_QUESTION:
            cls.last_stats["long_questions"] += 1
        for o in opts:
            if len(o) > MAX_POLL_OPTION:
                cls.last_stats["long_options"] += 1
                cls.last_warnings.append(f"#{idx}: option longer than {MAX_POLL_OPTION} chars ({len(o)})")
                break

        return {
            "question": question,
            "options": opts,
            "correct_answer": correct,
            "allows_multiple_answers": False,
        }

    @classmethod
    def _compose_question(cls, blk: _Block, opts: List[str]) -> str:
        is_match = all(_RE_MATCH_OPT.match(o) for o in opts)
        is_seq = (not is_match) and all(_RE_SEQ_OPT.match(o) for o in opts)

        if is_match:
            k = len(re.findall(r"\d\s*[-–—]\s*[a-fA-F]", opts[0]))
        elif is_seq:
            k = len(re.findall(r"\d", opts[0]))
        else:
            k = len(blk.items)

        if not (is_match or is_seq or blk.items):
            return cls._compose_plain(blk)

        # ---------- list-type question: sentence + numbered concepts (+ a) b) c) d) items) ----------
        parts = blk.parts
        mz_label = None
        label_entries = [(i, t) for i, (kd, t) in enumerate(parts) if kd == "label"]
        if blk.items and parts and parts[-1][0] == "label":
            mz_label = parts[-1][1]
            label_entries = label_entries[:-1]
        concept_label = label_entries[0][1] if label_entries else None

        content = [(kd, t) for kd, t in parts if kd != "label"]
        cand = [i for i, (kd, _) in enumerate(content) if kd in ("text", "list")]
        concept_idx = cand[-k:] if (k and len(cand) >= k) else cand
        concepts = [content[i][1] for i in concept_idx]
        sentence = " ".join(t for i, (kd, t) in enumerate(content) if i not in concept_idx).strip()

        sections: List[str] = []
        if sentence:
            sections.append(sentence)

        if concepts:
            lines = []
            label = concept_label or ("Tushunchalar" if is_match or blk.items else None)
            if label:
                label = re.sub(r"(?i)^tuhunchalar$", "Tushunchalar", label)
                lines.append(f"{label}:")
            lines += [f"{n}. {c}" for n, c in enumerate(concepts, 1)]
            sections.append("\n".join(lines))

        if blk.items:
            lines = [f"{mz_label or 'Mazmunlar'}:"]
            lines += [f"{chr(97 + n)}) {t}" for n, t in enumerate(blk.items)]
            sections.append("\n".join(lines))

        return "\n\n".join(sections).strip()

    @staticmethod
    def _compose_plain(blk: _Block) -> str:
        before: List[str] = []
        savol: Optional[str] = None
        after: List[str] = []
        for kd, t in blk.parts:
            if kd == "label":
                continue
            if kd == "savol" and savol is None:
                savol = t
            elif savol is None:
                before.append(t)
            else:
                after.append(t)
        scenario = " ".join(before).strip()
        if savol is None:
            return scenario
        question = " ".join([savol] + after).strip()
        if scenario and question:
            return f"{scenario}\n\n{question}"
        return scenario or question


# --------------------------------------------------------------------------- #
#  Validation (imported by quiz_split_handlers)
# --------------------------------------------------------------------------- #
def validate_quiz_structure(quiz: Dict) -> bool:
    """True when the quiz has a question, >= 2 options and a valid correct answer."""
    try:
        if not quiz or len((quiz.get("question") or "").strip()) < 3:
            return False
        opts = [o for o in (quiz.get("options") or []) if o and o.strip()]
        if len(opts) < 2:
            return False
        if quiz.get("allows_multiple_answers"):
            ca = quiz.get("correct_answers") or []
            return bool(ca) and all(isinstance(i, int) and 0 <= i < len(opts) for i in ca)
        ca = quiz.get("correct_answer")
        return isinstance(ca, int) and 0 <= ca < len(opts)
    except Exception:
        return False