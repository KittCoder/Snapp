"""Language boundary around the original, canonical English RecipeChatService.

No retrieval/parser mutations. Offline vocabulary is composable and deliberately
bounded; optional translators may return text, never filters, facts or recipe IDs.
"""
from copy import deepcopy
from functools import lru_cache
import importlib
import json
import os
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
LOCALES = tuple(json.loads((ROOT/'Web/i18n/locales.json').read_text()))

@lru_cache(maxsize=1)
def lexicons():
    return json.loads((ROOT/'Model/recipe_chat_locales.json').read_text())

def locale_code(value):
    if value in LOCALES: return value
    base = str(value or '').split('-')[0]
    return 'zh-CN' if base == 'zh' else base if base in LOCALES else 'en'

def ascii_digits(text):
    return ''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)

def phrase_pattern(phrase):
    # CJK/Korean particles do not use Latin word boundaries.
    if re.search(r'[\u3400-\u9fff\uac00-\ud7af]', phrase): return re.escape(phrase)
    return r'(?<!\w)'+re.escape(phrase)+r'(?!\w)'

@lru_cache(maxsize=1)
def latin_foreign_pattern():
    aliases={alias for terms in lexicons().values() for canonical,values in terms.items() for alias in values
             if len(alias)>=3 and alias.isascii() and alias.lower()!=canonical.lower()}
    return re.compile('|'.join(phrase_pattern(alias) for alias in sorted(aliases,key=len,reverse=True)),re.I)

@lru_cache(maxsize=1024)
def detect_locale(message, preferred='en'):
    preferred=locale_code(preferred)
    if message.isascii() and not latin_foreign_pattern().search(message):return 'en'
    scores={}
    for locale, terms in lexicons().items():
        scores[locale]=sum(len(alias) for canonical,aliases in terms.items() for alias in aliases
            if alias.lower()!=canonical.lower() and (len(alias)>=3 or re.search(r'[^\x00-\x7f]',alias)) and re.search(phrase_pattern(alias),message,re.I))
    best=max(scores,key=scores.get)
    if scores[best]==0: return 'en' if re.search(r'\b(?:want|with|without|dinner|show|how|what|under|chicken|beef|cheese|start|clear)\b',message,re.I) else preferred
    if scores.get(preferred)==scores[best]: return preferred
    return best

TIME_PATTERNS={
 'zh-CN':r'(\d+)\s*分钟(?:以内|内|以下)', 'zh-TW':r'(\d+)\s*分鐘(?:以內|內|以下)',
 'bn':r'(\d+)\s*মিনিট(?:ের)?\s*মধ্যে', 'ko':r'(\d+)\s*분\s*(?:이내|미만)',
 'ur':r'(\d+)\s*منٹ\s*(?:سے کم|کے اندر)',
 'pl':r'(?:poniżej|w mniej niż)\s*(\d+)\s*minut',
}
FILLERS={
 'es':['que tarde','que tenga','necesito','para','una','un','el','la','los','las','en','por favor','con lo que tengo'],
 'zh-CN':['我','想','道','以内','的','请'], 'zh-TW':['我','想','道','以內','的','請'],
 'ru':['мне','что','который','рецепт','пожалуйста','чем','за'],
 'bn':['একটি','খাবার','চাই','জন্য'], 'ht':['ki pran','ki','tanpri','yon'],
 'ko':['요','를','을','으로','만','레시피','싶어요','원해','해주세요'],
 'ar':['التي','يستغرق','أريد','وجبة','من فضلك'], 'fr':['du','de','qui prend','qui','une','un','le','la','les','s’il vous plaît'],
 'ur':['چاہیے','چاہتا ہوں','کی','کا','کو','میں'], 'pl':['przepis','chcę','proszę','na','coś'],
}

@lru_cache(maxsize=1)
def translation_provider():
    path=os.getenv('SNAPP_LANGUAGE_TRANSLATOR_FACTORY','')
    if not path: return None
    try:
        module,factory=path.split(':',1)
        provider=getattr(importlib.import_module(module),factory)()
        return provider if callable(getattr(provider,'translate',None)) else None
    except Exception: return None

@lru_cache(maxsize=1)
def phrase_forms():
    return json.loads((ROOT/'Model/recipe_chat_phrases.json').read_text())

@lru_cache(maxsize=1024)
def canonicalize(message, locale):
    if locale=='en': return message
    original=ascii_digits(message)
    normalized=original.lower().strip(' .!?¿¡।۔。؟').replace('’',"'")
    for action in phrase_forms().values():
        if any(normalized==form.lower().strip(' .!?¿¡।۔。؟').replace('’',"'") for form in action['forms'].get(locale,[])):
            return action['canonical']
    provider=translation_provider()
    if provider:
        try:
            translated=provider.translate(original,source=locale,target='en')
            if isinstance(translated,str) and 0<len(translated.strip())<=300:
                # A translator cannot silently drop or add numeric constraints.
                if re.findall(r'\d+',original)==re.findall(r'\d+',translated): return translated.strip()
        except Exception: pass
    text=original.lower().replace('’',"'").replace('؟','?').replace('，',',').replace('。','.').replace('।','.').replace('۔','.').replace('¿','').replace('¡','')
    pattern=TIME_PATTERNS.get(locale)
    if pattern: text=re.sub(pattern,lambda m:f' under {m[1]} minutes ',text)
    pairs=[(alias.lower().replace('’',"'"),canonical) for canonical,aliases in lexicons().get(locale,{}).items() for alias in aliases]
    # Protect replacements so a later foreign alias cannot rewrite English output.
    replacements=[]
    for alias,canonical in sorted(pairs,key=lambda pair:len(pair[0]),reverse=True):
        token=f'ZZTOKEN{len(replacements)}ZZ'
        changed=re.sub(phrase_pattern(alias),token,text,flags=re.I)
        if changed!=text: replacements.append((token,canonical));text=changed
    for word in sorted(FILLERS.get(locale,[]),key=len,reverse=True):text=re.sub(phrase_pattern(word),' ',text,flags=re.I)
    for token,canonical in replacements:text=text.replace(token,' '+canonical+' ')
    text=re.sub(r'\s+',' ',text).strip()
    # SOV languages place an absence marker after the noun.
    text=re.sub(r'\b(cheese|milk|garlic|mushrooms) without\b',r'without \1',text)
    text=re.sub(r'\b(\d+) minutes under\b',r'under \1 minutes',text)
    text=re.sub(r'\b(\d+) minutes (?:以内|以內|মধ্যে)\b',r'under \1 minutes',text)
    text=re.sub(r'\bwant\b','I want',text)
    return text[:300]

@lru_cache(maxsize=12)
def catalog(locale):
    path=ROOT/'Web/i18n'/f'{locale}.json'
    return json.loads(path.read_text()) if path.exists() else {}

@lru_cache(maxsize=1)
def response_index():
    return {value:key for key,value in catalog('en').items() if isinstance(value,str)}

def localize_copy(text,locale):
    if locale=='en':return text
    en=catalog('en');target=catalog(locale);index=response_index()
    if text in index:return target.get(index[text],text)
    template='Using a maximum total time of {minutes} minutes.'
    text=re.sub(r'Using a maximum total time of (\d+) minutes\.',
        lambda m:target.get(index.get(template,''),template).replace('{minutes}',m[1]),text)
    # Replace complete known phrases, longest first, keeping titles/numbers intact.
    for source,key in sorted(index.items(),key=lambda pair:len(pair[0]),reverse=True):
        if len(source)>=5 and '{' not in source and source in text:
            text=text.replace(source,target.get(key,source))
    return text

EXTRA_FIELDS={'preferred_ingredients','equipment_available','equipment_excluded','health_preferences',
              'spice_preference','budget_preference','unavailable_ingredients','household_size','comparison_recipe_ids','conversation_language'}

def split_state(state, core_fields):
    if state is None:return None,{}
    if not isinstance(state,dict):raise ValueError('state must be an object.')
    if set(state)-set(core_fields)-EXTRA_FIELDS:raise ValueError('state contains unsupported fields.')
    extra={key:deepcopy(value) for key,value in state.items() if key in EXTRA_FIELDS}
    for key,value in extra.items():
        if key=='household_size':
            if type(value) is not int or not 1<=value<=20:raise ValueError('Invalid household size.')
        elif key=='conversation_language':
            if value not in LOCALES:raise ValueError('Unsupported conversation language.')
        elif isinstance(value,list):
            if len(value)>20 or any(not isinstance(x,str) or not x or len(x)>160 for x in value):raise ValueError('Invalid conversation preference list.')
        elif not isinstance(value,str) or len(value)>160:raise ValueError('Invalid conversation preference.')
    return {key:deepcopy(value) for key,value in state.items() if key in core_fields},extra


def handle_message(service, message, state=None, locale='en', pantry_items=None, household_size=1):
    import recipe_chat as chat
    from recipe_chat_conversation import extension
    if not isinstance(message,str) or not message.strip() or len(message)>300:raise ValueError('message must be a nonempty string of at most 300 characters.')
    core,extra=split_state(state,chat.RecipeChatState.__dataclass_fields__)
    language=detect_locale(message,extra.get('conversation_language',locale))
    canonical=canonicalize(message,language)
    if re.match(r'^(?:start over|reset|new search)\b',canonical,re.I):extra.clear()
    result=extension(service,canonical,core,extra,pantry_items or [],household_size)
    if result is None:
        result=service.handle_message(canonical,core)
        if result['results'] and any(extra.get(key) for key in ('preferred_ingredients','equipment_available','equipment_excluded')):
            parsed,intent=result['parsed_constraints'],result['intent']
            result=extension(service,'__apply_active_preferences__',result['state'],extra,pantry_items or [],household_size)
            result['parsed_constraints'],result['intent']=parsed,intent
    if re.match(r'^(?:start over|reset|new search)\s*$',canonical,re.I):extra={}
    actions=[]
    operation=result.get('parsed_constraints',{}).get('operation')
    if operation=='alternatives':actions.append('SIMILAR_RECIPES' if re.search(r'similar|like that',canonical,re.I) else 'SHOW_MORE')
    if result.get('parsed_constraints',{}).get('replace_ingredients'):actions.append('REPLACE_CONSTRAINT')
    if re.match(r'^(?:start over|reset|new search)\b',canonical,re.I):actions.append('RESET_CONVERSATION')
    if result['intent'] not in actions:actions.append(result['intent'])
    result['conversation_actions']=actions
    response_language=language if language!='en'  else locale_code(extra.get('conversation_language',locale))
    if response_language!='en' or extra.get('conversation_language'):extra['conversation_language']=response_language
    if extra:result['state'].update(extra)
    if response_language!='en':
        from concurrent.futures import ThreadPoolExecutor
        from recipe_chat_presentation import localize_detail
        # The UI locale controls recipe display even if a query was typed in English.
        display_language = locale_code(locale)
        if display_language == 'en':
            display_language = response_language
        def display(recipe):
            return localize_detail(recipe['id'], recipe, display_language)
        with ThreadPoolExecutor(max_workers=5) as executor:
            result['localized_results'] = list(executor.map(display, result['results']))
        selected = result.get('selected_recipe')
        if selected:
            localized = display(selected)
            result['localized_selected_recipe'] = localized
            if result['intent']=='QUESTION_ABOUT_SELECTED_RECIPE':
                if re.search(r'what ingredients|list (?:the )?ingredients', canonical, re.I):
                    texts = localized.get('ingredients_text') or localized.get('ingredient_names') or []
                    if texts:
                        result['message'] = 'Stored ingredients: ' + '; '.join(texts) + '.'
                elif re.search(r'how (?:do|can) i (?:make|cook)|instructions|steps', canonical, re.I):
                    steps = localized.get('instructions') or []
                    steps = steps if isinstance(steps, list) else steps.splitlines()
                    if steps:
                        result['message'] = 'Stored instructions:\n' + '\n'.join(f'{i}. {step}' for i, step in enumerate(steps, 1))
            if selected.get('title'):
                result['message'] = result['message'].replace(selected['title'], localized.get('title', selected['title']))
        for recipe, localized in zip(result['results'], result['localized_results']):
            if recipe.get('title'):
                result['message'] = result['message'].replace(recipe['title'], localized.get('title', recipe['title']))
        result['message'] = localize_copy(result['message'], display_language)
        result['conversation_language'] = display_language
    return result
