from __future__ import annotations

import re

from .procurement import normalize_company_name, normalize_space

# Only source labels that literally declare a doing-business-as relationship are
# decomposed. This is intentionally not a fuzzy company-name resolver.
_EXPLICIT_DBA_PATTERN = re.compile(
    r"\s+(?:D\s*[/.-]\s*B\s*[/.-]\s*A\s*[/.-]?|DBA)\s+",
    flags=re.IGNORECASE,
)


def strict_identity_key(value: str | None) -> str:
    """Normalize case/punctuation while preserving legal suffixes."""
    return normalize_company_name(value, strip_legal_suffixes=False)


def explicit_dba_aliases(value: str | None) -> tuple[str, ...]:
    """Return source-declared DBA components, or an empty tuple.

    Examples accepted include ``D/B/A``, ``D/B/A/`` and ``DBA``. The full raw
    source label remains authoritative and is never replaced by these aliases.
    """
    text = normalize_space(value)
    if not text:
        return ()
    parts = _EXPLICIT_DBA_PATTERN.split(text, maxsplit=1)
    if len(parts) != 2:
        return ()
    aliases = tuple(
        alias
        for part in parts
        if (alias := normalize_space(part.strip(" /.-")))
    )
    return aliases if len(aliases) == 2 else ()


def source_identity_keys(value: str | None) -> frozenset[str]:
    """Return exact identity keys carried by one source vendor label.

    The full source label is always included. Extra keys are emitted only when
    the source explicitly declares a DBA relationship.
    """
    keys: set[str] = set()
    full_key = strict_identity_key(value)
    if full_key:
        keys.add(full_key)
    for alias in explicit_dba_aliases(value):
        alias_key = strict_identity_key(alias)
        if alias_key:
            keys.add(alias_key)
    return frozenset(keys)
