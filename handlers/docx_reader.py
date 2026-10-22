"""
docx_reader.py - read a .docx the way a human sees it.

Why this exists
---------------
The old code did   "all paragraphs first, then all tables".   That destroys the order of
a document that has tables in the middle (a table-based matching question ended up at the
very bottom of the text).  It also read vertically merged table cells several times.

extract_docx_text(path) walks the document body in its real order, keeps line breaks
inside a paragraph (e.g. "Mazmunlar:\na) ...\nb) ..."), reads every table cell once, and
splits question numbers that were glued to the previous line ("...salohiyatiga.16. Qaror").
"""
import re
from typing import List

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

_GLUED_NUM = re.compile(r"(?<=[A-Za-z\.\?!:;])(\d{1,3}\.\s+(?=[A-ZА-Я“\"‘']))")
_SKIP_CELLS = {"====", "++++", "----", "===", "+++", "---"}


def _split_glued(line: str) -> List[str]:
    """'...text.16. Next question' -> ['...text.', '16. Next question']"""
    out, last = [], 0
    for m in _GLUED_NUM.finditer(line):
        if m.start() == 0:
            continue
        out.append(line[last:m.start()])
        last = m.start()
    out.append(line[last:])
    return [x.strip() for x in out if x.strip()]


def _table_lines(table: Table) -> List[str]:
    lines: List[str] = []
    seen = set()                                   # merged cells appear in several rows
    for row in table.rows:
        for cell in row.cells:
            if cell._tc in seen:
                continue
            seen.add(cell._tc)
            for part in cell.text.replace("\r", "\n").split("\n"):
                part = part.strip()
                if part and part not in _SKIP_CELLS:
                    lines.append(part)
    return lines


def extract_docx_text(path: str) -> str:
    doc = Document(path)
    lines: List[str] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = Paragraph(child, doc).text
            for raw in text.replace("\r", "\n").split("\n"):
                raw = raw.strip()
                if raw:
                    lines.extend(_split_glued(raw))
        elif tag == "tbl":
            lines.extend(_table_lines(Table(child, doc)))
    return "\n".join(lines)