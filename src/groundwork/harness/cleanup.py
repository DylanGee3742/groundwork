"""Repair known extraction artifacts in document markdown.

PDF text extraction is lossy in characteristic, repeatable ways: page furniture
leaks into content, symbol-font bullets survive as meaningless glyphs, and
tables arrive in whichever markup the extractor found least lossy. Those repairs
live here rather than in :mod:`groundwork.harness.ingestion` so extraction and
cleaning stay independently testable, and so a caller can re-clean text that was
extracted elsewhere.

:func:`clean_markdown` is a pure string-to-string function and applies four
passes, in order:

1. **Repeating boilerplate removal.** Text that the extractor wrapped in
   ``<!-- Start of picture text -->`` markers and that recurs on at least
   ``min_boilerplate_repeats`` occasions is page furniture (a letterhead or logo
   block), so it is dropped.
2. **Heading repair.** When that same furniture leaks *out* of its wrapper it
   splices itself onto the following heading, corrupting the heading text and
   its level. The boilerplate learned in pass 1 is used to strip the leaked
   prefix, and the heading's level is restored from an uncorrupted occurrence of
   the same heading elsewhere in the document.
3. **Symbol-bullet normalization.** Word's second-level bullet is a Wingdings
   glyph that has no Unicode meaning; extractors surface it as a literal
   ``` `o` ```. Those become real nested markdown bullets.
4. **HTML table conversion.** ``<table>`` blocks become markdown pipe tables.

Nothing here is specific to any industry or client: the boilerplate is *learned*
from the document rather than hardcoded, so this stays usable from the harness.
Callers with furniture the extractor never wrapped can supply extra
``boilerplate_patterns`` explicitly.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence

__all__ = [
    "DEFAULT_MIN_BOILERPLATE_REPEATS",
    "SYMBOL_BULLET_GLYPHS",
    "clean_markdown",
    "flatten_table_cell",
    "rows_to_pipe_table",
]

#: A wrapped picture-text block recurring at least this often is page furniture.
DEFAULT_MIN_BOILERPLATE_REPEATS = 3

#: Glyphs that symbol fonts (Wingdings, Symbol) use for second-level bullets.
#: Extractors pass them through as literal characters, usually backtick-wrapped
#: because the source font is monospaced.
SYMBOL_BULLET_GLYPHS = "o§Øv·▪q"

#: Indent used for a normalized sub-bullet, matching what pymupdf4llm emits for
#: genuine nested lists so cleaned output stays internally consistent.
NESTED_BULLET_INDENT = "   "

_PICTURE_BLOCK = re.compile(
    r"[^\S\n]*<!--\s*Start of picture text\s*-->\s*"
    r"(?P<body>.*?)"
    r"<!--\s*End of picture text\s*-->[^\S\n]*",
    re.S,
)
_SYMBOL_BULLET = re.compile(
    rf"^(?P<indent>[ \t]*)(?:[-*+]\s+)?`[{re.escape(SYMBOL_BULLET_GLYPHS)}]`\s+(?P<content>\S.*?)\s*$"
)
_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<content>.*?)\s*$")
_TABLE = re.compile(r"<table[^>]*>(?P<body>.*?)</table>", re.S)
_ROW = re.compile(r"<tr[^>]*>(?P<body>.*?)</tr>", re.S)
_CELL = re.compile(r"<t[hd][^>]*>(?P<body>.*?)</t[hd]>", re.S)
_SPAN_ATTR = re.compile(r"\b(?:rowspan|colspan)\b", re.I)
_BR = re.compile(r"<br\s*/?>", re.I)
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_LEADING_NOISE = re.compile(r"^(?:~~[^~\n]*~~|<br\s*/?>|[\s_\-–—])+")
_MARKUP_CHARS = re.compile(r"[*_~`]")
_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_BLANK_RUN = re.compile(r"\n{3,}")
_TRAILING_SPACE = re.compile(r"[^\S\n]+$", re.M)

# A leaked boilerplate prefix is only stripped when there is corroborating
# evidence, so an ordinary heading that happens to open with the same word is
# left alone. Either the prefix is followed by extraction noise (strikethrough
# rules, stray <br>), or the remaining text matches a heading found elsewhere.
_SPLICE_NOISE = re.compile(r"^(?:~~[^~\n]*~~|<br\s*/?>)")

_MIN_BOILERPLATE_WORD_LENGTH = 3


def clean_markdown(
    markdown: str,
    *,
    boilerplate_patterns: Sequence[str | re.Pattern[str]] = (),
    min_boilerplate_repeats: int = DEFAULT_MIN_BOILERPLATE_REPEATS,
) -> str:
    """Repair extraction artifacts in ``markdown`` and return the cleaned text.

    Safe to run on already-clean markdown: every pass is targeted at a specific
    artifact and leaves unaffected text byte-identical apart from trailing
    whitespace and runs of blank lines, which are always normalized.

    Args:
        markdown: Extracted document markdown, typically from
            :func:`groundwork.harness.ingestion.extract_document`.
        boilerplate_patterns: Additional regexes for page furniture the
            extractor never wrapped in picture-text markers. Matches are removed
            outright, and their words join the vocabulary used for heading
            repair.
        min_boilerplate_repeats: How many times a wrapped picture-text block
            must recur before it is treated as furniture rather than content.
            Must be at least 2 — a block appearing once is not repeating.

    Returns:
        The cleaned markdown.

    Raises:
        ValueError: ``min_boilerplate_repeats`` is less than 2.
        re.error: A supplied ``boilerplate_patterns`` entry is not a valid regex.
    """
    if min_boilerplate_repeats < 2:
        raise ValueError(
            f"min_boilerplate_repeats must be at least 2, got {min_boilerplate_repeats}"
        )

    extra = [re.compile(p) if isinstance(p, str) else p for p in boilerplate_patterns]

    boilerplate, vocabulary = _learn_boilerplate(markdown, min_boilerplate_repeats)
    text = _strip_boilerplate_blocks(markdown, boilerplate)
    for pattern in extra:
        # Learn from what the caller's pattern actually matched, so explicitly
        # declared furniture can repair spliced headings too.
        vocabulary |= {word for hit in pattern.findall(text) for word in _words(str(hit))}
        text = pattern.sub("", text)

    text = _repair_spliced_headings(text, vocabulary)
    text = _normalize_symbol_bullets(text)
    text = _convert_html_tables(text)
    return _tidy_whitespace(text)


def _fingerprint(text: str) -> str:
    """Normalize text to lowercase alphanumerics for order-insensitive matching."""
    return _NON_ALNUM.sub("", _BR.sub(" ", text).lower())


def _learn_boilerplate(markdown: str, min_repeats: int) -> tuple[set[str], set[str]]:
    """Identify recurring picture-text furniture in ``markdown``.

    Returns the fingerprints of blocks that recur at least ``min_repeats`` times,
    alongside the vocabulary of words those blocks contain. The vocabulary is
    what makes heading repair possible without hardcoding any client's logo: the
    blocks that survived their wrapper teach us what the leaked one looked like.
    """
    bodies = [match.group("body") for match in _PICTURE_BLOCK.finditer(markdown)]
    counts = Counter(_fingerprint(body) for body in bodies)
    fingerprints = {
        fingerprint
        for fingerprint, count in counts.items()
        if fingerprint and count >= min_repeats
    }
    vocabulary = {
        word
        for body in bodies
        if _fingerprint(body) in fingerprints
        for word in _words(body)
    }
    return fingerprints, vocabulary


def _words(text: str) -> set[str]:
    """Extract candidate boilerplate words: alphabetic and long enough to be distinctive.

    Short tokens (``+``, ``&``, ``of``) are dropped — they occur everywhere in
    real headings, so matching on them would strip genuine content.
    """
    plain = _MARKUP_CHARS.sub("", _HTML_TAG.sub(" ", _BR.sub(" ", text)))
    return {
        token
        for token in re.split(r"[^0-9A-Za-z]+", plain)
        if len(token) >= _MIN_BOILERPLATE_WORD_LENGTH and token.isalpha()
    }


def _strip_boilerplate_blocks(markdown: str, boilerplate: set[str]) -> str:
    """Drop picture-text blocks whose content was identified as furniture.

    Picture text that does *not* repeat is left in place — a one-off diagram
    caption may carry real requirement content.
    """
    if not boilerplate:
        return markdown

    def replace(match: re.Match[str]) -> str:
        return "" if _fingerprint(match.group("body")) in boilerplate else match.group(0)

    return _PICTURE_BLOCK.sub(replace, markdown)


def _repair_spliced_headings(markdown: str, vocabulary: set[str]) -> str:
    """Strip leaked boilerplate from heading lines and restore the heading level."""
    if not vocabulary:
        return markdown

    lines = markdown.splitlines()

    # Levels are learned only from headings with no leaked prefix, so a corrupted
    # heading can never teach its own wrong level to its uncorrupted twin.
    clean_levels: dict[str, Counter[int]] = {}
    candidates: dict[int, tuple[int, str, str]] = {}
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match is None:
            continue
        content = match.group("content")
        level = len(match.group("hashes"))
        remainder, prefix = _strip_leading_vocabulary(content, vocabulary)
        if prefix and remainder:
            candidates[index] = (level, prefix, remainder)
        else:
            clean_levels.setdefault(_heading_key(content), Counter())[level] += 1

    for index, (level, prefix, remainder) in candidates.items():
        twin = clean_levels.get(_heading_key(remainder))
        # Require corroboration before rewriting: either the removed span carries
        # extraction noise (a strikethrough rule or stray <br> from the logo
        # artwork), or the surviving text matches an uncorrupted heading. Without
        # one of those, assume the word is genuine and leave the line alone.
        if _SPLICE_NOISE.search(prefix) is None and twin is None:
            continue
        restored = twin.most_common(1)[0][0] if twin is not None else level
        lines[index] = f"{'#' * restored} {remainder}"

    return "\n".join(lines) + ("\n" if markdown.endswith("\n") else "")


def _strip_leading_vocabulary(content: str, vocabulary: set[str]) -> tuple[str, str]:
    """Remove a run of leading boilerplate words from ``content``.

    Returns ``(remainder, removed_prefix)``; ``removed_prefix`` is empty when
    nothing matched. Words are only matched bare, so a heading opening with
    markdown emphasis (``**Enterprise …**``) is left untouched — emphasis means
    the extractor saw real styled text, not a spliced-in logo fragment.
    """
    pattern = re.compile(
        "|".join(re.escape(word) for word in sorted(vocabulary, key=len, reverse=True)),
        re.I,
    )
    remainder = content
    stripped = False
    while True:
        candidate = _LEADING_NOISE.sub("", remainder)
        match = pattern.match(candidate)
        # Reject partial-word hits so "Enterprise" never truncates "Enterprises".
        if match is None or (match.end() < len(candidate) and candidate[match.end()].isalnum()):
            break
        remainder = candidate[match.end() :]
        stripped = True
    if not stripped:
        return content, ""
    remainder = _LEADING_NOISE.sub("", remainder)
    return remainder, content[: len(content) - len(remainder)]


def _heading_key(content: str) -> str:
    """Normalize heading text so styled and unstyled variants compare equal."""
    without_tags = _HTML_TAG.sub("", content)
    return _NON_ALNUM.sub("", _MARKUP_CHARS.sub("", without_tags).lower())


def _normalize_symbol_bullets(markdown: str) -> str:
    """Turn literal symbol-font bullet glyphs into real nested markdown bullets."""

    def replace(match: re.Match[str]) -> str:
        indent = match.group("indent") or NESTED_BULLET_INDENT
        return f"{indent}- {match.group('content')}"

    return "\n".join(
        _SYMBOL_BULLET.sub(replace, line) for line in markdown.splitlines()
    ) + ("\n" if markdown.endswith("\n") else "")


def _convert_html_tables(markdown: str) -> str:
    """Rewrite ``<table>`` blocks as markdown pipe tables."""

    def replace(match: re.Match[str]) -> str:
        body = match.group("body")
        # Pipe tables cannot express merged cells; leaving the HTML intact loses
        # less information than flattening a spanned table into the wrong shape.
        if _SPAN_ATTR.search(match.group(0)):
            return match.group(0)
        rows = [
            [flatten_table_cell(cell) for cell in _CELL.findall(row)]
            for row in _ROW.findall(body)
        ]
        table = rows_to_pipe_table(rows)
        return table if table else match.group(0)

    return _TABLE.sub(replace, markdown)


def rows_to_pipe_table(rows: Sequence[Sequence[str]]) -> str:
    """Render rows of already-flattened cells as a markdown pipe table.

    The first row becomes the header, since pipe tables require one. Returns an
    empty string when every row is blank.
    """
    populated = [list(row) for row in rows if any(cell for cell in row)]
    if not populated:
        return ""

    width = max(len(row) for row in populated)
    padded = [row + [""] * (width - len(row)) for row in populated]

    header, *body = padded
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def flatten_table_cell(text: str) -> str:
    """Collapse cell content to a single line that cannot break a pipe table."""
    return " ".join(_BR.sub(" ", text).replace("|", r"\|").split())


def _tidy_whitespace(markdown: str) -> str:
    """Drop trailing spaces and collapse the blank-line runs left by removals."""
    return _BLANK_RUN.sub("\n\n", _TRAILING_SPACE.sub("", markdown)).strip() + "\n"
