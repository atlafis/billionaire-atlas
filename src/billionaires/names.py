"""Name normalisation and record linkage between the two sources.

The historical lists and the real-time archive share no identifier, so people
are linked by name. The rules are deliberately conservative: a link is made
only when the normalised key is unique on the real-time side. An ambiguous key
(two different people called "Wang Wei") is left unlinked rather than guessed.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

_DROP_TOKENS = {
    "jr", "sr", "ii", "iii", "iv", "family", "and", "the", "sir", "dame",
    "dr", "de", "da", "di", "del", "der", "van", "von", "la", "le", "al", "el", "bin",
}


# Nicknames and transliteration variants seen in the two sources. Applied to
# every token, so "Jim Simons" and "James Simons" share a key.
_ALIASES = {
    "jim": "james", "jimmy": "james", "bill": "william", "billy": "william", "will": "william",
    "bob": "robert", "rob": "robert", "bobby": "robert", "les": "leslie", "mike": "michael",
    "steve": "steven", "stephen": "steven", "dick": "richard", "rick": "richard",
    "chuck": "charles", "charlie": "charles", "tom": "thomas", "tony": "anthony",
    "dan": "daniel", "danny": "daniel", "dave": "david", "joe": "joseph", "ken": "kenneth",
    "larry": "lawrence", "sam": "samuel", "andy": "andrew", "pat": "patrick", "ron": "ronald",
    "don": "donald", "ed": "edward", "ned": "edward", "phil": "phillip", "philip": "phillip",
    "chris": "christopher", "matt": "matthew", "nick": "nicholas", "ben": "benjamin",
    "jeff": "jeffrey", "geoffrey": "jeffrey", "greg": "gregory", "fred": "frederick",
    "liz": "elizabeth", "beth": "elizabeth", "kathy": "katherine", "kate": "katherine",
    "catherine": "katherine", "peggy": "margaret", "maggie": "margaret", "sue": "susan",
    "alexey": "alexei", "aleksei": "alexei", "sergey": "sergei", "andrey": "andrei",
    "yury": "yuri", "iouri": "yuri", "dmitri": "dmitry", "dmitriy": "dmitry",
    "mikhael": "mikhail", "gennady": "gennadi", "nikolay": "nikolai",
}


def is_group(name: str) -> bool:
    """'Theo and Karl Albrecht' names two people; never link those."""
    text = f" {str(name).lower()} "
    return " and " in text.replace(" and family", " ") or bool(re.search(r"&\s*(?!family)\w", text))


def ascii_fold(text: str) -> str:
    """Strip accents: 'Hansjörg Wyss' -> 'Hansjorg Wyss'."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def tokens(name: str) -> list[str]:
    """Lower-case alphabetic tokens of a name, honorifics and suffixes removed."""
    text = ascii_fold(str(name)).lower().replace("&", " ")
    text = re.sub(r"[^a-z ]", " ", text)
    return [_ALIASES.get(t, t) for t in text.split() if len(t) > 1 and t not in _DROP_TOKENS]


def full_key(name: str) -> str:
    """Order-independent key, so 'Li Ka-shing' and 'Ka-shing Li' collide."""
    return " ".join(sorted(tokens(name)))


def short_key(name: str) -> str:
    """First and last token only, to absorb middle names and initials."""
    t = tokens(name)
    ends = {t[0], t[-1]} if t else set()
    return " ".join(sorted(ends)) if len(ends) == 2 else ""


def unique_index(names: Iterable[tuple[str, str]], keyfunc) -> dict[str, str]:
    """Map key -> id, dropping every key that more than one id produces."""
    seen: dict[str, set[str]] = {}
    for ident, name in names:
        k = keyfunc(name)
        if k:
            seen.setdefault(k, set()).add(ident)
    return {k: next(iter(ids)) for k, ids in seen.items() if len(ids) == 1}


def link(
    left: Iterable[str], right: Iterable[tuple[str, str]]
) -> dict[str, tuple[str, str]]:
    """Link names on the left to ids on the right.

    Returns ``{left_name: (right_id, method)}`` for linked names only, where
    method is ``"full"`` (all tokens agree) or ``"short"`` (first and last
    token agree and both keys are unambiguous).
    """
    right = list(right)
    by_full = unique_index(right, full_key)
    by_short = unique_index(right, short_key)
    out: dict[str, tuple[str, str]] = {}
    for name in left:
        if is_group(name):
            continue
        k = full_key(name)
        if k in by_full:
            out[name] = (by_full[k], "full")
            continue
        s = short_key(name)
        if s and s in by_short:
            out[name] = (by_short[s], "short")
    return out


def slug(name: str) -> str:
    return "-".join(tokens(name)) or "unknown"
