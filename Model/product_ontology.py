"""Deterministic ingredient/product identities and a precision-first purchase gate.

Unknown evidence stays unknown. Embeddings, brands, price and package quantities
cannot establish identity or override an incompatible required attribute.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
import re, unicodedata
from ingredient_normalization import parse_ingredient, contextual_ingredient_text
from food_identity_rules import (FOUNDATION_HEADS, BASIC_COMPOUNDS, COMPOSITE_MARKERS,
    KITCHEN_FORMS, CUTTABLE_FAMILIES, head_identity, purchased_identity, normalize_food_words, query_branches, final_identity, PURCHASED_FINAL_FAMILIES, strip_final_head, micro_identity, strip_micro_head, precision_identity, strip_precision_head, purchased_specificity, domain_evidence)

from structural_identity_policy import (Evidence, REQUIRED_ATTRIBUTES, identity_form, semantic_head, required_evidence, generic_child, attribute_exception, derived_parts, purchased_compound_head, verified_whole_produce_base)

ONTOLOGY_VERSION = 'food-identity-v3.13'

@dataclass(frozen=True)
class FoodIdentity:
    alternatives: tuple[FoodIdentity, ...] = ()
    absence_claims: tuple[str, ...] = ()
    head: str | None = None
    domain: str = 'food'
    grade: str | None = None
    ripeness: str | None = None
    packing_medium: str | None = None
    treatment: str | None = None
    family: str | None = None
    subfamily: str | None = None
    canonical: str | None = None
    species: str | None = None
    cut: str | None = None
    form: str | None = None
    state: str | None = None
    fat_level: str | None = None
    salt_level: str | None = None
    sweetness: str | None = None
    flavor: str | None = None
    bone: str | None = None
    skin: str | None = None
    prepared: str | None = None
    dietary_identity: str | None = None
    variety: str | None = None
    brand: str | None = None
    dietary_requirements: tuple[str, ...] = ()
    purchase_variants: tuple[str, ...] = ()
    ambiguous: bool = False
    normalized_text: str = ''
    evidence: tuple[str, ...] = ()

    @property
    def semantic_head(self):return semantic_head(self)

    @property
    def identity_form(self):return identity_form(self)

    def to_dict(self):
        value=asdict(self);value.update(semantic_head=self.semantic_head,identity_form=self.identity_form)
        return value

@dataclass(frozen=True)
class IdentityDecision:
    match_type: str
    reasons: tuple[str, ...]
    uncertain: tuple[str, ...] = ()

    @property
    def allowed(self): return self.match_type in ('exact', 'equivalent')


def norm(text):
    text=re.sub(r'[-‐‑‒–—]', ' ', str(text or ''))
    text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().lower()
    text=text.replace('&',' and ').replace('percent','%')
    text=re.sub(r'(?<=[a-z])(?=[0-9])|(?<=[0-9])(?=[a-z])',' ',text)
    text=normalize_food_words(text)
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9%\s-]',' ',text)).strip()

@lru_cache(maxsize=512)
def regex(pattern): return re.compile(pattern)
def has(text,pattern): return bool(regex(pattern).search(text))

CHEESES = (
 ('cream_cheese',r'cream cheese'),('cottage_cheese',r'cottage cheese'),
 ('monterey_jack',r'monterey jack'),('pepper_jack',r'pepper jack|3 pepper.*jack'),
 ('colby_jack',r'colby jack'),('queso_fresco',r'queso fresco'),
 ('goat_cheese',r'goat(?:s)? cheese|chevre'),('blue_cheese',r'blue cheese|gorgonzola|roquefort|stilton'),
 ('parmesan',r'parmesan|parmigiano(?: reggiano)?'),('pecorino',r'pecorino|romano'),
 ('mozzarella',r'mozzarella|mozzarela'),('cheddar',r'cheddar'),('ricotta',r'ricotta'),
 ('swiss',r'swiss cheese'),('emmental',r'emmental'),('gruyere',r'gruyere'),('grana_padano',r'grana padano'),('provolone',r'provolone'),('gouda',r'gouda'),
 ('brie',r'brie'),('burrata',r'burrata'),('mascarpone',r'mascarpone'),
 ('neufchatel',r'neufchatel'),('feta',r'feta'),('colby',r'colby'),
 ('american',r'american (?:cheese|singles)|kraft singles'),('havarti',r'havarti'),
 ('asiago',r'asiago'),('fontina',r'fontina'),('munster',r'muenster|munster'),
)
SPECIES = (('chicken',r'chicken|chkn'),('turkey',r'turkey'),('beef',r'beef|rib ?eye|sirloin|filet mignon|new york strip|hamburger meat|hanger steak|skirt steak|flank steak|chuck roast|round steak|round roast|fillet beef'),
 ('pork',r'pork|bacon|prosciutto|ham'),('lamb',r'lamb'),('duck',r'duck'),('veal',r'veal'))
CUTS = (
 ('corned',r'corned beef'),('bacon',r'bacon'),('ham',r'\bham\b|prosciutto'),
 ('belly',r'belly'),('liver',r'liver'),('hock',r'hocks?'),('tongue',r'tongue'),
 ('ground',r'ground|hamburger meat|minced (?:beef|pork|chicken|turkey|lamb)'),
 ('ribeye',r'rib ?eye'),('tenderloin',r'tenderloin|filet mignon|fillet beef'),
 ('sirloin',r'sirloin'),('strip',r'new york strip|strip steak'),('flank',r'flank'),
 ('hanger',r'hanger'),('skirt',r'skirt'),('chuck',r'chuck'),('shoulder',r'shoulder|boston butt|pork butt'),
 ('shank',r'shank|hindshank'),('chop',r'chops?'),('loin',r'loin'),('round',r'round'),('brisket',r'brisket'),('stew',r'stew'),
 ('breast',r'breasts?|tenders?'),('thigh',r'thighs?'),('wing',r'wings?'),
 ('drumstick',r'drumsticks?'),('whole',r'whole (?:chicken|turkey)|cornish hen'),
 ('chop',r'chops?'),('ribs',r'ribs?|spare ?ribs?'),('steak',r'steak'),('roast',r'roast'),
)
PLANTS = (
 ('plant_milk','almond',r'almond ?milk'),('plant_milk','oat',r'oat ?milk'),
 ('plant_milk','soy',r'soy ?milk'),('plant_milk','coconut',r'coconut milk'),
 ('plant_butter','plant',r'vegan butter|plant butter|plant[- ]based.*(?:spread|butter)'),
 ('plant_yogurt','plant',r'(?:almond|coconut|soy|oat|vegan|plant based).*yogurt'),
 ('plant_cheese','plant',r'vegan.*cheese|plant[- ]based.*cheese|dairy[- ]free.*cheese'),
)
# Prepared products containing an ingredient are not that ingredient. Foundation
# products such as broth, nut butter, tomato sauce and bread are handled below.
PREPARED = r'\b(?:crackers?(?! barrel)|cookies?|pizza|sandwich|nuggets?|breaded|entrees?|dinners?|meal kits?|(?<!whole )meals?|lemon curd|lime curd|salami|pepperoni|bologna|pastrami|hash|chipped beef|'
PREPARED += r'soup|salad|icing|frosting|cake|pies?|muffins?|waffles?|pancakes?|pancake mix|'
PREPARED += r'franks|frankfurters?|hot dogs?|sausages?|jerky|parmesan entree|cordon bleu|'
PREPARED += r'rotisserie|ready to eat|fully cooked|chicken parmesan|marinated|seasoned|glazed|'
PREPARED += r'cheese filled|butter chicken|simmer sauce|mac and cheese|macaroni and cheese)\b'
PREPARED += r'|\b(?:breadcrumbs?|matzos?|pretzels?|cereal|chips|bread|store prepared|grilled|cheese sauce|cheese dip|pudding)\b'
PREPARED += r'|\b(?:dressing|tartes?|hummus|corn ?bread|rolls?|dip|ravioli|pouch|wraps?|granola bars?|protein bars?|couscous mix|rice cups?|blintzes|crepes|stuffed|pierogi|pasteles|gravy|kits?|breakfast bars?|snack bars?|biscuits?|tortillas?|in sauce|milk singles|tea|bagels?|mints|gelato|mint chip|sparkling water|(?<!baking )soda|lemonade|juice drink|(?<!seasoning )blend|potstickers?|dumplings?|gerber|2nd foods|baby food|beech[- ]nut|fruit snacks|coffee creamer|rice sides|beverages?|drinks?|mix(?:es)?|corn dogs?|candy|chocolate covered|chocolate with|petroleum jelly|cocoa butter|steak sauce|egg substitute|egg beaters|liquid egg|pickles?|pickled|rings|crisps|yogurt drink|marinade|ready[- ]to[- ]eat|braised|deli|lunch meat|roast beef|meatballs?|burgers?|marrow bones|beef stew with)\b'
PREPARED += r'|\bqueso\b(?! (?:fresco|blanco))|\bcheesecakes?\b|\bmozzarella sticks\b|\bfrench fries\b|\bice cream\b|\bmilk chocolate\b|\bchocolate milk\b'
NONFOOD = r'\b(?:dog food|cat food|dog treats?|cat treats?|pet food|purina|friskies|fancy feast|'
NONFOOD += r'(?:trash|garbage|drawstring|kitchen) bags?|graters?|cutlery|utensils?|(?:pasta|roasting|baking|cooking) pans?|sugar dispensers?|rice serving bowls?|cleaners?|polish|metal care|copper cream|silver cream|furniture care|cosmetics?|face cream|hand cream|skin cream|supplements?|conditioner|dental floss|floss|wipes|milk[- ]bone|vaseline|lotion|biscuits.*beef flavor|toothpaste|shampoo|soap|detergent|tissues?|paper towels?|mouthwash)\b'

# Canonical aliases are general food identities, not recipe exceptions.
FOUNDATIONS = (
 ('broth','broth',r'broth|stock|consomme'),
 ('tomato','paste',r'tomato paste'),('tomato','puree',r'tomato puree'),
 ('tomato','sauce',r'tomato sauce'),('tomato','diced',r'diced tomatoes|tomatoes diced'),
 ('tomato','crushed',r'crushed tomatoes|tomatoes crushed'),('tomato','sun_dried',r'sun dried tomatoes'),
 ('tomato','whole',r'(?:whole|peeled).*tomatoes|tomatoes.*(?:whole|peeled)'),
 ('tomato','pasta_sauce',r'pasta sauce|spaghetti sauce|marinara'),
 ('dairy','condensed_milk',r'condensed.*milk'),('dairy','evaporated_milk',r'evaporated.*milk'),
 ('dairy','powdered_milk',r'dry milk|powdered milk|milk powder'),('dairy','buttermilk',r'buttermilk'),
 ('dairy','heavy_cream',r'heavy.*cream|whipping cream|double cream'),('dairy','half_and_half',r'half[- ]and[- ]half'),
 ('dairy','light_cream',r'light cream'),('dairy','sour_cream',r'sour cream'),
 ('dairy','yogurt',r'yogurt|yoghurt'),('dairy','cream',r'cream'),('dairy','milk',r'milk'),
 ('nut_butter','peanut',r'peanut butter'),('nut_butter','almond',r'almond butter'),
 ('nut_butter','cashew',r'cashew butter'),('seed_butter','sunflower',r'sunflower.*butter|sunbutter'),
 ('dairy','butter',r'butter'),('fat','margarine',r'margarine|vegetable oil spread|buttery spread'),
 ('flour','almond',r'almond flour'),('flour','coconut',r'coconut flour'),
 ('flour','self_rising',r'self rising flour'),('flour','bread',r'bread flour'),
 ('flour','cake',r'cake flour'),('flour','whole_wheat',r'whole wheat flour'),
 ('flour','rice',r'rice flour'),('flour','corn',r'(?:instant )?corn (?:masa )?flour|masa harina|masa flour'),
 ('flour','all_purpose',r'all purpose flour|all-purpose flour|plain flour|ap flour|flour'),
 ('starch','corn',r'corn starch|cornstarch'),('starch','potato',r'potato starch'),
 ('starch','tapioca',r'tapioca starch'),('grain','cornmeal',r'corn ?meal'),
 ('sugar','powdered',r'powdered sugar|confectioners.*sugar|icing sugar'),
 ('sugar','brown',r'brown sugar'),('sugar','granulated',r'granulated sugar|white sugar|cane sugar|sugar'),
 ('sweetener','honey',r'honey'),('sweetener','maple_syrup',r'maple syrup'),
 ('fat','olive_oil',r'olive oil'),('fat','canola_oil',r'canola oil|rapeseed oil'),
 ('fat','vegetable_oil',r'vegetable oil'),('fat','coconut_oil',r'coconut oil'),
 ('fat','sesame_oil',r'sesame oil'),('fat','sunflower_oil',r'sunflower oil'),
 ('fat','corn_oil',r'corn oil'),('fat','peanut_oil',r'peanut oil'),
 ('rice','brown',r'brown rice'),('rice','arborio',r'arborio'),('rice','basmati',r'basmati'),
 ('rice','jasmine',r'jasmine'),('rice','white',r'white rice|long grain rice|rice'),
 ('pasta','spaghetti',r'spaghetti|spaghettini'),('pasta','penne',r'penne'),('pasta','macaroni',r'macaroni|elbow'),
 ('pasta','lasagna',r'lasagna'),('pasta','fusilli',r'fusilli|rotini'),('pasta','generic',r'pasta|noodles'),
 ('beans','black',r'black beans'),('beans','kidney',r'kidney beans'),('beans','pinto',r'pinto beans'),
 ('beans','chickpeas',r'chickpeas?|garbanzo'),('beans','white',r'white beans|cannellini|navy beans|great northern'),
 ('beans','green',r'green beans|string beans'),('legume','split_peas',r'split peas'),
 ('legume','lentils',r'lentils'),('eggs','whole',r'eggs?'),
 ('produce','onion',r'onions?'),('produce','scallion',r'scallions?|green onions?|spring onions?'),
 ('produce','garlic',r'garlic'),('produce','lemon',r'lemons?'),('produce','lime',r'limes?'),
 ('produce','spinach',r'spinach'),('produce','basil',r'basil'),('produce','parsley',r'parsley'),
 ('produce','cilantro',r'cilantro|coriander leaves'),('produce','carrot',r'carrots?'),
 ('produce','celery',r'celery'),('produce','tomato',r'tomatoes|tomato'),
 ('produce','potato',r'potatoes|potato'),('produce','sweet_potato',r'sweet potatoes|sweet potato'),
 ('produce','cucumber',r'cucumbers?'),('produce','banana',r'bananas?'),('produce','apple',r'apples?'),
 ('produce','bell_pepper',r'bell peppers?|green peppers?'),('produce','chili_pepper',r'chil[l]?ies|chili peppers?|jalapeno|serrano'),
 ('produce','zucchini',r'zucchini|courgette'),('produce','summer_squash',r'summer squash|yellow squash'),
 ('produce','butternut_squash',r'butternut squash'),('produce','broccoli',r'broccoli'),
 ('produce','cabbage',r'cabbage'),('produce','mushroom',r'mushrooms?'),('produce','lettuce',r'lettuce'),
 ('nuts','peanut',r'peanuts?'),('nuts','almond',r'almonds?'),('nuts','walnut',r'walnuts?'),
 ('nuts','pecan',r'pecans?'),('nuts','cashew',r'cashews?'),('nuts','coconut',r'coconut'),
 ('seasoning','white_pepper',r'white pepper'),('seasoning','black_pepper',r'black pepper|peppercorns'),
 ('seasoning','paprika',r'paprika'),('seasoning','cumin',r'cumin'),('seasoning','cinnamon',r'cinnamon'),
 ('seasoning','oregano',r'oregano'),('seasoning','thyme',r'thyme'),('seasoning','salt',r'salt'),
 ('leavener','baking_powder',r'baking powder'),('leavener','baking_soda',r'baking soda|bicarbonate'),
 ('sauce','tamari',r'tamari'),('sauce','soy_sauce',r'soy sauce'),('sauce','mayonnaise',r'mayonnaise|mayo'),
 ('sauce','mustard',r'mustard'),('sauce','ketchup',r'ketchup'),
 ('olive','generic',r'olives?'),('acid','vinegar',r'vinegar'),('juice','lemon',r'lemon juice'),('juice','lime',r'lime juice'),
 ('corn','creamed',r'cream(?:ed)?[- ](?:style )?corn|corn.*cream[- ]style'),('corn','kernels',r'corn kernels|sweet corn|whole kernel corn|corn'),
 ('grain','oats',r'oats|oatmeal'),('water','water',r'water'),
)
# Longest specific identities win over generic tokens, e.g. green onion vs onion.
# Declaration order is intentional: specific nouns precede generic heads.
FOUNDATIONS = ((
 ('produce','scallion',r'scallions?|green onions?|spring onions?'),
 ('produce','sweet_potato',r'sweet potatoes|sweet potato'),
 ('acid','vinegar',r'(?:rice|apple cider|balsamic|red wine|white wine) vinegar'),
 ('herb','kaffir_lime',r'kaffir lime leaves|lime leaves'),
 ('produce','butternut_squash',r'butter ?nut squash'),
 ('flour','gluten_free',r'gluten[- ]free.*flour'),
 ('produce','chili_pepper',r'hot peppers?'),
 ('produce','ginger',r'ginger(?: root)?'),('produce','eggplant',r'eggplants?|aubergine'),
 ('produce','cauliflower',r'cauliflower'),('produce','avocado',r'avocados?'),
 ('produce','blueberry',r'blueberries|blueberry'),('produce','strawberry',r'strawberries|strawberry'),
 ('produce','cranberry',r'cranberries|cranberry'),('produce','peas',r'peas'),
 ('seasoning','rosemary',r'rosemary'),('produce','chives',r'chives'),
 ('tortilla','corn',r'corn tortillas?'),('sweetener','corn_syrup',r'corn syrup'),
 ('seasoning','garlic_powder',r'garlic powder|granulated garlic'),
 ('seasoning','onion_powder',r'onion powder|granulated onion'),
 ('seasoning','garlic_salt',r'garlic salt'),('seasoning','celery_salt',r'celery salt'),
 ('seasoning','chili_powder',r'chili powder'),('seasoning','curry_powder',r'curry powder'),
 ('seasoning','cayenne',r'cayenne(?: pepper)?'),('seasoning','lemon_pepper',r'lemon pepper(?: seasoning)?'),
 ('syrup','vanilla',r'vanilla syrup'),('extract','vanilla',r'vanilla extract'),
 ('starch','corn',r'cornflour'),
 ('juice','orange',r'orange juice'),('juice','apple',r'apple juice|juice.*apple'),
 ('juice','carrot',r'carrot juice'),
 ('sauce','mustard_seed',r'mustard seeds?'),('sauce','mustard_powder',r'mustard powder'),
 ('olive','kalamata',r'kalamata olives'),('olive','green',r'green olives'),('olive','black',r'black olives'),
 ('produce','arugula',r'arugula|rockets?'),('produce','pineapple',r'pineapple'),
 ('dairy','creme_fraiche',r'creme fraiche'),('dairy','skyr',r'skyr'),('dairy','kefir',r'kefir'),
 ('produce','mint',r'mint(?: leaves)?'),
 ('sauce','sweet_chili',r'sweet chil[l]?i(?: hot)? sauce'),
 ('sauce','sriracha',r'sriracha'),('sauce','chili',r'chili sauce|chilli sauce'),
 ('fruit_preserve','applesauce',r'applesauce|apple sauce'),

 ('legume','red_lentils',r'red lentils'),('legume','green_lentils',r'green lentils'),('legume','brown_lentils',r'brown lentils'),
 ('leavener','active_yeast',r'active dry yeast'),('leavener','instant_yeast',r'instant yeast|rapid rise yeast'),('leavener','nutritional_yeast',r'nutritional yeast'),
 ('pastry','puff',r'puff pastry|sheets pastry dough'),
 ('seasoning','dried_basil',r'dried basil'),
 ('seasoning','dried_parsley',r'dried parsley'),
 ('juice','lemon',r'lemon juice|juice of.*lemon'),('juice','lime',r'lime juice|juice of.*lime'),
) + FOUNDATIONS)


def describe(text, *, feature=None, product=False):
    feature=feature or {}
    raw=norm(text)
    if not product:
        raw=re.sub(r"\bpeppeer\b","pepper",raw)
        raw=re.sub(r"\bcinamon\b","cinnamon",raw)
        raw=re.sub(r"\bgingerroot\b","ginger root",raw)
        raw=re.sub(r"\bnut meats\b","nuts",raw)
        raw=re.sub(r"\btoast\b","bread",raw)
    if not product and has(raw,r'\b(?:cooking (?:liquor|liquid)|(?:liquor|liquid) from (?:the )?(?:salmon|chicken|beef|fish|pork))\b'):
        return FoodIdentity(normalized_text=raw,evidence=('unverified_cooking_liquid_head',))
    if not product:
        # Negative/open-ended substitution notes are not positive identities.
        # In exact shopping mode retain the named primary ingredient instead of
        # interpreting e.g. 'non-balsamic' as permission to purchase balsamic.
        raw=re.sub(r'\bor (?:any )?(?:non\b|not\b|anything but\b|other than\b|except\b).*$', '', raw).strip()
        # Quantity/preparation notes are not food alternatives.
        raw=re.sub(r'\bor (?:more as needed|enough to moisten|can)\b.*$','',raw).strip()
        raw=re.sub(r'\bor other (?:toppings|dried fruit)\b.*$','',raw).strip()
        if has(raw,r'mixed(?: diced|chopped|cut)? vegetables'):raw=norm(re.sub(r'\([^)]*\)','',str(text)))
        if re.search(r'^\s*(?:for the|for)\s+[^:]+:\s*$',str(text),re.I) or str(text).strip().endswith(':'):raw='unverified section heading'
        if has(raw,r'\bpasta\b') and has(raw,r'\bspaghetti\b'):raw=re.split(r'\bwill work\b',raw,maxsplit=1)[0].replace('any other long noodle','spaghetti')
        # Slash-separated food options must never silently select a component.
        compound_options=bool('/' in str(text) and has(raw,r'\boption\b'))
        component_note=re.search(r'\(([^)]*)\)',str(text))
        specific_mix=bool(has(norm(text),r'mixed(?: diced|chopped|cut)? vegetables') and component_note and len(re.findall(r'beans?|carrots?|peas|celery|broccoli|corn',component_note.group(1),re.I))>1)
    if not product:
        # Post-purchase cutting instructions cannot introduce OR identities.
        raw=re.split(r'\bcut into\b',raw,maxsplit=1)[0].strip()
    if not product:
        if has(raw,r'\bdressing\b') and has(raw,r'\bor\b') and not has(re.split(r'\bor\b',raw,maxsplit=1)[0],r'\bdressing\b'):
            return FoodIdentity(normalized_text=raw,ambiguous=True,evidence=('unresolved_compound_dressing_scope',))
        branches=query_branches(raw)
        if branches:
            identities=tuple(describe(branch) for branch in branches)
            # A shared required modifier must not disappear on an OR branch.
            # Until scope is explicit, asymmetric purchase attributes abstain.
            material=('state','fat_level','salt_level','sweetness','bone','skin','ripeness','packing_medium','treatment','dietary_requirements','purchase_variants')
            scoped=any(len({getattr(i,key) for i in identities})>1 and any(getattr(i,key) in (None,()) for i in identities) for key in material)
            if len({i.family for i in identities})>1 and re.search(r'\bor\s+\d',raw):scoped=False
            if len({i.family for i in identities})>1 and any(i.form in ('powdered','ground') for i in identities):scoped=False
            if all(i.family and not i.ambiguous for i in identities) and not scoped:
                return replace(identities[0], alternatives=identities, normalized_text=raw, evidence=identities[0].evidence+('explicit_query_alternatives',))
            return replace(identities[0], ambiguous=True, normalized_text=raw)
    compound_query=False
    if not product and has(raw,r'\band\b'):
        parts=re.split(r'\band\b',raw,maxsplit=1)
        identities=[describe(part) for part in parts]
        keys=('family','subfamily','species','cut')
        compound_query=all(i.family for i in identities) and any(getattr(identities[0],key)!=getattr(identities[1],key) for key in keys)
    parsed=None if product else parse_ingredient(text)
    # Preserve original identity evidence: legacy normalization removes cut/form
    # words. Remove only the alternate branch, not explicit fat/salt/style words.
    detection=raw if product else re.split(r'\bor\b',norm(contextual_ingredient_text(raw)),maxsplit=1)[0]
    if not product:
        detection=detection.replace('for stew','stew')
        if has(raw,r'\bsteak\b') and has(detection,r'\b(?:round|flank|skirt)\b') and not has(detection,r'beef|pork|chicken|lamb|veal'):detection+=' steak'
        detection=re.split(r'\b(?:for|to serve|cut into|such as|optional)\b',detection,maxsplit=1)[0].strip()
    elif feature.get('brand'):
        detection=re.sub(rf'\b{re.escape(norm(feature["brand"]))}\b',' ',detection).strip()
    if product:
        # Company names may contain a spice/food noun even when brand metadata
        # is absent. A marked company prefix is not the purchased food head.
        detection=re.sub(r'^(?:the )?[a-z ]+ (?:spice company|foods company)\b',' ',detection).strip()
    if not product and detection=='vanilla':detection='vanilla extract'
    # Quantity context resolves the common pepper alias, not meat species/cuts.
    if not product and has(detection,r'\bpepper\b') and not has(detection,r'black|white|cayenne|bell|green|red|jalapeno|serrano|lemon|hot'):
        if has(detection,r'\b(?:tsp|teaspoons?|tbsp|tablespoons?|ground|grains?|pinch|speck)\b') or detection=='pepper':detection+=' black pepper'
        else: detection+=' bell pepper'
    from absence_claims import separate_absence_claims
    claim_text = detection
    detection, absence_claims = separate_absence_claims(detection)
    values={'absence_claims':absence_claims,'normalized_text':claim_text,'brand':feature.get('brand') if product else parsed.brand}
    evidence=[]
    def set_identity(family,subfamily,species=None,cut=None):
        values.update(family=family,subfamily=subfamily,canonical=f'{family}:{subfamily}',species=species,cut=cut,head=(cut or subfamily).replace('_',' '))
        evidence.append(f'name_identity:{family}:{subfamily}')
    if not product and has(detection,r'\bsour cream dressing\b'):detection=detection.replace('sour cream dressing','sour cream')
    beverage = None
    if has(detection, r'\bcola\b'):
        beverage = ('beverage', 'cola', 'cola')
    elif has(detection, r'\b(?:soft drink|soda)\b') and not has(detection, r'\bbaking soda\b'):
        beverage = ('beverage', 'soda', 'soda')
    elif has(detection, r'\bbeverages?\b|(?<!to )(?<!can )\bdrinks?\b(?! (?:it|them)\b)'):
        beverage = ('beverage', 'drink', 'drink')
    precision=beverage or purchased_compound_head(detection) or precision_identity(detection)
    if product and precision and precision[:2]==('extract','vanilla') and not has(detection,r'vanilla (?:extract|essence)'):
        precision=('prepared','unverified_flavor_head','vanilla')
    micro=micro_identity(detection)
    outer=precision or micro or final_identity(detection)
    compound=outer or head_identity(detection)
    purchased=outer if outer and outer[0] in (PURCHASED_FINAL_FAMILIES | {'bread','chips','cracker','pickle','syrup','cereal','pastry','beverage'}) else purchased_identity(detection)
    ready=purchased[:2] if outer and purchased else None
    if not ready and has(detection,r'potato pancake mix'):ready=('baking_mix','potato_pancake')
    elif not ready and has(detection,r'pancake mix'):ready=('baking_mix','pancake')
    elif not ready and has(detection,r'cream of chicken soup'):ready=('soup','cream_chicken')
    elif not ready and has(detection,r'tomato soup'):ready=('soup','tomato')
    elif not ready and has(detection,r'corn tortillas?'):ready=('tortilla','corn')
    elif not ready and has(detection,r'(?:whole wheat|wheat|flour).*tortillas?'):ready=('tortilla','flour')
    elif not ready and has(detection,r'pita breads?'):ready=('bread','pita')
    elif not ready and has(detection,r'\bhummus\b'):
        ready=('dip','hummus')
    elif not ready and has(detection,r'\b(?:bread ?crumbs?|panko)\b'):ready=('breadcrumbs','plain')
    elif has(detection,r'beef.*sausage|sausage.*beef'):ready=('sausage','beef')
    elif has(detection,r'pork.*sausage|sausage.*pork'):ready=('sausage','pork')
    if ready:
        # A requested ready ingredient still cannot be a component of a snack.
        remainder=re.sub(r'potato pancake mix|pancake mix|cream of chicken soup|tomato soup|corn tortillas?|(?:whole wheat|wheat|flour).*?tortillas?|pita breads?|hummus|bread ?crumbs?|panko|sausages?',' ',detection)
        if has(remainder,PREPARED):ready=None
    if not ready and purchased:ready=purchased[:2]
    residual=re.sub(BASIC_COMPOUNDS,' ',detection)
    if has(detection,r'(?:vegan|plant) butter'):residual=re.sub(r'plant based oil spread|\bspread\b',' ',residual)
    if precision:residual=strip_precision_head(residual,*precision[:2])
    if micro:residual=strip_micro_head(residual,*micro[:2])
    if outer:
        residual=strip_final_head(residual,*outer[:2])
        if outer[0]=='beans':residual=re.sub(r'\bseasoned\b',' ',residual)
    if compound:residual=re.sub(re.escape(compound[2]),' ',residual)
    if ready and purchased:
        residual=re.sub(re.escape(purchased[2]),' ',residual)
    # Purchased foods still cannot be components of a different composite head.
    composite=has(detection,r'\bbaked(?: black|red|kidney|pinto)? beans\b') or has(residual,COMPOSITE_MARKERS) or (has(residual,PREPARED) and not ready)
    if ready and purchased and (has(residual,COMPOSITE_MARKERS) or has(residual,PREPARED)):ready=None;composite=True
    if ready and has(detection,r'\bsauce\b') and ready[0] not in ('sauce','tomato'):
        ready=None;composite=True
    if ready and has(detection,r'\bjuice\b') and ready[0]!='juice' and not has(detection,r'(?:in|packed in)\s+(?:100\s*%\s*)?juice'):
        ready=None;composite=True
    nonfood_category=product and any(has(norm(feature.get(key)),r'\b(?:household|cleaning|nonfood|cosmetics|personal care|pet supplies|supplements)\b') for key in ('category','subcategory','record_status'))
    if has(detection,NONFOOD) or nonfood_category: set_identity('nonfood','nonfood');values['prepared']='nonfood'
    elif ready:set_identity(*ready);values['prepared']='prepared';values['head']=ready[1]
    elif not (outer and outer[0] in ('sauce','tomato')) and has(detection,r'\bsauce\b') and not has(detection,r'tomato sauce|pasta sauce|spaghetti sauce|marinara|soy sauce|tamari|sweet chil[l]?i(?: hot)? sauce|chili sauce|chilli sauce|sriracha|oyster sauce|hoisin sauce|worcestershire'):
        set_identity('prepared','prepared');values['prepared']='prepared'
    elif outer and outer[0]!='juice' and has(detection,r'\bjuice\b') and not has(detection,r'(?:in|packed in)\s+(?:100\s*%\s*)?juice'):
        set_identity('prepared','prepared');values['prepared']='prepared'
    elif product and not outer and norm(feature.get('category')) in ('prepared','snacks','bakery','baby') and not ready:
        set_identity('prepared','prepared');values['prepared']='prepared'
    elif composite: set_identity('prepared','prepared');values['prepared']='prepared'
    elif compound:
        set_identity(*compound[:2]);values['head']=compound[2]
        if compound[0]=='plant_cream':values['dietary_identity']='plant'
    elif has(detection,r'butter lettuce'):set_identity('produce','lettuce');values['variety']='butterhead'
    elif has(detection,r'butter ?nut squash'):set_identity('produce','butternut_squash')
    else:
        cheeses=[name for name,pattern in CHEESES if has(detection,rf'\b(?:{pattern})\b')]
        # Nested identities such as colby jack/colby are not ambiguous blends.
        if 'colby_jack' in cheeses and 'colby' in cheeses:cheeses.remove('colby')
        if has(detection,r'plant[- ]based|vegan|meatless') and any(has(detection,pattern) for _,pattern in SPECIES):
            species=next(name for name,pattern in SPECIES if has(detection,pattern))
            set_identity('plant_meat',species);values['dietary_identity']='plant'
        elif cheeses and has(claim_text,r'vegan|plant[- ]based|dairy[- ]free'):
            set_identity('plant_cheese',cheeses[0]);values['dietary_identity']='plant'
        elif cheeses:
            set_identity('cheese',cheeses[0]);values['ambiguous']=len(set(cheeses))>1
            values['dietary_identity']='dairy'
            if cheeses[0]=='mozzarella':
                if has(detection,r'\bfresh\b|fresca'):values['flavor']='fresh_mozzarella'
                elif has(detection,r'low moisture|low-moisture'):values['flavor']='low_moisture'
        else:
            found=False
            for family,species,pattern in PLANTS:
                if has(detection,rf'\b(?:{pattern})\b'):
                    set_identity(family,species);values['dietary_identity']='plant';found=True;break
            broth=has(detection,r'\b(?:broth|stock|consomme|bouill(?:on|an))\b')
            if not found and not broth:
                for species,pattern in [('salmon',r'salmon'),('tuna',r'tuna'),('cod',r'cod'),('tilapia',r'tilapia'),('haddock',r'haddock'),('trout',r'trout'),('shrimp',r'shrimp'),('crab',r'crab'),('lobster',r'lobster'),('clam',r'clams?'),('mussel',r'mussels?')]:
                    if has(detection,rf'\b(?:{pattern})\b'):
                        set_identity('shellfish' if species in ('shrimp','crab','lobster','clam','mussel') else 'fish',species,species)
                        values['dietary_identity']='animal';found=True;break
            broth=has(detection,r'\b(?:broth|stock|consomme|bouill(?:on|an))\b')
            if not found and not broth:
                species=next((name for name in ('chicken','turkey','beef','pork','lamb','duck','veal') if has(detection,rf'\b{name}\b')),None)
                if species is None:species=next((name for name,pattern in SPECIES if has(detection,rf'\b(?:{pattern})\b')),None)
                if species:
                    cut=next((name for name,pattern in CUTS if has(detection,rf'\b(?:{pattern})\b')),None)
                    set_identity('meat',species,species,cut);values['dietary_identity']='animal';found=True
            if not found:
                # Prefer the food noun appearing first, with declaration order
                # breaking ties for nested generic heads. Descriptive secondary
                # ingredients cannot replace the product's primary identity.
                matches=[]
                for order,(family,subfamily,pattern) in enumerate(FOUNDATIONS):
                    identity_text=re.sub(r'\blow[- ]sodium\b',' ',detection)
                    match=regex(rf'\b(?:{pattern})\b').search(identity_text)
                    if match:matches.append((match.start(),order,family,subfamily))
                if matches:
                    heads={'dairy','nut_butter','seed_butter','flour','starch','sauce','juice','acid','tomato','sweetener','syrup','fat','sugar','leavener','pasta','fruit_preserve','seasoning'}
                    head_matches=[m for m in matches if m[2] in heads]
                    _,_,family,subfamily=min(head_matches,key=lambda m:m[1]) if head_matches else min(matches)
                    set_identity(family,subfamily);found=True
                if broth:
                    set_identity('broth','bouillon' if has(detection,r'bouill(?:on|an)|granules|powder') else 'liquid')
                    values['species']=next((name for name,pattern in [('chicken',r'chicken|chkn'),('beef',r'beef'),('vegetable',r'vegetable|veggie'),('veal',r'veal'),('turkey',r'turkey'),('pork',r'pork'),('lamb',r'lamb'),('seafood',r'fish|seafood')]
                                           if has(detection,rf'\b(?:{pattern})\b')),None)
                if values.get('family')=='dairy':values['dietary_identity']='dairy'
    # An unrecognized juice derivative cannot inherit a basic ingredient head.
    if has(detection,r'\bjuice\b') and not has(detection,r'(?:in|packed in)\s+(?:100\s*%\s*)?juice') and values.get('family') not in ('juice','produce','prepared','nonfood'):
        set_identity('prepared','unverified_juice_head');values['prepared']='prepared'
    # Identity was established from positive evidence only. The original claims
    # remain available for required dietary/absence attributes.
    detection = claim_text
    # Explicit metadata is evidence; broad category alone cannot establish state.
    metadata_rules={'state':('freshness',{'fresh':'fresh','frozen':'frozen','canned':'canned','dried':'dried'}),
        'fat_level':('fat_level',{'nonfat':'skim','non-fat':'skim','fat-free':'skim','whole':'whole','2 percent':'2%','1 percent':'1%','low-fat':'low_fat'}),
        'bone':('bone_status',{'boneless':'boneless','bone-in':'bone_in'}),
        'skin':('skin_status',{'skinless':'skinless','skin-on':'skin_on'}),
        'salt_level':('salted_status',{'unsalted':'unsalted','salted':'salted','no-salt-added':'unsalted','reduced-sodium':'low_sodium'})}
    if product:
        for key,(source,mapping) in metadata_rules.items():
            observed=mapping.get(feature.get(source))
            if observed:values[key]=observed;evidence.append('explicit_metadata:'+source)
    # Specific material attributes; never infer a required attribute from silence.
    attribute_rules={
      'state':[('frozen',r'frozen'),('canned',r'canned|tinned|\bcans?\b'),('dried',r'dried|dry'),('fresh',r'fresh')],
      'form':[('spray',r'sprays?'),('powdered',r'powder|powdered|granules|granulated(?: garlic| onion)'),('belly',r'belly'),('liver',r'liver'),('hock',r'hocks?'),('tongue',r'tongue'),
 ('ground',r'ground'),('shredded',r'shredded'),('grated',r'grated'),('block',r'block'),('crumbled',r'crumbles?|crumbled'),('sliced',r'sliced|slices'),('sticks',r'sticks'),('spears',r'spears?'),('diced',r'diced'),('chopped',r'chopped|minced'),('whole',r'whole')],
      'bone':[('boneless',r'boneless'),('bone_in',r'bone[- ]in')],
      'skin':[('skinless',r'skinless'),('skin_on',r'skin[- ]on')],
      'salt_level':[('unsalted',r'unsalted|unslt|no salt added|salt free'),('low_sodium',r'low(?:er)?[- ]sodium|less[- ]sodium|reduced[- ]sodium'),('salted',r'(?<!un)salted')],
      'sweetness':[('unsweetened',r'unsweetened'),('sweetened',r'(?<!un)sweetened')],
    }
    for key,rules in attribute_rules.items():
        attribute_text=re.sub(r'whole (?:grain|wheat|meal)',' ',detection) if key=='form' else detection
        if key=='state' and not product:attribute_text=re.sub(r'\b(?:you|we|i|they) can\b',' ',attribute_text)
        if key=='state' and product:attribute_text=re.sub(r'\bfresh cut\b',' ',attribute_text)
        found={value for value,pattern in rules if has(attribute_text,rf'\b(?:{pattern})\b')}
        if key=='form' and len(found)>1 and values.get('family') in CUTTABLE_FAMILIES and found <= set(KITCHEN_FORMS):
            found={next(x for x in ('chopped','diced','grated','shredded','crumbled','sliced','chunks','wedges','spears') if x in found)}
        if len(found)==1:
            observed=found.pop()
            if key in values and values[key]!=observed:values['ambiguous']=True
            values[key]=observed
        elif len(found)>1:values['ambiguous']=True
    if values.get('family')=='meat' and values.get('cut')=='ground':
        values['form']='ground'
        # Ground is processing, not an anatomical cut. Keep both when named.
        anatomical=next((name for name,pattern in CUTS if name!='ground' and has(detection,rf'\b(?:{pattern})\b')),None)
        if anatomical:values['cut']=anatomical;values['head']=anatomical
    if product and values.get('family')=='produce' and values.get('subfamily') in ('parsley','basil','chives','mint') and has(detection,r'flakes|freeze[- ]dried'):
        values['state']='dried';values['form']='flakes'
    if product and values.get('family')=='produce' and values.get('subfamily') in ('onion','garlic') and not values.get('state'):
        source_aisles = re.sub(r'[-_]', ' ', ' '.join(str(x) for x in feature.get('source_categories', [])))
        if has(source_aisles, r'\bspices?\b|\bseasonings?\b') and has(detection, r'\b(?:minced|flakes|granulated|dehydrated)\b'):
            values['state']='dried'
            evidence.append('processed_allium_in_source_spice_aisle')
    if values.get('family')=='seasoning' and values.get('subfamily') in ('cumin','cinnamon','paprika','chili_powder','curry_powder','white_pepper','black_pepper','cayenne') and values.get('form')=='powdered':values['form']='ground'
    flavor=next((name for name in ('cherry','guava','acai','pineapple','mango','raspberry','lemon','coconut','coffee','honey','mixed berry','vanilla','strawberry','chocolate','banana','blueberry','peach','plain') if has(detection,rf'\b{name}\b')),None)
    if values.get('family')=='plant_milk':
        flavor=next((name for name in ('vanilla','chocolate','strawberry','coffee','honey','plain','coconut') if name!=values.get('subfamily') and has(detection,rf'\b{name}\b')),None)
    if flavor and values.get('family') in ('dairy','plant_yogurt','plant_milk','cheese','dessert'):values['flavor']=flavor
    if values.get('family') in ('dairy','plant_yogurt') and values.get('subfamily')=='yogurt':
        if has(detection,r'greek|strained'):values['subfamily']='greek_yogurt';values['canonical']=f"{values['family']}:greek_yogurt"
    fat=None
    if has(detection,r'fat[- ]free|non[- ]?fat|skim'):fat='skim'
    elif has(detection,r'whole[- ]milk|whole.*yogurt'):fat='whole'
    elif has(detection,r'2\s*%|two %'):fat='2%'
    elif has(detection,r'1\s*%|one %'):fat='1%'
    elif has(detection,r'low[- ]fat|lowfat|reduced[- ]fat|fat[- ]reduced|light butter|light mayonnaise'):fat='low_fat'
    if values.get('family') in ('cheese','plant_cheese'):
        if has(detection,r'fat[- ]free|non[- ]?fat'):fat='fat_free'
        elif has(detection,r'part[- ]skim'):fat='part_skim'
    if fat:
        if values.get('fat_level') and values['fat_level']!=fat:values['ambiguous']=True
        values['fat_level']=fat
    if values.get('family')=='meat' and values.get('form')=='ground':
        lean=regex(r'\b(\d{2})\s*%\s*lean').search(detection)
        if lean:values['fat_level']='lean_'+lean.group(1)
    if values.get('family')=='eggs':
        if has(detection,r'egg whites?'):values['subfamily']='whites';values['canonical']='eggs:whites'
        elif has(detection,r'egg yolks?'):values['subfamily']='yolks';values['canonical']='eggs:yolks'
    if not product and values.get('family') in ('corn','fish','shellfish','beans') and has(detection,r'\bcans?\b'):values['state']='canned'
    if values.get('family')=='fish' and has(detection,r'salt cod'):values['prepared']='cured'
    if values.get('family')=='dip':
        if has(detection,r'red pepper|garlic|jalapeno|spinach'):values['flavor']=next(x for x in ('red pepper','garlic','jalapeno','spinach') if has(detection,x))
    if values.get('prepared') is None:
        values['prepared']='cooked' if has(detection,r'\bcooked\b|hard[- ](?:cooked|boiled)|\broasted\b|\bsmoked\b') else 'raw' if values.get('family') in ('meat','fish','shellfish','eggs') else None
    if product and values.get('family')=='nut_butter' and has(detection,r'chocolate|\bcups?\b|protein|mush'):set_identity('prepared','prepared');values['prepared']='prepared'
    if product and values.get('family') in ('dairy','plant_milk') and has(detection,r'chocolate') and values.get('subfamily')=='milk':set_identity('prepared','prepared');values['prepared']='prepared'
    if values.get('family')=='produce' and has(detection,r'\bjuice\b') and not has(detection,r'(?:in|packed in)\s+(?:100\s*%\s*)?juice'):set_identity('juice',values['subfamily'])
    if product and values.get('family')=='juice':
        fruits={x for x in ('apple','orange','lemon','lime','carrot','beet','ginger','grape','pineapple') if has(detection,rf'\b{x}\b')}
        if len(fruits)>1:values['ambiguous']=True
    if values.get('family') in ('nuts','nut_butter') and has(detection,r'chocolate|\bcandy\b'):set_identity('prepared','prepared');values['prepared']='prepared'
    if product and values.get('family')=='produce' and has(detection,r'\bchocolate\b'):set_identity('prepared','chocolate_coated_produce');values['prepared']='prepared'
    if product and values.get('family')=='seasoning' and has(detection,r'multi grain|multigrain'):
        set_identity('prepared','unverified_multigrain_head');values['prepared']='prepared'
    if not product and has(raw,r'fresh or frozen|frozen or fresh') and not values.get('alternatives'):values['ambiguous']=True
    if values.get('family')=='produce' and values.get('subfamily')=='onion':
        variety=next((x for x in ('red','yellow','white','sweet') if has(detection,rf'\b{x}\b')),None)
        if variety:values['variety']=variety
    if values.get('family')=='produce' and values.get('subfamily')=='apple':
        variety=next((x for x in ('granny smith','golden delicious','red delicious','macintosh','fuji','gala') if has(detection,x)),None)
        if variety:values['variety']=variety
    if values.get('family') in ('bread','flour','grain','rice','tortilla') and has(detection,r'whole (?:meal|wheat|grain)') and values.get('form')=='whole':values['form']=None
    if values.get('family')=='nut_butter':
        if has(detection,r'chunky|crunchy|super ?chunk'):values['variety']='chunky'
        elif has(detection,r'creamy|smooth'):values['variety']='creamy'
    # Milk and seasoning powder are intrinsically forms, including common dry synonyms.
    if values.get('subfamily')=='powdered_milk':values['form']='powdered';values['state']='dried'
    if values.get('family')=='produce' and values.get('subfamily') in ('bell_pepper','chili_pepper'):
        color=next((x for x in ('green','red','yellow','orange') if has(detection,rf'\b{x}\b')),None)
        if color:values['variety']=color
    if values.get('family')=='produce' and values.get('subfamily')=='lettuce':
        variety=next((x for x in ('iceberg','romaine','butterhead','bibb') if has(detection,x)),None)
        if variety:values['variety']=variety
    if product and values.get('family')=='meat' and has(detection,r'store sliced|deli sliced|oven roasted'):values['prepared']='cooked'
    if values.get('family')=='produce' and values.get('subfamily')=='cabbage':
        color=next((x for x in ('red','green') if has(detection,rf'\b{x}\b')),None)
        if color:values['variety']=color
    if values.get('family')=='produce' and values.get('subfamily')=='tomato' and has(detection,r'\bcan(?:ned)?\b'):set_identity('tomato','whole')
    if values.get('family')=='tomato' and product:values.setdefault('state','canned')
    if values.get('family')=='meat' and values.get('cut') in ('bacon','ham','corned'):
        values['prepared']='raw' if has(detection,r'\b(?:uncooked|raw)\b') else 'cured'
    if values.get('family')=='juice' and has(detection,r'\bjuice\b') and has(detection,r'peel|zest|rind|outer scrapings'):values['ambiguous']=True
    dietary=[]
    for requirement in ('vegan','gluten free','lactose free','nut free'):
        if has(detection,rf'\b{requirement.replace(" ","[- ]")}\b'):dietary.append(requirement.replace(' ','_'))
    if product:
        for attr in feature.get('dietary_attributes',[]):
            a=norm(attr).replace('-',' ').replace(' ','_')
            if a in ('vegan','gluten_free','lactose_free','nut_free') and a not in dietary:dietary.append(a)
    if values.get('dietary_identity')=='plant' and has(detection,r'plant[- ]based|vegan') and 'vegan' not in dietary:dietary.append('vegan')
    if dietary:values['dietary_requirements']=tuple(sorted(dietary))
    if has(detection,r'all varieties|select varieties|\bor\b'):values['ambiguous']=True
    # Explicit product states remain unknown when inventory supplies no evidence.
    if values.get('family')=='produce' and values.get('subfamily')=='banana':
        if has(detection,r'\bgreen\b'):values['ripeness']='unripe'
        elif has(detection,r'\bripe\b'):values['ripeness']='ripe'
    if values.get('family')=='tomato' and has(detection,r'with.*(?:chili|chile|jalapeno)|tomatoes.*(?:chili|chile)'):values['flavor']='chili'
    if values.get('family') in ('meat','fish','sauce','bread','cracker','sausage','seed','grain','breadcrumbs','gelatin','dessert_mix'):
        flavors=[(m.start(),v) for v,p in [('honey',r'\bhoney\b'),('sweet',r'\bsweet\b'),('ranch',r'\branch\b'),('cinnamon',r'\bcinnamon\b'),('hot',r'\b(?:hot|spicy)\b'),('chocolate',r'\bchocolate\b'),('apple',r'\bapple\b'),('parmesan',r'\bparmesan\b'),('seasoned',r'\bseasoned\b'),('garlic',r'\bgarlic\b'),('lemon',r'\blemon\b'),('teriyaki',r'\bteriyaki\b'),('barbecue',r'\bbarbecue\b')] for m in regex(p).finditer(detection)]
        # The food-adjacent modifier takes precedence over earlier branding.
        if flavors:values['flavor']=max(flavors)[1]
    if values.get('family')=='sauce' and values.get('subfamily')=='sweet_chili' and values.get('flavor') in ('sweet','hot'):values['flavor']=None
    if values.get('family')=='sausage':
        values['dietary_identity']='animal'
        if values.get('subfamily')=='italian':values['prepared']='raw'
        if has(detection,r'vegan|plant based|vegetarian|meatless'):
            set_identity('plant_sausage',values['subfamily']);values['dietary_identity']='plant'
    if values.get('family')=='produce' and values.get('subfamily')=='lettuce' and has(detection,r'leaf lettuce|lettuce.*leaf'):values['variety']='leaf'
    if values.get('family')=='produce' and product and feature.get('base_unit')=='milliliter':
        set_identity('prepared','beverage');values['prepared']='prepared';evidence.append('liquid_packaging_or_beverage_category_conflict')
    if values.get('family')=='juice' and has(detection,r'freshly squeezed'):values['state']='fresh'
    if values.get('family') in ('fish','produce') and has(detection,r'(?:in|packed in) (?:100\s*%\s*)?(?:water|oil|juice)'):
        values['packing_medium']='juice' if has(detection,r'in (?:100\s*%\s*)?juice') else 'water' if has(detection,r'in water') else 'oil'
    if values.get('family') in ('meat','fish','shellfish','eggs','seed','nuts'):
        treatment=next((v for v,p in [('smoked',r'\bsmoked\b'),('uncured',r'\buncured\b'),('cured',r'\bcured\b'),('boiled',r'hard (?:boiled|cooked)'),('roasted',r'\broasted\b')] if has(detection,p)),None)
        if treatment:values['treatment']=treatment
    if values.get('family')=='produce' and values.get('subfamily')=='apple' and has(detection,r'\btart\b'):values['flavor']='tart'
    if values.get('family')=='plant_cream':values['prepared']=None
    if values.get('family')=='gelatin':
        flavored=has(detection,r'(?<!un)flavou?red|orange|cherry|lemon|lime|strawberry|raspberry')
        if flavored:set_identity('gelatin','flavored')
        dessert=has(detection,r'refrigerated|ready to eat|dessert')
        if dessert:set_identity('gelatin_dessert','flavored');values['prepared']='prepared'
        else:values['flavor']=None
    if values.get('family')=='dressing':
        values['flavor']=next((v for v in ('lemon poppy seed','poppy seed','ranch','balsamic','italian','caesar','french','thousand island','blue cheese','russian','lemon','honey mustard') if has(detection,rf'\b{v}\b')),None)
    if values.get('family')=='cereal' and has(detection,r'\bsquares?\b'):values['form']='squares'
    if values.get('family')=='dessert_mix':
        for flavor in ('lemon','vanilla','chocolate'):
            if has(detection,rf'\b{flavor}\b'):values['flavor']=flavor
    if values.get('family')=='produce' and values.get('subfamily')=='potato':
        potato_varieties={v for v,p in [('yukon_gold',r'yukon gold'),('russet',r'russet'),('red',r'\bred\b'),('yellow',r'\byellow\b'),('white',r'\bwhite\b')] if has(detection,p)}
        values['variety']='mixed' if len(potato_varieties)>1 else next(iter(potato_varieties),None)
    if values.get('family')=='olive' and has(detection,r'extra virgin'):
        values['ambiguous']=True;evidence.append('oil_grade_without_verified_oil_head')
    if values.get('family')=='meat' and has(detection,r'\bsalt pork\b'):
        values.update(species='pork',cut='belly',treatment='cured',prepared='cured',dietary_identity='animal')
    if (values.get('family')=='dressing' or values.get('family')=='dessert' and values.get('subfamily')=='whipped_topping') and has(detection,r'\b(?:light|lite)\b'):
        values['fat_level']='low_fat'
    if not product and has(detection,r'\bdressing\b') and has(detection,r'\bor\b') and values.get('family')!='dressing':
        values['ambiguous']=True;evidence.append('unresolved_compound_dressing_scope')
    if not product and values.get('family')=='produce' and values.get('subfamily')=='bell_pepper' and has(detection,r'\band\b') and len({c for c in ('green','red','yellow','orange') if has(detection,rf'\b{c}\b')})>1:
        values['ambiguous']=True;evidence.append('multiple_required_produce_colors')
    if product and values.get('family')=='seasoning' and values.get('subfamily')=='cinnamon' and has(detection,r'\b(?:apple|banana|berry|berries|peach|pear)\b'):
        values['ambiguous']=True;evidence.append('unverified_pure_spice_head')
    if product and values.get('family')=='produce' and values.get('subfamily')=='chili_pepper' and has(detection,r'\bcrushed\b'):
        values.update(state='dried',form='crushed');evidence.append('crushed_pepper_seasoning_form')
    if product and has(detection,r'\bfresh cut\b') and values.get('state')=='fresh':
        values['state']=None;evidence.append('marketing_fresh_cut_not_purchase_state')
    if values.get('family')=='beans' and values.get('subfamily') in ('white','lima'):
        sizes={v for v in ('large','small') if has(detection,rf'\b{v}\b')}
        if has(detection,r'garrofo'):sizes.add('large')
        if values.get('subfamily')=='lima' and has(detection,r'\bbaby\b'):sizes.add('small')
        if len(sizes)>1:values['ambiguous']=True
        elif sizes:values['grade']=sizes.pop()
    if values.get('family')=='sugar' and values.get('subfamily')=='brown':
        grades={v for v in ('light','dark') if has(detection,rf'\b{v}\b')}
        if len(grades)>1:values['ambiguous']=True;evidence.append('conflicting_sugar_grades')
        elif grades:values['grade']=grades.pop()
    if values.get('family')=='rice' and values.get('subfamily')=='wild' and has(detection,r'\b(?:long grain|brown rice|white rice|basmati|jasmine)\b'):
        set_identity('rice','blend');evidence.append('multiple_grain_identities')
    if values.get('family')=='confection' and has(detection,r'\btoasted\b'):
        values['treatment']='toasted'
    if not product and values.get('family')=='produce' and values.get('subfamily')=='fruit_mix' and component_note:
        values['ambiguous']=True;evidence.append('unverified_specific_mix_components')
    if product and values.get('family')=='produce' and values.get('subfamily')=='chili_pepper' and values.get('form') in ('sliced','diced','chopped') and values.get('state') is None:
        values['ambiguous']=True;evidence.append('unverified_processed_pepper_state')
    if product and values.get('family')=='produce' and values.get('state')=='frozen' and not any(feature.get(k) for k in ('canonical_name','category','brand')):
        # A frozen flavor word with an unexplained name cannot establish a raw
        # produce head. Explicit head metadata or a simple produce name suffices.
        residual_name=re.sub(r'\b(?:frozen|fresh|organic|whole|sliced|diced|chopped|cut|chunks?|spears?|berries|berry|fruits?|vegetables?|oz|lb|lbs|g|kg|ounce|ounces|pounds?|grams?)\b|[0-9]+',' ',detection)
        residual_name=re.sub(rf'\b{re.escape(values["subfamily"].replace("_"," "))}s?\b',' ',residual_name).strip()
        if residual_name:values['ambiguous']=True;evidence.append('unverified_frozen_produce_head')
    if values.get('family')=='produce' and values.get('subfamily')=='cherry':
        if has(detection,r'tart|morell[oa]'):values['variety']='tart'
        elif has(detection,r'\bsweet\b'):values['variety']='sweet'
    if values.get('family') in ('sausage','deli_meat'):
        values['species']=next((species for species,pattern in SPECIES if has(detection,rf'\b(?:{pattern})\b')),None)
        values['dietary_identity']='animal'
        if has(detection,r'vegan|plant based|vegetarian|meatless'):
            set_identity('plant_'+values['family'],values['subfamily']);values['dietary_identity']='plant'
    if values.get('family')=='fish' and has(detection,r'pesto|red peppers?|jalapeno|chili|spicy'):
        values['flavor']='pesto' if has(detection,r'pesto') else 'chili'
    if values.get('family')=='seasoning' and values.get('subfamily')=='paprika':
        if has(detection,r'\bsweet\b'):values['flavor']='sweet'
        elif has(detection,r'\bhot\b'):values['flavor']='hot'
    if values.get('family')=='seasoning' and has(detection,r'\bsmoked\b'):values['treatment']='smoked'
    if values.get('family')=='fat' and values.get('subfamily')=='olive_oil':
        values['grade']=next((v for v,p in [('extra_virgin',r'extra virgin|e v o o|evoo'),('virgin',r'\bvirgin\b'),('refined',r'refined|light olive oil|light flavor|extra light')] if has(detection,p)),None)
    if values.get('family')=='produce':
        if has(detection,r'\bcandied\b'):values['treatment']='candied'
        elif has(detection,r'\bpreserved\b'):values['treatment']='preserved'
    if values.get('family')=='nuts' and has(detection,r'\bflaked\b'):values['form']='flakes'
    if values.get('family')=='meat' and values.get('cut')=='bacon' and has(detection,r'canadian|back bacon'):values['cut']='back_bacon';values['head']='back bacon';values['prepared']='cured'
    if values.get('family')=='beans' and has(detection,r'\bseasoned\b'):values['flavor']='seasoned'
    if product and values.get('family')=='meat' and values.get('prepared')=='cooked':
        # No SKU/brand inference: cooked meat with unexplained nominal tokens
        # cannot be certified as a simple ingredient rather than a meal.
        simple=re.sub(r'\b(?:chicken|turkey|beef|pork|lamb|veal|breasts?|thighs?|legs?|wings?|meat|boneless|skinless|roasted|oven|cooked|smoked|sliced|diced|grilled|herb|herbs|plain|fresh|frozen|lean|oz|ounce|ounces|lb|pound|pounds|g|gram|grams)\b|[0-9]+',' ',detection)
        if simple.strip():values['ambiguous']=True;evidence.append('unverified_simple_cooked_meat_head')
    if values.get('family')=='juice' and has(detection,r'100\s*%'):values['variety']='100_percent'
    if not product and values.get('family')=='leavener' and values.get('subfamily')=='baking_soda':values['head']='baking_soda'
    # Measurement context resolves the conventional baking alias, not soft drinks.
    if not product and has(detection,r'\bsoda\b') and has(detection,r'teaspoons?|tsp') and not has(detection,r'club|sparkling'):
        set_identity('leavener','baking_soda');values['prepared']=None
    variants=[]
    if values.get('family')=='produce' and has(detection,r'\bbaby\b'):variants.append('baby')
    if values.get('family')=='baking_mix' and has(detection,r'\bcomplete\b'):variants.append('complete')
    if values.get('family')=='produce_mix' and has(detection,r'microwavable|steam in bag'):variants.append('microwave_ready')
    if values.get('family')=='rice' and (has(detection,r'whole grain') or values.get('subfamily')=='brown'):variants.append('whole_grain')
    if values.get('family')=='seasoning' and values.get('subfamily')=='black_pepper' and has(detection,r'peppercorns?|whole black pepper'):variants.append('whole_peppercorn');values['form']='whole'
    if values.get('family') in ('rice','grain','baking_mix','dessert_mix'):
        if has(detection,r'\binstant\b'):variants.append('instant')
        if has(detection,r'quick cooking|quick oats|\b1 minute\b'):variants.append('quick_cooking')
    variants.extend(purchased_specificity(values.get('family'),values.get('subfamily'),detection,values.get('cut')))
    values['purchase_variants']=tuple(variants)
    if values.get('family') in PURCHASED_FINAL_FAMILIES:values['prepared']='prepared'
    if not product and specific_mix:values['ambiguous']=True;evidence.append('unverified_specific_mix_components')
    if values.get('family')=='meat' and values.get('cut')=='bacon' and has(detection,r'lardons?'):values['form']='diced'
    if not product and compound_options:values['ambiguous']=True;evidence.append('unresolved_compound_options')
    if product and values.get('family')=='water' and has(detection,r'vitamin|flavou?r|essence|dragonfruit|lemon|berry'):set_identity('beverage','flavored_water');values['prepared']='prepared'
    if values.get('family')=='fish' and precision:values['species']=values['subfamily'];values['dietary_identity']='animal'
    # Absence evidence is required directionally for explicit dietary requests.
    if 'salt' in absence_claims:
        values['salt_level']='unsalted'
    if 'fat' in absence_claims:
        values['fat_level']='fat_free' if values.get('family') in ('cheese','plant_cheese') else 'skim'
    if product:
        domain=domain_evidence(raw,feature)
        if domain:values['domain']='ineligible';evidence.append(domain)
        if values.get('family')=='nonfood':values['domain']='nonfood'
    if values.get('family')=='produce' and has(detection,r'\bpaste\b'):
        origin=values['canonical'];set_identity('derived_paste',origin);values['head']='paste';values['prepared']='prepared';evidence.append('produce_condiment_paste_head')
    if values.get('family') in (None,'prepared') and values.get('domain','food')=='food':
        parts=derived_parts(detection)
        if parts:
            base_text,derived_head=parts
            base=describe(base_text,product=product)
            if base.family and not base.ambiguous and base.identity_form=='basic':
                set_identity('derived_'+derived_head,base.canonical)
                values['head']=derived_head;values['prepared']='prepared'
                evidence.append('compositional_derived_head')
    if compound_query:values['ambiguous']=True;evidence.append('multiple_ingredient_heads_in_query')
    from food_identity_rules import commodity_product_head, herb_product_head
    commodity_head = herb_product_head(detection, values.get('family')) or commodity_product_head(detection, values.get('family'), feature if product else None)
    if product and not commodity_head and values.get('family')=='produce':
        source_aisles = re.sub(r'[-_]', ' ', ' '.join(str(x) for x in feature.get('source_categories', [])))
        if has(source_aisles, r'\bpickled goods\b'):
            values['treatment']='preserved'
            evidence.append('source_pickled_goods_aisle')
        if has(source_aisles, r'\bfrozen snacks\b'):
            # A flavor-only snack title does not establish a produce head.
            commodity_head = ('prepared', 'source_snack')
    if commodity_head:
        set_identity(*commodity_head)
        values['prepared'] = 'prepared'
        evidence.append('outer_commodity_product_head')
    if values.get('family')=='sugar' and has(detection,r'\b(?:coconut|palm|date) sugar\b'):
        subtype=next(word for word in ('coconut','palm','date') if has(detection,rf'\b{word} sugar\b'))
        set_identity('sugar',subtype);evidence.append('named_sugar_material')
    # Outer purchase heads take precedence over constituent ingredient tokens.
    # These are compositional rules, independent of retailer, brand and SKU.
    if product:
        family=values.get('family')
        outer=None
        if family=='acid' and has(detection,r'\bglaze\b'):outer='glaze'
        if family=='fat' and has(detection,r'\bin (?:olive |extra virgin olive )?oil\b') and has(detection,r'\b(?:garlic|tuna|sardines?|anchovies|peppers?)\b'):outer='oil_packed_food'
        if family=='cheese' and has(detection,r'\b(?:salame|salami|prosciutto|pepperoni|snack kit|sandwich)\b'):outer='meat_cheese_composite'
        if family=='beans' and has(detection,r'\b(?:pasta|penne|rotini|casarecce|fusilli|spaghetti|curry|kofta)\b'):outer='legume_prepared_food'
        if family=='seasoning' and has(detection,r'\bpaste\b'):outer='seasoning_paste'
        if family=='pasta' and has(detection,r'\b(?:beefaroni|pasta bowls?|ready to eat|fully cooked)\b'):outer='prepared_pasta_meal'
        if family=='produce' and has(detection,r'\btandoori\b'):outer='unverified_prepared_aromatic'
        if family in ('produce','seasoning') and has(detection,r'\b(?:naan|bread|crackers?|chips?|dressing|marinade|tea|candy|gum)\b'):outer='flavored_composite'
        if family=='beans' and has(detection,r'\b(?:potato|warm spices|chickpeas (?:and )?tomato (?:and )?onion)\b'):outer='legume_prepared_food'
        if family=='dairy' and values.get('subfamily')=='milk' and has(detection,r'\b(?:cheese|cookies?|biscuits?|fudge|chocolate|milk substitute|(?:orange|strawberry|banana|guava|coconut) with milk)\b'):outer='milk_composite_or_analogue'
        if family=='eggs' and has(detection,r'\bwhite eggs\b') and feature.get('base_unit') in ('gram','milliliter'):
            values['subfamily']='whites';evidence.append('liquid_or_mass_egg_white_product')
        if family=='eggs' and has(detection,r'\b(?:replacer|coloring|dyes?)\b'):outer='egg_analogue_or_decoration'
        if family in ('fat','dairy') and values.get('subfamily')=='butter' and has(detection,r'\b(?:popcorn|puffcorn|beans|spray|potatoes|croissants?|crossiants?|croutons?|cakes?|caramel|sauced|broccoli)\b'):outer='butter_named_composite'
        if family=='bread' and has(detection,r'\bbread fruit\b'):outer='breadfruit'
        if family=='produce' and values.get('subfamily')=='potato' and has(detection,r'\b(?:mashed|scalloped)\b'):outer='prepared_potato'
        if family=='meat' and values.get('species')=='chicken' and has(detection,r'\bpatt(?:y|ies)\b'):outer='formed_chicken_product'
        departments=norm(' '.join(str(x) for x in feature.get('source_categories',[])))
        if family=='rice' and has(norm(feature.get('verified_label_text')),r'\bready in (?:1|one) minute\b'):outer='unverified_ready_rice_state'
        if family=='dairy' and values.get('subfamily')=='milk' and has(departments,r'\b(?:sweets|breads and bakery|deli)\b'):outer='unverified_milk_purchase_head'
        if family=='rice' and has(departments,r'\bfrozen foods\b'):
            values['ambiguous']=True;evidence.append('unverified_frozen_rice_state')
        if family=='produce' and values.get('subfamily')=='onion' and has(departments,r'\bpantry\b'):
            values['ambiguous']=True;evidence.append('pantry_allium_processing_unverified')
        if outer:
            set_identity('prepared',outer);values['head']=outer;values['prepared']='prepared'
            evidence.append('outer_purchase_head')
        if family=='meat':
            departments=norm(' '.join(str(x) for x in feature.get('source_categories',[])))
            if values.get('prepared')=='raw' and has(departments,r'\b(?:pantry|frozen foods)\b') and not has(detection,r'\b(?:raw|fresh|uncooked)\b'):
                values['ambiguous']=True;evidence.append('unverified_raw_meat_department')
            if has(departments,r'\b(?:deli|prepared foods)\b'):
                values['ambiguous']=True;evidence.append('prepared_meat_department_state_unverified')
            if has(detection,r'\b(?:chunk(?:s)? in water|baked|breaded|whole grain|vegetable tenders|skewers)\b'):
                values['prepared']='prepared';evidence.append('processed_meat_purchase_form')
            if has(detection,r'\bpatt(?:y|ies)\b'):
                values['form']='patties'
            if has(detection,r'\b(?:tenders?|tenderloins?)\b') and values.get('cut')=='breast' and values.get('prepared')!='cooked':
                evidence.append('unverified_breast_tender_purchase_form')
            label=norm(feature.get('verified_label_text'))
            if has(label,r'plant based|meat from plants|vegan|vegetarian'):
                values['dietary_identity']='plant';evidence.append('explicit_plant_label')
    values['evidence']=tuple(evidence)
    return FoodIdentity(**values)


def compatibility(query, product, mode='exact'):
    if mode not in ('exact','substitute'):raise ValueError('match mode must be exact or substitute')
    if query.alternatives:
        results=[compatibility(branch,product,mode) for branch in query.alternatives]
        valid=next((d for d in results if d.allowed),None)
        if valid:return IdentityDecision('equivalent',valid.reasons+('explicit_query_alternative',),valid.uncertain)
        if mode=='substitute':
            valid=next((d for d in results if d.match_type=='substitute'),None)
            if valid:return valid
        return IdentityDecision('none',tuple(sorted({reason for d in results for reason in d.reasons})))
    if product.domain!='food':return IdentityDecision('none',('nonfood_or_ineligible_domain',))
    failures=[];uncertain=[];equivalent=False;substitute=False
    if not query.family or not product.family:return IdentityDecision('none',('unknown_family',))
    if query.ambiguous or product.ambiguous:return IdentityDecision('none',('ambiguous_identity_or_variant',))
    if query.identity_form=='basic' and product.identity_form=='derived':return IdentityDecision('none',('basic_vs_derived_head_conflict','food_family_conflict'))
    if query.family != product.family:return IdentityDecision('none',('food_family_conflict',))
    if product.family in ('prepared','nonfood'):return IdentityDecision('none',('prepared_or_nonfood_product',))
    if query.dietary_identity and product.dietary_identity != query.dietary_identity:failures.append('dietary_identity_conflict')
    if query.species and query.species != product.species:failures.append('species_conflict' if product.species else 'unverified_species')
    if query.subfamily != product.subfamily:
        # Substitutions are opt-in and never presented as exact equivalents.
        if mode=='substitute' and query.family=='sauce' and {query.subfamily,product.subfamily} <= {'tamari','soy_sauce'}:substitute=True
        elif mode=='substitute' and query.family=='cheese' and {query.subfamily,product.subfamily} <= {'parmesan','pecorino'}:
            substitute=True
        elif query.family=='dairy' and query.subfamily=='yogurt' and product.subfamily=='greek_yogurt':
            substitute=mode=='substitute'
            if not substitute:failures.append('yogurt_style_conflict')
        elif query.family=='eggs' and query.subfamily in ('whites','yolks') and product.subfamily=='whole':equivalent=True
        elif query.family=='dairy' and query.subfamily=='cream' and product.subfamily in ('heavy_cream','light_cream'):equivalent=True
        elif generic_child(query.family,query.subfamily,product.subfamily):equivalent=True
        else:failures.append('subfamily_conflict')
    if query.cut and query.cut!=product.cut:
        if query.family=='meat' and query.cut=='ground' and query.form=='ground' and product.form=='ground':equivalent=True
        elif mode=='substitute' and query.family=='meat' and query.species=='chicken' and {query.cut,product.cut} <= {'breast','thigh'}:substitute=True
        else:failures.append('cut_conflict' if product.cut else 'unverified_cut')
    if query.family=='meat' and query.prepared=='raw' and 'unverified_breast_tender_purchase_form' in product.evidence:failures.append('unverified_raw_breast_tender_form')
    if query.family=='meat' and query.form!='ground' and product.form=='ground':failures.append('ground_vs_whole_conflict')
    if query.family=='meat' and not query.cut and query.prepared=='raw' and not (query.species=='chicken' and query.form=='whole' and product.form=='whole'):uncertain.append('unspecified_meat_cut')
    for key in REQUIRED_ATTRIBUTES:
        required=getattr(query,key);observed=getattr(product,key)
        if required is None:continue
        exception=attribute_exception(query,key,required,observed)
        if exception:
            if exception!='plain_milk_identity':equivalent=True
            continue
        evidence=required_evidence(required,observed)
        if evidence!=Evidence.MATCH:
            failures.append('unverified_'+key if evidence==Evidence.UNKNOWN else key+'_conflict')
    if query.family=='confection' and query.treatment is None and product.treatment is not None:failures.append('unrequested_material_treatment')
    if query.family=='cheese' and not query.flavor and product.flavor in ('pineapple','strawberry','guava','mango','cherry'):failures.append('unrequested_cheese_flavor')
    if query.family=='dip' and not query.flavor and product.flavor:failures.append('unrequested_dip_flavor')
    if query.family in ('meat','fish','shellfish','seasoning') and query.treatment is None and product.treatment in ('smoked','cured') and query.cut not in ('bacon','ham','corned'):failures.append('unrequested_material_treatment')
    if query.family=='produce' and query.treatment is None and product.treatment in ('preserved','candied'):failures.append('unrequested_produce_processing')
    if query.family=='produce' and query.state is None and product.state=='dried' and query.subfamily in ('cranberry','strawberry','cherry','pineapple','apple','pear','peach','blueberry','banana','mango','apricot'):
        failures.append('unrequested_dried_fruit_state')
    if query.family=='produce' and query.state is None and product.state=='dried' and query.subfamily in ('onion','garlic'):
        failures.append('unrequested_dried_allium_state')
    if query.family=='flour' and query.subfamily in ('all_purpose','bread','cake','whole_wheat','self_rising') and 'gluten_free' not in query.dietary_requirements and 'gluten_free' in product.dietary_requirements:failures.append('unrequested_gluten_free_flour')
    if (query.family=='plant_milk' or query.family=='dairy' and query.subfamily=='milk') and not query.flavor and product.flavor not in (None,'plain'):failures.append('unrequested_milk_flavor')
    if query.family in ('dairy','plant_yogurt') and query.subfamily in ('yogurt','greek_yogurt') and not query.flavor and product.flavor not in (None,'plain'):
        failures.append('unrequested_yogurt_flavor')
    if query.family in ('meat','fish','sauce','seed','grain','breadcrumbs','gelatin') and query.flavor is None and product.flavor is not None:
        if not (query.family=='sauce' and query.subfamily=='mustard' and product.flavor=='hot'):failures.append('unrequested_flavor')
    for variant in query.purchase_variants:
        if variant not in product.purchase_variants:failures.append('unverified_purchase_variant:'+variant)
    for claim in query.absence_claims:
        verified = claim in product.absence_claims or (claim=='fat' and product.fat_level in ('skim','fat_free')) or (claim=='salt' and product.salt_level=='unsalted') or claim+'_free' in product.dietary_requirements
        if not verified and query.family=='produce' and claim in ('seed','seeds','stalk','stalks','skin','peel'):
            verified=True;equivalent=True  # ordinary post-purchase removal
        if not verified:failures.append('unverified_absence:'+claim)
    for requirement in query.dietary_requirements:
        if requirement not in product.dietary_requirements:failures.append('unverified_'+requirement)
    if query.family=='produce' and query.form=='spears' and product.form is None and not verified_whole_produce_base(product):failures.append('unverified_whole_base_for_spears')
    # Whole produce can be cut at home. Whole cheese can be grated/shredded.
    if query.family=='meat' and query.cut in ('ham','bacon','corned') and query.form=='ground' and product.form in (None,'whole','sliced','block'):equivalent=True
    elif query.form and query.form!=product.form and not (query.family=='dairy' and query.subfamily=='milk' and query.form=='whole'):
        if query.family in CUTTABLE_FAMILIES and query.form in KITCHEN_FORMS and product.form in KITCHEN_FORMS[query.form]:
            equivalent=True
        elif query.family in ('produce','nuts','seasoning') and query.form=='whole' and product.form is None:equivalent=True
        else:failures.append('form_conflict' if product.form else 'unverified_form')
    if failures:return IdentityDecision('none',tuple(sorted(set(failures))),tuple(uncertain))
    if uncertain:return IdentityDecision('none',('ambiguous_required_identity',),tuple(uncertain))
    if query.family=='broth' or query.family=='cheese' and not query.form or query.family=='dairy' and not query.fat_level:equivalent=True
    return IdentityDecision('substitute' if substitute else 'equivalent' if equivalent else 'exact',('verified_food_identity',))


class IdentityCatalog:
    def __init__(self, features):
        self.identities={};self.by_family={}
        for feature in features:
            if not feature.get('eligible_for_retrieval'):continue
            identity=describe(feature.get('original_product_name') or feature.get('normalized_name'),feature=feature,product=True)
            pid=feature['product_id'];self.identities[pid]=identity
            if identity.family:self.by_family.setdefault(identity.family,set()).add(pid)
        self._candidate_cache={}

    def family_candidate_ids(self, query):
        families={branch.family for branch in query.alternatives} if query.alternatives else {query.family}
        return set().union(*(self.by_family.get(family,set()) for family in families))

    def candidate_ids(self, query, mode='exact'):
        key=(query,mode)
        if key not in self._candidate_cache:
            allowed=set()
            for pid in self.family_candidate_ids(query):
                decision=compatibility(query,self.identities[pid],mode)
                if decision.allowed or mode=='substitute' and decision.match_type=='substitute':allowed.add(pid)
            if len(self._candidate_cache)>4096:self._candidate_cache.clear()
            self._candidate_cache[key]=allowed
        return self._candidate_cache[key]
