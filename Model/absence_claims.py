"""Separate absence claims from positive food-head evidence.

Input is ontology-normalized text (hyphens are spaces). Added-ingredient claims
are deliberately distinct from total absence: no added sugar is not sugar-free.
"""
import re

_CLAIMS = re.compile(
    r'\b(?:no\s+added\s+(?P<added>[a-z]+)|no\s+(?P<added_after>[a-z]+)\s+added|'
    r'without\s+added\s+(?P<without_added>[a-z]+)|zero\s+(?P<zero>[a-z]+)|(?P<suffix>[a-z]+)\s+free(?!\s+of\b)|'
    r'free\s+of\s+(?P<free_of>[a-z]+)|no\s+(?P<no>[a-z]+)|'
    r'without\s+(?:the\s+)?(?P<without>[a-z]+)|(?P<nonfat>non\s*fat))\b'
)


def separate_absence_claims(text):
    claims = set()
    def remove(match):
        fields = match.groupdict()
        token = next(value for value in fields.values() if value)
        if fields['nonfat']:
            token = 'fat'
        if fields['added'] or fields['added_after'] or fields['without_added']:
            token = 'added_' + token
        # Sodium/salt absence use the same established dietary identity.
        if token in ('sodium', 'added_sodium', 'added_salt'):
            token = 'salt'
        claims.add(token)
        return ' '
    identity_text = re.sub(r'\s+', ' ', _CLAIMS.sub(remove, text)).strip()
    return identity_text, tuple(sorted(claims))
