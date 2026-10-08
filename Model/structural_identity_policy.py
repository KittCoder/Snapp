"""Shared structural policy: no text similarity, product IDs or brand exceptions.

Taxonomy assigns identities; this module compares them directionally. Unknown
required evidence never becomes a match. Kitchen operations are explicit policy
exceptions, not similarity-based substitutions.
"""
from enum import Enum
import re

class Evidence(str,Enum):
    MATCH='MATCH'
    MISMATCH='MISMATCH'
    UNKNOWN='UNKNOWN'

REQUIRED_ATTRIBUTES=('state','fat_level','salt_level','sweetness','flavor','variety','bone','skin','prepared','grade','ripeness','packing_medium','treatment')
DERIVED_FAMILIES=frozenset({'juice','sauce','soup','fruit_preserve','dressing','dip','pastry','baking_mix','dessert','dessert_mix','cookie','cracker','chips','confection','chocolate','cereal','gravy','syrup','condiment_paste','nut_butter','seed_butter','plant_milk','plant_yogurt','plant_cream','plant_meat','plant_cheese','deli_meat','sausage','produce_mix','imitation_food','prepared_side','creamer','prepared'})
KITCHEN_OPERATIONS=frozenset({'chopped','diced','sliced','peeled','minced','cubed','grated','shredded','cooked'})
PURCHASE_DIMENSIONS=frozenset({'state','treatment','grade','variety','grain_type','dietary_identity','fat_level','salt_level','species','cut','packing_medium','purchase_variants'})
GENERIC_CHILDREN={
 ('pasta','generic'):None,('juice','generic'):None,('cereal','generic'):None,
 ('syrup','generic'):None,('nuts','generic'):None,('dressing','generic'):None,
 ('acid','vinegar'):frozenset({'cider_vinegar','rice_vinegar','white_vinegar','white_wine_vinegar','red_wine_vinegar','balsamic_vinegar','raspberry_vinegar'}),
 ('acid','wine_vinegar'):frozenset({'red_wine_vinegar','white_wine_vinegar'}),
 ('fat','cooking_oil'):frozenset({'olive_oil','canola_oil','vegetable_oil','coconut_oil','sesame_oil','sunflower_oil','corn_oil','peanut_oil','avocado_oil'}),
 ('bread','plain'):frozenset({'whole_grain','whole_wheat'}),
}

def identity_form(identity):
    if not identity.family:return 'unknown'
    if identity.domain!='food' or identity.family=='nonfood':return 'nonfood'
    if identity.family.startswith('derived_') or identity.family in DERIVED_FAMILIES:return 'derived'
    return 'basic'

def semantic_head(identity):
    # Shared head category is separate from species/cut/variety requirements.
    if identity.family=='dessert':return identity.subfamily or 'dessert'
    if identity.family in ('dairy','plant_milk','plant_yogurt','plant_cream'):
        return identity.family+':'+str(identity.subfamily or 'unknown')
    if identity.family=='derived_sauce':return 'sauce'
    if identity.family and identity.family.startswith('derived_'):return identity.family[8:]
    return identity.family or 'unknown'

def required_evidence(required,observed):
    if observed is None:return Evidence.UNKNOWN
    return Evidence.MATCH if required==observed else Evidence.MISMATCH

def generic_child(family,parent,child):
    key=(family,parent)
    if key not in GENERIC_CHILDREN:return False
    allowed=GENERIC_CHILDREN[key]
    return bool(child) and (allowed is None or child in allowed)

def attribute_exception(query,key,required,observed):
    if key=='prepared' and required=='cooked' and observed in ('raw',None) and query.family in ('meat','produce','beans','legume','pasta','rice') and query.treatment is None:return 'kitchen_cooking'
    if key=='fat_level' and required=='low_fat' and observed in ('1%','2%') and query.family=='dairy' and query.subfamily=='milk':return 'verified_lower_fat_milk'
    if key=='flavor' and required=='plain' and observed is None and query.family=='dairy' and query.subfamily=='milk':return 'plain_milk_identity'
    if key=='salt_level' and required=='low_sodium' and observed=='unsalted':return 'verified_no_added_salt'
    return None

def attribute_trace(query,product):
    return {key:{'required':getattr(query,key),'observed':getattr(product,key),'evidence':required_evidence(getattr(query,key),getattr(product,key)).value,'policy_exception':attribute_exception(query,key,getattr(query,key),getattr(product,key))} for key in REQUIRED_ATTRIBUTES if getattr(query,key) is not None}

# A bounded compositional grammar for an explicit terminal derived head. It
# never infers a base identity from embeddings or creates an identity for X
# whose taxonomy is unknown. Known purchased identities take precedence.
DERIVED_HEAD_PATTERN=re.compile(r'^(.+?)\s+(juice|sauce|spread|soup|cereal|pastry|chips|snack|drink|seasoning|entree)$')
def derived_parts(text):
    match=DERIVED_HEAD_PATTERN.fullmatch(text)
    if match and re.search(r'\b(?:to|for|from|with|and|or|in)\b',match.group(1)):return None
    return match.groups() if match else None

PURCHASED_COMPOUND_HEADS=(
    ('dessert','ice_cream',r'\bice cream\b'),
    ('chips','rice_snack',r'\brice snaps?\b'),
    ('prepared_side','side_dish',r'\bside dish(?:es)?\b'),
    ('alcohol','liqueur',r'\bliqueurs?\b'),
    ('chips','rice_cake',r'\brice cakes?\b'),
    ('prepared_side','potato_mash',r'\bmashed potatoes\b'),
    ('creamer','generic',r'\b(?:coffee |dairy )?creamer\b'),
    ('corn','creamed',r'\bcream(?:ed)?(?: style)? corn\b'),
)
def purchased_compound_head(text):
    # An explicit purchased noun outranks a dairy component/texture modifier.
    # Covers the class of cream-containing prepared foods, not a brand or SKU.
    if re.search(r'\bcream(?:y)?\b',text):
        for head,pattern in (
            ('soup',r'\bsoups?\b'), ('noodle_meal',r'\b(?:ramen|noodles?|pasta)\b'),
            ('cracker',r'\bcrackers?\b'), ('cookie',r'\b(?:cookies?|biscuits?)\b'),
            ('cake',r'\b(?:cakes?|pastries)\b'), ('snack',r'\b(?:snacks?|chips?)\b')):
            if re.search(pattern,text):return 'prepared',head,text
        if re.search(r'\bcream flavou?red\b',text):return 'prepared','flavored_food',text
    for family,subfamily,pattern in PURCHASED_COMPOUND_HEADS:
        match=re.search(pattern,text)
        if match:return family,subfamily,match.group()
    return None


def verified_whole_produce_base(identity):
    """Unknown form can supply spears only with an affirmative simple food head.

    Explicit whole/spear forms bypass this check. Unexplained nominal tokens
    are not brand evidence; the ontology already strips verified brand text.
    """
    text=identity.normalized_text
    text=re.sub(r'\b(?:fresh|organic|large|small|ripe|whole|fruit|fruits|oz|lb|lbs|kg|g|each)\b|[0-9]+',' ',text)
    head=(identity.subfamily or '').replace('_',' ')
    text=re.sub(rf'\b{re.escape(head)}s?\b',' ',text)
    return not text.strip()
