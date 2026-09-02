"""
Reading of the free-text description of a routine as titled sections.

A routine description written by hand tends to arrive as prose with real structure in it —
a heading line in capitals, then indented body lines — and rendering it as a single paragraph
throws that structure away. This module reads the shape back out so the template can typeset
it, without asking the person to fill in extra fields or migrating the text into new columns.

Nothing here is required: text with no discernible structure comes back as plain paragraphs,
which is exactly how it used to render.
"""

import re

UPPER = 'A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ'

# The capitalized run that opens a heading line: 'FREQUÊNCIA', 'REGRA DAS 24H',
# 'SEGURANÇA'. Whatever follows it — a dash subtitle, a parenthetical — is the subtitle.
HEADING_RE = re.compile(r'^([{u}][{u}0-9\s\'/-]*[{u}0-9])(.*)$'.format(u=UPPER))


def _split_heading(line):
    """
    Return ``(title, subtitle)`` when the line opens a section, else ``(None, None)``.

    A heading starts at column zero and opens with a run of capitals carrying at least three
    letters, so an ordinary sentence beginning with a name is not mistaken for one.
    """
    if not line or line[:1].isspace():
        return None, None
    match = HEADING_RE.match(line.strip())
    if not match:
        return None, None

    title = match.group(1).strip()
    if len([c for c in title if c.isalpha()]) < 3:
        return None, None

    subtitle = match.group(2).strip()
    subtitle = re.sub(r'^[\s—–:-]+', '', subtitle).strip()
    subtitle = subtitle.rstrip('.') or None
    return title.rstrip('.:'), subtitle


def parse_sections(text):
    """
    Split ``text`` into blocks the template can render.

    Returns a list of dicts ``{'title', 'subtitle', 'body'}``, where ``body`` is a list of
    paragraphs and ``title`` is ``None`` for the untitled opening and closing prose. Blank
    lines separate blocks.
    """
    if not text:
        return []

    sections = []
    for raw_block in re.split(r'\n\s*\n', text.strip()):
        lines = [line.rstrip() for line in raw_block.split('\n') if line.strip()]
        if not lines:
            continue

        title, subtitle = _split_heading(lines[0])
        if title:
            lines.pop(0)

        body = _join_wrapped(lines)
        if title or body:
            sections.append({'title': title, 'subtitle': subtitle, 'body': body})
    return sections


# How much shorter than the widest line a line may be and still count as "full". The text is
# hard-wrapped at a fixed column, so a line that stops well before it stopped on purpose.
WRAP_SLACK = 12


def _join_wrapped(lines):
    """
    Rejoin hard-wrapped lines into paragraphs.

    The text is wrapped by hand at a fixed column, so a line break means one of two things:
    the sentence ran out of room, or a new item started. Only a line that reached the wrap
    margin can be continued by the next one — a line that stopped early ended on purpose,
    which is what separates 'Semana ímpar … Semana par' from a sentence merely spilling over.
    """
    if not lines:
        return []

    margin = max(len(line.strip()) for line in lines)
    paragraphs, current = [], []
    for raw in lines:
        stripped = raw.strip()
        if current and not _continues(current[-1], margin):
            paragraphs.append(' '.join(current))
            current = []
        current.append(stripped)
    if current:
        paragraphs.append(' '.join(current))
    return paragraphs


def _continues(previous, margin):
    """True when ``previous`` was cut by the wrap margin rather than ended by its author."""
    if previous.endswith(('.', '!', '?', ':')):
        return False
    return len(previous) >= margin - WRAP_SLACK
