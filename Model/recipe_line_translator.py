"""Translate recipe display lines without changing amounts or named brands."""
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

QUANTITIES = re.compile(r'\d+(?:[.,/]\d+)*(?:\s*[¼½¾⅓⅔⅛⅜⅝⅞])?|[¼½¾⅓⅔⅛⅜⅝⅞]')
BRANDS = re.compile(r'\b(?:Kraft|Knorr|Hellmann[’\']?s?|McCormick|Tabasco|Heinz|Campbell[’\']?s?|Velveeta|Oreo)\b', re.I)
PROTECTED = re.compile(QUANTITIES.pattern + '|' + BRANDS.pattern, re.I)


def quantities(text):
    return QUANTITIES.findall(text)


def valid_translation(source, candidate):
    return (isinstance(candidate, str) and bool(candidate.strip())
            and len(candidate) <= max(500, len(source)*5)
            and quantities(source) == quantities(candidate)
            and all(brand in candidate for brand in BRANDS.findall(source)))


class RecipeLineTranslator:
    def _request(self, texts, source, target):
        query = urlencode({'client': 'dict-chrome-ex', 'sl': source, 'tl': target, 'q': texts}, doseq=True)
        request = Request('https://clients5.google.com/translate_a/t?' + query,
                          headers={'User-Agent': 'SNAPP recipe localization'})
        with urlopen(request, timeout=12) as response:
            data = json.load(response)
        if not isinstance(data, list) or len(data) != len(texts):
            raise ValueError('Translation changed the number of recipe lines')
        return data

    def translate_many(self, texts, source='en', target='es'):
        # Translate whole sentences first to retain natural grammar.
        candidates = self._request(texts, source, target)
        results = [candidate.strip() if valid_translation(original, candidate) else None
                   for original, candidate in zip(texts, candidates)]
        # If a provider converted a number or transliterated a brand, translate the
        # surrounding text separately and retain the exact protected source spans.
        fragments, reconstructions = [], []
        for index, (text, result) in enumerate(zip(texts, results)):
            if result is not None:
                continue
            pieces, end = [], 0
            for match in PROTECTED.finditer(text):
                segment = text[end:match.start()]
                if segment.strip():
                    pieces.append(('translated', len(fragments), segment))
                    fragments.append(segment.strip())
                else:
                    pieces.append(('literal', segment))
                pieces.append(('literal', match.group()))
                end = match.end()
            segment = text[end:]
            if segment.strip():
                pieces.append(('translated', len(fragments), segment))
                fragments.append(segment.strip())
            else:
                pieces.append(('literal', segment))
            reconstructions.append((index, pieces))
        translated = self._request(fragments, source, target) if fragments else []
        for index, pieces in reconstructions:
            parts = []
            for piece in pieces:
                if piece[0] == 'literal':
                    parts.append(piece[1])
                else:
                    value = translated[piece[1]]
                    if not isinstance(value, str):
                        parts = []
                        break
                    original = piece[2]
                    parts.append((' ' if original[:1].isspace() else '') + value.strip()
                                 + (' ' if original[-1:].isspace() else ''))
            candidate = ''.join(parts)
            results[index] = candidate if valid_translation(texts[index], candidate) else None
        return results

    def translate(self, text, source='en', target='es'):
        candidate = self.translate_many([text], source=source, target=target)[0]
        if candidate is None:
            raise ValueError('Translation lost a protected recipe value')
        return candidate
