"""Ingredient quantities × USDA nutrients per 100 g, independent of purchases."""
from functools import lru_cache
import gzip
import json
import math
from pathlib import Path
import re

from basket_quantity import canonical_quantity, VOLUME_TO_MILLILITER
from ingredient_normalization import normalize_unit
from recipe_ingredient_adapter import canonical_recipe_ingredients

MACROS = ('protein_g', 'carbohydrates_g', 'fat_g')
NUTRIENTS = (*MACROS, 'calories', 'fiber_g', 'sugars_g', 'sodium_mg')
STOP = {'and','of','the','all','purpose','fresh','chopped','diced','sliced','shredded','crushed',
        'minced','ground','large','medium','small','warm','cold','beaten','peeled','divided',
        'drained','optional','finely','thinly','packed','about','into','piece','pieces',
        'cubed','trimmed','seeded','deseeded','halved','quartered','softened','melted'}
ALIASES = {'eggs':'egg','onions':'onion','tomatoes':'tomato','potatoes':'potato','leaves':'leaf',
           'chilies':'chili','chiles':'chili','chilli':'chili','garbanzo':'chickpea','scallion':'onion',
           'scallions':'onion','cilantro':'coriander','arugula':'rocket','powdered':'powder'}


def tokens(text):
    words = re.findall(r'[a-z]+', text.lower())
    return {ALIASES.get(word, word[:-1] if word.endswith('s') and not word.endswith(('ss','us')) else word)
            for word in words if word not in STOP}


@lru_cache(maxsize=1)
def catalog():
    path = Path(__file__).with_name('usda_nutrition_catalog.json.gz')
    with gzip.open(path, 'rt') as source:
        return json.load(source)['foods']


def ingredient_query(ingredient):
    name = re.sub(r'\b\d+(?:[./]\d+)?\b|\b(?:ounce|pound|gram|oz|lb)s?\b', '', ingredient.ingredient_name)
    name = re.sub(r'\bskin[- ]on\b', 'skin', name, flags=re.I)
    raw = ingredient.raw_text.lower()
    if re.search(r'\begg\s+whites?\b', raw):name = 'egg white'
    elif re.search(r'\begg\s+yolks?\b', raw):name = 'egg yolk'
    for state in ('cooked', 'dry', 'dried', 'raw', 'canned'):
        if re.search(r'\b'+state+r'\b',raw) and state not in name:name += ' '+state
    if ingredient.unit == 'can' and 'canned' not in name:name += ' canned'
    if 'green onion' in raw or 'scallion' in raw:name = 'onion spring'
    if 'cilantro' in raw:name = 'coriander leaves raw'
    if 'all-purpose flour' in raw or 'all purpose flour' in raw:name = 'wheat flour all-purpose'
    if tokens(name) == {'flour'}:name = 'wheat flour all-purpose'
    if tokens(name) in ({'rice'}, {'rice', 'raw'}, {'rice', 'cooked'}):name += ' white'
    if re.search(r'\bground\b',raw) and re.search(r'\b(?:beef|pork|turkey|chicken)\b',raw):name += ' ground'
    return re.sub(r'\s+',' ',name).strip()


def grams_for(ingredient, food):
    quantity = ingredient.quantity
    if quantity is None or not math.isfinite(quantity) or quantity <= 0:return None
    unit = ingredient.unit
    if ingredient.package_quantity and ingredient.package_unit:
        amount = canonical_quantity(quantity*ingredient.package_quantity, ingredient.package_unit)
        if amount.dimension == 'mass':return amount.base_quantity
    if unit in ('can','package','jar','bottle'):
        match = re.search(r'(\d+(?:[./]\d+)?)\s*(ounces?|oz|pounds?|lbs?|grams?|g)\b',ingredient.raw_text,re.I)
        if match:
            amount = canonical_quantity(quantity*float(match[1]),match[2])
            if amount.dimension=='mass':return amount.base_quantity
    amount = canonical_quantity(quantity,unit or 'count')
    if amount.dimension == 'mass':return amount.base_quantity
    normalized = normalize_unit(unit) if unit else None
    choices=[]
    for portion in food.get('portions',[]):
        description = (portion['unit']+' '+portion['description']).lower()
        portion_amount = float(portion.get('amount') or 1)
        weight = float(portion.get('grams') or 0)
        if portion_amount<=0 or weight<=0:continue
        portion_match = re.search(r'\b(cups?|tablespoons?|teaspoons?|tbsp|tbs|tsp|milliliters?|liters?|ml)\b', description)
        portion_unit = normalize_unit(portion_match[1]) if portion_match else None
        if normalized in VOLUME_TO_MILLILITER and portion_unit:
            grams = quantity*VOLUME_TO_MILLILITER[normalized]/VOLUME_TO_MILLILITER[portion_unit]*weight/portion_amount
            score = 20 if normalized==portion_unit else 10
        elif not portion_unit and ((unit and re.search(r'\b'+re.escape(unit)+r's?\b',description)) or (amount.dimension=='count' and (tokens(ingredient.ingredient_name) & tokens(description) or re.search(r'\b(?:small|medium|large|whole|fruit|vegetable|egg|piece)\b',description)))):
            grams=quantity*weight/portion_amount;score=10
        else:continue
        for qualifier in ('large','medium','small','chopped','diced','sliced','shredded','packed','clove'):
            if qualifier in ingredient.raw_text.lower() and qualifier in description:score+=5
        if 'extra' in description and 'extra' not in ingredient.raw_text.lower():score-=3
        if not re.search(r'\b(?:large|small)\b',ingredient.raw_text.lower()) and 'medium' in description:score+=3
        choices.append((score,grams))
    if not choices:return None
    return max(choices,key=lambda choice:choice[0])[1]


@lru_cache(maxsize=2048)
def food_candidates(query):
    wanted=tokens(query)
    if not wanted:return []
    candidates=[]
    for food in catalog():
        description=food['description'].lower();available=tokens(description)
        if not wanted <= available:continue
        if any(re.search(r'\b(?:no|without)\s+'+re.escape(word)+r'\b',description) for word in wanted):continue
        # Whole ingredients must not silently become a mixed dish or a different preparation.
        forbidden={'baby','infant','formula','bread','sandwich','pizza','soup','sauce','flour','juice',
                   'powder','white','yolk','dried','dehydrated','cooked','canned','sweetened','sweet' }
        if wanted & {'broth','stock','bouillon'}:forbidden -= {'soup','canned'}
        extras=(forbidden & available)-wanted
        if {'olive','oil'} <= wanted and available & {'corn','peanut','soybean','canola'}:continue
        score=100-len(available-wanted)*8-len(extras)*35
        if wanted & {'broth','stock'}:
            if 'ready-to-serve' in description or 'ready to serve' in description:score+=30
            if available & {'condensed','dry','cube','dehydrated'} and not wanted & {'condensed','dry','cube','dehydrated'}:score-=60
        if 'rice' in wanted and available & {'wild','sweet','instant','parboiled'} and not available & wanted & {'wild','sweet','instant','parboiled'}:score-=40
        if 'raw' in available and 'cooked' not in wanted:score+=15
        if 'ground' in query and 'ground' in description:score+=15
        if 'all-purpose' in query and 'all-purpose' in description:score+=20
        if food['data_type']=='Foundation':score+=4
        if food.get('portions'):score+=3
        candidates.append((score,food))
    return sorted(candidates,key=lambda item:item[0],reverse=True)[:30]


def recipe_nutrition(recipe, servings=None, servings_source='recipe'):
    if isinstance(recipe, dict) and recipe.get('ingredients') and not recipe.get('extendedIngredients'):
        recipe = {**recipe, 'ingredients': [
            {**item, 'raw': item.get('raw') or item.get('display') or item.get('measure') or ''}
            if isinstance(item, dict) else item for item in recipe['ingredients']]}
    totals={key:0.0 for key in NUTRIENTS};lines=[];missing=[]
    for ingredient in canonical_recipe_ingredients(recipe):
        query=ingredient_query(ingredient)
        choices=[]
        for score,food in food_candidates(query):
            grams=grams_for(ingredient,food)
            if grams is not None and score>=30:choices.append((score,food,grams))
        if not choices:
            missing.append(ingredient.raw_text)
            lines.append({'ingredient':ingredient.raw_text,'status':'unmatched_or_unknown_quantity'})
            continue
        _,food,grams=max(choices,key=lambda item:item[0])
        nutrients={key:food['nutrients_per_100g'].get(key,0)*grams/100 for key in NUTRIENTS}
        for key,value in nutrients.items():totals[key]+=value
        lines.append({'ingredient':ingredient.raw_text,'status':'matched','fdc_id':food['fdc_id'],
                      'usda_description':food['description'],'grams':round(grams,3),
                      'nutrients':{key:round(value,3) for key,value in nutrients.items()}})
    valid_servings = isinstance(servings,(int,float)) and math.isfinite(servings) and servings>0
    totals={key:round(value,3) for key,value in totals.items()}
    return {'nutrition_total':totals,'nutrition_per_person':{key:round(value/servings,3) for key,value in totals.items()} if valid_servings else {},
            'calories_total':totals['calories'],'calories_per_person':round(totals['calories']/servings,3) if valid_servings else None,
            'nutrition_servings':servings if valid_servings else None,
            'nutrition_servings_source':servings_source,
            'nutrition_source':'USDA FoodData Central',
            'nutrition_status':'complete' if lines and not missing else 'partial' if len(missing)<len(lines) else 'unavailable',
            'nutrition_missing_ingredients':missing,'nutrition_ingredients':lines}
