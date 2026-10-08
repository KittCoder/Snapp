"""Cheap conversational interpretation around the unchanged retrieval parser.

Only vocabulary-backed ingredients and existing indexed categories become filters.
Vague preferences remain semantic text; they are never recipe claims.
"""
from __future__ import annotations
import re
import recipe_search_typesense as retrieval

SCAFFOLD = re.compile(
    r"\b(?:can|could|would) you (?:please )?(?:find|show|give)(?: me)?\b|"
    r"\b(?:i (?:want|would like|feel like|have)|i'd like|i'm (?:looking for|craving)|"
    r"i am (?:looking for|craving)|i've got|i have got|can i use|do you have|"
    r"give me|show me|find me|make (?:it|that|those)|i changed my mind)\b", re.I)
FILLER = re.compile(r"\b(?:maybe|perhaps|something|anything|please|actually|instead|"
                    r"really|tonight|sounds good|recipes?|ideas?|for|a|an|the)\b", re.I)
ALTERNATIVES = re.compile(
    r"\b(?:another(?: one| option| recipe)?|more(?!\s+than\b)(?: options| recipes| results)?|"
    r"something else|something similar|similar(?: options| recipes)?|something like (?:that|this|it)|"
    r"not (?:that|this)(?: one)?|anything else)\b", re.I)
RELATIVE_TIME = re.compile(r"\b(?:quicker|faster|not as long)\b", re.I)
NEGATIVE = re.compile(r"\b(?:i (?:do not|don't) (?:really )?(?:want|like)|"
                      r"anything but|avoid|not(?! too\b| as\b| that\b| this\b)|skip|exclude|"
                      r"without|no)\s+(?:the\s+)?", re.I)
NEUTRAL = re.compile(r"\bi (?:don't|do not) mind\s+", re.I)
CLEAR = re.compile(r"^(?:forget|remove|clear|drop|ignore|never mind)\s+(?:the\s+)?(.+?)"
                   r"(?:\s+(?:restriction|constraint|filter|limit|part))?$", re.I)
REPLACE = re.compile(r"\binstead\b|^replace\b|^actually\b|\bi changed my mind\b", re.I)
SEARCH_REQUEST = re.compile(r"^(?:(?:can|could|would) you (?:please )?(?:find|show|give)|"
                            r"do you have|can i use|anything\b)", re.I)
GENERAL = {'hi', 'hello', 'thanks', 'thank you', 'help', 'yes', 'no', 'ok', 'okay',
           'why', 'why that', 'tell me more'}


def normalize(message):
    return retrieval.normalize_text(message.replace('’', "'").replace('—', ',').replace('–', ',')).lower().strip(' .?!')


def semantic_text(text):
    text = SCAFFOLD.sub(' ', text)
    text = FILLER.sub(' ', text)
    for term in list(retrieval.MEAL_TERMS) + list(retrieval.DIETARY_CATEGORY_TERMS):
        text = re.sub(rf'\b{re.escape(term)}\b', ' ', text)
    # These joins/pronouns have no content once their structured spans are gone.
    text = re.sub(r'\b(?:with|using|use|and|but|in those|in these|it|that|those)\b', ' ', text)
    return retrieval.normalize_text(text).strip(' .?!,;:-')


def parse_message(message):
    text = normalize(message)
    audit = {'original_message': message, 'operation': None}
    # Return constraint operations explicitly; don't run ingredient extraction on
    # the object of an undo request and accidentally re-add that ingredient.
    clear = CLEAR.fullmatch(text)
    allowance = re.fullmatch(r'(.+?) (?:is|are) (?:fine|okay|ok)(?: actually)?', text)
    if clear or allowance:
        audit.update(operation='clear', clear_target=clear.group(1) if clear else allowance.group(1),
                     allowance=bool(allowance))
        return '', empty_constraints(audit)

    text = re.sub(r"\b(?:i have got|i've got|i have)\b", 'with', text)
    text = SCAFFOLD.sub(' ', text)
    alternative = ALTERNATIVES.search(text)
    if alternative:
        audit['operation'] = 'alternatives'
        audit['reject_selected'] = bool(re.search(r'\bnot (?:that|this)', text))
        text = ALTERNATIVES.sub(' ', text)
    relative = bool(RELATIVE_TIME.search(text))
    if relative:
        audit['relative_time'] = True
        text = RELATIVE_TIME.sub(' ', text)
    replacing = bool(REPLACE.search(normalize(message)))
    audit['replace_ingredients'] = replacing
    old_term = None
    explicit = re.fullmatch(r'replace (.+?) with (.+)', normalize(message))
    contrast = re.fullmatch(r'(?:actually )?(.+?) instead of (.+)', normalize(message))
    if explicit:
        old_term, text = explicit.groups()
    elif contrast:
        text, old_term = contrast.groups()
    if old_term:
        audit['replace_target'] = old_term
    # The legacy 'actually' rule accepts arbitrary trailing words. Remove that
    # marker and let its existing high-confidence vocabulary do the extraction.
    text = re.sub(r'\b(?:actually|instead)\b', ' ', text)

    # Explicit time bounds are authoritative. Vague speed stays semantic.
    text = re.sub(r'\b(?:under|less than|within|no more than) half an hour\b', 'under 30 minutes', text)
    text = re.sub(r'\b(?:no more than|not more than|not over) (\d+)\s*(minutes?|mins?)\b', r'under \1 minutes', text)
    text = re.sub(r'\baround (\d+)\s*(minutes?|mins?)\b', r'around \1 minutes', text)
    around = re.search(r'\baround (\d+) minutes\b', text)
    if around:
        audit['approximate_time_minutes'] = int(around.group(1))
        # "Around" is a preference, not a maximum constraint.
        text = re.sub(r'\baround (\d+) minutes\b', r'about \1 minutes', text)
    text = re.sub(r"\bi (?:don't|do not) have much time\b", 'quick', text)
    text = re.sub(r'\bfast\b', 'quick', text)
    # Preserve low-spice meaning instead of treating "not" as an exclusion.
    text = re.sub(r'\bnot too spicy\b', 'mild', text)
    text = re.sub(r'\bless spicy\b', 'mild', text)
    ingredient = retrieval.implicit_ingredient_pattern()

    def marked_terms(pattern, value, positive=False):
        spans = []
        terms = []
        for marker in pattern.finditer(value):
            pos = marker.end()
            if not positive and re.match(r'dairy\b', value[pos:]):
                # Existing dairy_free path is supported by indexed ingredient metadata.
                spans.append((marker.start(), pos + len('dairy'), ' dairy-free '))
                continue
            category = next((term for term in list(retrieval.MEAL_TERMS) + list(retrieval.DIETARY_CATEGORY_TERMS)
                             if re.match(rf'{re.escape(term)}\b', value[pos:])), None)
            if category and not positive:
                audit['unsupported_negative_category'] = category
                spans.append((marker.start(), pos + len(category), ' '))
                continue
            item = ingredient.match(value, pos)
            if not item:
                continue
            while item:
                terms.append(retrieval.normalize_token(item.group()))
                pos = item.end()
                separator_pattern = r'\s+and\s+' if marker.group().strip() == 'not' else r'(?:\s+and\s+|,\s*)'
                separator = re.match(separator_pattern, value[pos:])
                if not separator:
                    break
                next_pos = pos + separator.end()
                item = ingredient.match(value, next_pos)
                if item:
                    pos = next_pos
            spans.append((marker.start(), pos, ' '))
        for start, end, replacement in reversed(spans):
            value = value[:start] + replacement + value[end:]
        return value, terms

    text, neutral = marked_terms(NEUTRAL, text, positive=True)
    audit['neutral_ingredients'] = neutral
    text, excluded = marked_terms(NEGATIVE, text)
    cleaned, parsed = retrieval.parse_natural_language_query(text)
    parsed['exclude_ingredients'] = retrieval.clean_terms(parsed['exclude_ingredients'] + excluded)
    for key in ('include_ingredients', 'exclude_ingredients'):
        parsed[key] = retrieval.clean_terms([re.sub(r'^(?:and|or)\s+', '', term) for term in parsed[key]])
    # Negative and positive spans are extracted independently, never inferred
    # from an LLM or a fuzzy ingredient match.
    parsed.update(audit)
    preference = semantic_text(cleaned)
    parsed['cleaned_semantic_query'] = preference
    return preference, parsed


def empty_constraints(audit):
    return {**{key: [] for key in ('include_ingredients', 'exclude_ingredients', 'categories', 'dietary')},
            'max_time': None, 'min_time': None, 'clear_time': False,
            'replace_include_ingredients': False, 'cleaned_semantic_query': '', **audit}
