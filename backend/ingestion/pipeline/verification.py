"""Deterministic checks that keep invented content out of the database.

This module is the main guarantee of contract §0.1: every claim must carry a
literal quote that is found inside the stored document text, and an event date
is only accepted when its own quote is in the text *and* states that day and
month. The language model can propose; only these functions decide.

Matching is tolerant to presentation differences only: Unicode NFKC, typographic
quotes and apostrophes, dashes, soft hyphens and zero-width characters, any
decimal digit system, letter case and whitespace. It never tolerates changed,
added or omitted words (an internal ellipsis therefore fails).
"""
import re
import unicodedata
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlsplit

DOUBLE_QUOTES = '"“”„‟″«»‹›「」『』＂'
SINGLE_QUOTES = "'‘’‚‛′`´＇"
DASHES = '‐‑‒–—―−﹘﹣－'
INVISIBLE = '­​‌‍⁠﻿'

_TRANSLATION = {ord(char): '"' for char in DOUBLE_QUOTES}
_TRANSLATION.update({ord(char): "'" for char in SINGLE_QUOTES})
_TRANSLATION.update({ord(char): '-' for char in DASHES})
_TRANSLATION.update({ord(char): None for char in INVISIBLE})
_WHITESPACE = re.compile(r'\s+')

# Minimum size of a claim quote: avoids "verifying" a claim with a trivial
# fragment such as a single name. Maximum size: public excerpts stay brief
# (copyright of the downloaded content; see PIPELINE_AGENTES.md).
QUOTE_MIN_CHARS = 20
QUOTE_MIN_WORDS = 4
QUOTE_MAX_CHARS = 600
DATE_QUOTE_MIN_CHARS = 4
DATE_QUOTE_MAX_CHARS = 200
MIN_EVENT_YEAR = 1900


def _digit(char):
    value = unicodedata.decimal(char, None)
    return str(value) if value is not None and not char.isascii() else char


def _normalize_char(char):
    value = unicodedata.normalize('NFKC', char).translate(_TRANSLATION)
    return ''.join(_digit(item) for item in value).casefold()


def _normalize_with_map(value):
    """Normalized text plus, for each output character, its index in ``value`` (already NFC)."""
    output, positions = [], []
    pending_space = False
    for index, char in enumerate(value):
        if char.isspace():
            pending_space = bool(output)
            continue
        piece = _normalize_char(char)
        if not piece:
            continue
        for item in piece:
            if item.isspace():
                pending_space = bool(output)
                continue
            if pending_space:
                output.append(' ')
                positions.append(index)
                pending_space = False
            output.append(item)
            positions.append(index)
    return ''.join(output), positions


def normalize_text(value):
    """Canonical form used for literal matching (see module docstring)."""
    if not value:
        return ''
    return _normalize_with_map(unicodedata.normalize('NFC', value))[0]


def clean_quote(value):
    """Normalized quote without surrounding quote marks or leading/trailing ellipses."""
    text = normalize_text(value)
    previous = None
    while text != previous:
        previous = text
        text = text.strip(' "\'')
        for ellipsis in ('...', '[...]', '(...)'):
            if text.startswith(ellipsis):
                text = text[len(ellipsis):]
            if text.endswith(ellipsis):
                text = text[:-len(ellipsis)]
    return text.strip()


@dataclass
class QuoteCheck:
    ok: bool
    reason: str = ''
    excerpt: str = ''  # exact substring of the (NFC) stored text that matched
    first_paragraph: int | None = None  # 1-based, counting non-empty lines
    last_paragraph: int | None = None

    @property
    def locator(self):
        if self.first_paragraph is None:
            return 'Cita literal del texto descargado'
        if self.first_paragraph == self.last_paragraph:
            return f'Cita literal, párrafo {self.first_paragraph}'
        return f'Cita literal, párrafos {self.first_paragraph}–{self.last_paragraph}'


class NormalizedDocument:
    """Stored document text, normalized once for repeated lookups.

    ``text`` is kept in NFC (the fetcher already stores NFC text) so that the
    matched span can be returned as an exact excerpt of the stored text.
    """

    def __init__(self, text):
        self.text = unicodedata.normalize('NFC', text or '')
        self.normalized, self._positions = _normalize_with_map(self.text)
        self._line_starts = []
        offset = 0
        for line in self.text.split('\n'):
            if line.strip():
                self._line_starts.append(offset)
            offset += len(line) + 1

    def contains(self, fragment, min_chars=2):
        """Whole-word presence of ``fragment`` (names of actors and places)."""
        needle = clean_quote(fragment) if isinstance(fragment, str) else ''
        if len(needle) < min_chars:
            return False
        return re.search(r'(?<!\w)' + re.escape(needle) + r'(?!\w)', self.normalized) is not None

    def _paragraph(self, index):
        return bisect_right(self._line_starts, index) or None

    def check_quote(self, quote, *, min_chars=QUOTE_MIN_CHARS, min_words=QUOTE_MIN_WORDS, max_chars=QUOTE_MAX_CHARS):
        if not isinstance(quote, str) or not quote.strip():
            return QuoteCheck(False, 'cita vacía')
        needle = clean_quote(quote)
        if len(needle) < min_chars or len(needle.split(' ')) < min_words:
            return QuoteCheck(False, 'cita demasiado breve para verificar')
        if len(needle) > max_chars:
            return QuoteCheck(False, f'cita demasiado larga (máximo {max_chars} caracteres)')
        position = self.normalized.find(needle)
        if position < 0:
            return QuoteCheck(False, 'la cita no aparece literalmente en el texto descargado')
        start = self._positions[position]
        end = self._positions[position + len(needle) - 1] + 1
        return QuoteCheck(True, excerpt=self.text[start:end], first_paragraph=self._paragraph(start),
                          last_paragraph=self._paragraph(end - 1))


# --- Dates -----------------------------------------------------------------

MONTH_NAMES = {
    1: ('enero', 'ene', 'january', 'jan', 'janvier', 'janv', 'janeiro', 'januar', 'gennaio'),
    2: ('febrero', 'feb', 'february', 'février', 'fevrier', 'févr', 'fevereiro', 'fev', 'februar', 'febbraio'),
    3: ('marzo', 'mar', 'march', 'mars', 'março', 'marco', 'märz', 'marz'),
    4: ('abril', 'abr', 'april', 'apr', 'avril', 'avr', 'aprile'),
    5: ('mayo', 'may', 'mai', 'maio', 'maggio'),
    6: ('junio', 'jun', 'june', 'juin', 'junho', 'juni', 'giugno'),
    7: ('julio', 'jul', 'july', 'juillet', 'juil', 'julho', 'juli', 'luglio'),
    8: ('agosto', 'ago', 'august', 'aug', 'août', 'aout'),
    9: ('septiembre', 'setiembre', 'sep', 'sept', 'set', 'september', 'septembre', 'setembro', 'settembre'),
    10: ('octubre', 'oct', 'october', 'octobre', 'outubro', 'out', 'oktober', 'okt', 'ottobre'),
    11: ('noviembre', 'nov', 'november', 'novembre', 'novembro'),
    12: ('diciembre', 'dic', 'december', 'dec', 'décembre', 'decembre', 'déc', 'dezembro', 'dez', 'dezember', 'dicembre'),
}
_MONTH_PATTERNS = {month: re.compile(r'(?<![^\W\d_])(?:' + '|'.join(re.escape(name) for name in names) + r')\.?(?![^\W\d_])')
                   for month, names in MONTH_NAMES.items()}
_ISO_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_YEAR = re.compile(r'(?<!\d)(1[89]\d{2}|2\d{3})(?!\d)')
_NUMERIC_DATE = re.compile(r'(?<!\d)(\d{1,2})[/.\-](\d{1,2})(?:[/.\-](\d{2}|\d{4}))?(?!\d)')


@dataclass
class DateCheck:
    ok: bool
    value: date | None = None
    reason: str = ''


def parse_iso_date(value):
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def date_quote_states(quote, value):
    """True if the normalized ``quote`` explicitly states the day and month of ``value``.

    Accepted forms: ISO ``AAAA-MM-DD``; numeric ``d/m[/a]`` (either order);
    or the day number together with the month name (es, en, fr, pt, de, it).
    A year present in the quote must match. Relative expressions such as
    "ayer" or "el martes" are rejected: deriving a date from them is inference.
    """
    text = normalize_text(quote)
    years = _YEAR.findall(text)
    if years and str(value.year) not in years:
        return False
    if value.isoformat() in text:
        return True
    for day_part, month_part, year_part in _NUMERIC_DATE.findall(text):
        day, month = int(day_part), int(month_part)
        if year_part and len(year_part) == 4 and int(year_part) != value.year:
            continue
        if (day, month) == (value.day, value.month) or (month, day) == (value.day, value.month):
            return True
    day_present = re.search(rf'(?<!\d)0?{value.day}(?!\d)', text) is not None
    return day_present and _MONTH_PATTERNS[value.month].search(text) is not None


def check_event_date(event_date, date_quote, document, *, today):
    """Accept ``event_date`` only if ``date_quote`` is in ``document`` and states that date."""
    if event_date in (None, ''):
        return DateCheck(False, reason='sin fecha')
    value = parse_iso_date(event_date)
    if value is None:
        return DateCheck(False, reason=f'fecha no válida «{event_date}»')
    if not date(MIN_EVENT_YEAR, 1, 1) <= value <= today + timedelta(days=366):
        return DateCheck(False, reason='fecha fuera del intervalo plausible')
    if not date_quote:
        return DateCheck(False, reason='fecha sin cita que la respalde')
    quote_check = document.check_quote(date_quote, min_chars=DATE_QUOTE_MIN_CHARS, min_words=1, max_chars=DATE_QUOTE_MAX_CHARS)
    if not quote_check.ok:
        return DateCheck(False, reason=f'cita de la fecha: {quote_check.reason}')
    if not date_quote_states(date_quote, value):
        return DateCheck(False, reason='la cita no expresa ese día y mes')
    return DateCheck(True, value=value)


# --- Corroboration ------------------------------------------------------------

_SECOND_LEVEL = {'co', 'com', 'org', 'net', 'gov', 'gob', 'gouv', 'ac', 'edu', 'go', 'or', 'ne', 'mil', 'nic', 'int'}


def registrable_domain(url):
    """Approximate registrable domain (eTLD+1) used to tell publishers apart.

    Heuristic without a public-suffix download: ``news.bbc.co.uk`` → ``bbc.co.uk``,
    ``www.reuters.com`` → ``reuters.com``. Unusual suffixes may be grouped
    imperfectly; the count is informative, not a quality score.
    """
    host = (urlsplit(url).hostname or '').rstrip('.').lower()
    labels = [label for label in host.split('.') if label]
    if len(labels) <= 2:
        return '.'.join(labels)
    if len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL:
        return '.'.join(labels[-3:])
    return '.'.join(labels[-2:])


def distinct_publishers(urls):
    return len({registrable_domain(url) for url in urls if url})


def valid_references(references, valid_ids):
    """``references`` as a sorted id list if non-empty and every id exists; otherwise ``None``."""
    if not isinstance(references, list) or not references:
        return None
    ids = []
    for item in references:
        if isinstance(item, bool) or not isinstance(item, int) or item not in valid_ids:
            return None
        ids.append(item)
    return sorted(set(ids))
