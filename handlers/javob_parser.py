"""
Tolerant parser for quiz files written like:

    1-savol
    Question text
    A: option
    B: option
    C: option
    D: option
    Javob: D

It also copes with the messy variations found in real files:
  * headers as "12-savol", "48. Question...", "50.Question..."
  * options as "A: x", "A) x", "A. x", "A:x", "D :x", ": C: x"
  * answers as "Javob: B", ": Javob: D", "Javob - B", Cyrillic "А"/"В"/"С"
  * missing blank lines between questions
  * multi-line questions (soft line breaks inside one paragraph)
  * several correct letters ("Javob: A, C") -> multiple-answer question

Returns dicts in the same shape QuizSplitter produces:
  {'question', 'options', 'correct_answer', 'allows_multiple_answers'}
  or, for several correct answers, 'correct_answers' (list of indices).
"""
import re
import logging

logger = logging.getLogger(__name__)

# Cyrillic look-alikes that people type by accident
_CYR_TO_LAT = str.maketrans({
    "А": "A", "В": "B", "С": "C", "Е": "E",
    "а": "a", "в": "b", "с": "c", "е": "e",
})

_LETTERS = "A-Fa-fАВСЕавсе"

# Marker for a soft line break INSIDE one Word paragraph (Shift+Enter). The extractor replaces
# "\n" inside a paragraph with this so the parser can keep matching-type questions
# ("1. ... 2. ... A. ... B. ...") together instead of mistaking "A." for an answer option.
SOFT_BREAK = "\u0001"

# "Javob: D", ": Javob: D", "Javob - D", "Javob D", "Javob: A, C"
_ANSWER_RE = re.compile(
    rf"^\s*[:\-–.]*\s*(?:javob|ответ|answer)\s*[:\-–=]?\s*([{_LETTERS}][{_LETTERS}\s,;&/]*)\s*$",
    re.IGNORECASE,
)

# "A: text", "A) text", "A. text", "A :text", ": C: text"
_OPTION_RE = re.compile(
    rf"^\s*[:\-–]?\s*([{_LETTERS}])\s*[:.)]\s*(.*)$",
    re.DOTALL,
)

# "12-savol", "12-savol." or "12. text", "12) text", "12.text"
_HEADER_SAVOL_RE = re.compile(r"^\s*(\d{1,4})\s*-\s*savol\s*[.:]?\s*(.*)$", re.IGNORECASE | re.DOTALL)
_HEADER_NUM_RE = re.compile(r"^\s*(\d{1,4})\s*[.)]\s*(\S.*)$", re.DOTALL)


def _letter(ch: str) -> str:
    return ch.translate(_CYR_TO_LAT).upper()


def _finalize(cur, out, skipped):
    if cur is None:
        return
    question = "\n".join(cur["q"]).strip()
    options = [o.strip() for o in cur["opts"]]
    letters = cur["letters"]
    ans = cur["ans"]

    if not (question and len(options) >= 2 and ans):
        skipped.append(cur["num"])
        return

    idx = []
    for a in ans:
        if a in letters:
            idx.append(letters.index(a))
    idx = sorted(set(idx))
    if not idx:
        skipped.append(cur["num"])
        return

    if len(idx) == 1:
        out.append({
            "question": question,
            "options": options,
            "correct_answer": idx[0],
            "allows_multiple_answers": False,
        })
    else:
        out.append({
            "question": question,
            "options": options,
            "correct_answers": idx,
            "allows_multiple_answers": True,
        })


def parse_javob_format(content: str):
    """Parse text in the 'N-savol / A: / Javob:' style. Returns a list of quiz dicts."""
    out, skipped = [], []
    cur = None
    state = "idle"          # idle | question | options | done

    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        has_soft = SOFT_BREAK in line
        text_line = line.replace(SOFT_BREAK, "\n")

        # 1) answer line closes the current question
        m = _ANSWER_RE.match(line)
        if m and cur is not None and cur["opts"]:
            cur["ans"] = [_letter(c) for c in re.findall(rf"[{_LETTERS}]", m.group(1))]
            _finalize(cur, out, skipped)
            cur, state = None, "idle"
            continue

        # 2) new question header
        h = _HEADER_SAVOL_RE.match(line)
        h2 = None if h else _HEADER_NUM_RE.match(line)
        # a "1. text" line is only a header when we are not inside the options of a question
        if h or (h2 and state in ("idle", "done")):
            if cur is not None:
                _finalize(cur, out, skipped)      # previous one had no answer line
            hm = h or h2
            cur = {"num": hm.group(1), "q": [], "opts": [], "letters": [], "ans": None}
            first = hm.group(2).replace(SOFT_BREAK, "\n").strip()
            if first:
                cur["q"].append(first)
            state = "question"
            continue

        if cur is None:
            continue

        # 3) option line (only a real option if it is a single leading letter)
        om = _OPTION_RE.match(line)
        if om and not has_soft:
            cur["letters"].append(_letter(om.group(1)))
            cur["opts"].append(om.group(2).strip())
            state = "options"
            continue

        # 4) everything else: question text, or continuation of the last option
        if state == "options" and cur["opts"]:
            cur["opts"][-1] += " " + text_line.replace("\n", " ")
        else:
            cur["q"].append(text_line)
            state = "question"

    if cur is not None:
        _finalize(cur, out, skipped)

    if skipped:
        logger.warning(f"[SPLIT] javob-parser skipped incomplete questions: {skipped}")
    logger.info(f"[SPLIT] javob-parser found {len(out)} questions")
    return out


def parse_best(content: str, correct_marker: str = "#"):
    """Run the javob parser and the original QuizSplitter; keep whichever finds more."""
    mine = parse_javob_format(content)
    try:
        from handlers.quiz_splitter import QuizSplitter
        theirs = QuizSplitter.parse_quiz_file(content, correct_marker) or []
    except Exception as e:
        logger.error(f"[SPLIT] QuizSplitter failed: {e}")
        theirs = []
    logger.info(f"[SPLIT] parsers: javob={len(mine)} quiz_splitter={len(theirs)}")
    return mine if len(mine) >= len(theirs) else theirs