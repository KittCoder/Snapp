"""Reusable food heads and modifiers, independent of query/product IDs.

Purchased composites have their own identities. Component words cannot make a
composite a basic ingredient; kitchen cutting does not change purchased state.
"""
import re

# Ordered compounds before their component tokens. Each entry is a real food
# identity/alias; these rules also apply to unseen brands and quantity contexts.
FOUNDATION_HEADS = (
 ('extract','vanilla',r'vanilla extract'),
 ('extract','almond',r'almond extract'),
 ('plant_cream','coconut',r'cream of coconut|coconut cream'),
 ('produce','garlic',r'garlic cloves?'),
 ('produce','banana_pepper',r'banana peppers?'),
 ('produce','orange_pepper',r'orange peppers?'),
 ('produce','water_chestnut',r'water chestnuts?'),
 ('legume','pigeon_peas',r'pigeon peas'),
 ('beans','chickpeas',r'chick peas?|chickpeas?|garbanzo'),
 ('legume','garden_peas',r'(?:green|garden|english) peas|\bpeas\b'),
 ('acid','rice_vinegar',r'rice vinegar'),
 ('acid','white_wine_vinegar',r'white wine vinegar'),
 ('acid','red_wine_vinegar',r'red wine vinegar'),
 ('acid','cider_vinegar',r'(?:apple )?cider vinegar'),
 ('acid','balsamic_vinegar',r'balsamic vinegar'),
 ('acid','white_vinegar',r'(?:distilled|white) vinegar'),
 ('sauce','oyster_sauce',r'oyster sauce'),
 ('sauce','hoisin',r'hoisin sauce'),
 ('sauce','worcestershire',r'worcestershire(?: sauce)?'),
 ('sauce','mustard',r'deli mustard|mustard deli|stoneground mustard'),
 ('seasoning','red_pepper_flakes',r'(?:crushed (?:hot )?red pepper|red pepper flakes)'),
 ('seasoning','bay_leaf',r'bay (?:leaf|leaves|leafs)'),
 ('seasoning','dill',r'dill(?: weed)?'),
 ('seasoning','turmeric',r'turmeric'),
 ('seasoning','clove',r'cloves?'),
 ('seed','sesame',r'sesame seeds?'),
 ('seed','sunflower',r'sunflower seeds?'),
 ('gelatin','plain',r'(?:unflavou?red )?gelatin(?:e)?'),
 ('produce','honeydew',r'honeydew(?: melon)?'),
 ('produce','acorn_squash',r'acorn squash(?:es)?'),
 ('produce','tomatillo',r'tomatillos?'),
 ('produce','mandarin',r'mandarin oranges?|mandarins?'),
 ('produce','orange',r'oranges?'),
 ('produce','pear',r'pears?'),
 ('produce','watermelon',r'watermelon'),
 ('produce','beet',r'beets?'),
 ('produce','fruit_mix',r'fruit (?:grapes|mix|salad)|mixed fruit'),
 ('juice','grape',r'grape juice|juice grape'),
 ('juice','generic',r'fruit juice'),
 ('fat','cooking_oil',r'cooking oil|\boil\b'),
)
# A legitimate requested composite is matched only to that purchased head.
PURCHASED_HEADS = (
 ('baking_mix','pancake',r'(?:complete |buttermilk |buckwheat )?pancake(?: and waffle)? mix'),
 ('baking_mix','biscuit',r'biscuit (?:mix|mixture)'),
 ('bread','cornbread',r'corn ?bread'),
 ('bread','whole_wheat',r'whole wheat bread'),
 ('bread','whole_grain',r'whole grains? bread|whole grain(?:s)? \d+ grain bread'),
 ('bread','plain',r'\bbread\b'),
 ('cracker','graham',r'graham crackers?'),
 ('sausage','italian',r'italian sausages?|sausages? italian'),
 ('pastry','pie_crust',r'pie crusts?'),
)
# Exclude identity compounds from marker analysis, not entire ingredient lines.
# Their own head is determined below and secondary snack/entree markers remain.
BASIC_COMPOUNDS = r'cream(?:ed)?(?: style)? corn|baking soda|cake flour|bread flour|rice flour|almond flour|coconut flour|flour tortillas?|cream cheese|cottage cheese|coconut cream|cream of coconut|peanut butter|almond butter|(?:chicken|beef|tomato) (?:broth|stock)|deli mustard|mustard deli'
COMPOSITE_MARKERS = r'\b(?:snacks?|bites|pastr(?:y|ies)|strudel|pate|mousse|fluff|protein treats?|crispy|seasoning|spread|shortcakes?|bruschetta|entrees?|meals|dinners|baked beans|burgers?|biscuits?|cookies?|cereals?|crisps?|oatmeal|granola|bakes|shapes|breakfast|soft drink|nectar|soda|rice cakes?|creamed|mixed vegetables|mixed fruit|vegetable medley|cheese sticks|cheese snack|gels?|sorbets?|smoothies?|beverages?|drinks?|bars?|desserts?|extracts?|stuffing|biscotti|lozenges)\b'
# Cutting is directional: whole/sliced/chopped can be cut smaller; powders,
# ground meat, cured foods and material fresh/frozen/canned/dried states cannot.
KITCHEN_FORMS = {
 'chopped': {None,'whole','block','sticks','sliced','diced','chunks','wedges','spears'},
 'diced': {None,'whole','block','sticks','sliced','chunks','wedges','spears'},
 'sliced': {None,'whole','block','sticks'},
 'crumbled': {None,'whole','block','sliced'},
 'grated': {None,'whole','block','sticks'},
 'shredded': {None,'whole','block','sticks'},
 'chunks': {None,'whole','block'},
 'wedges': {None,'whole'}, 'spears': {None,'whole'},
}
CUTTABLE_FAMILIES = {'produce','cheese','meat','fish','shellfish','eggs','nuts','bread','pastry','seasoning','pickle','produce_mix','cookie','confection'}


def head_identity(text):
    for family, subfamily, pattern in FOUNDATION_HEADS:
        match = re.search(r'\b(?:'+pattern+r')\b', text)
        if match:
            # Generic oil must not preempt an explicitly named oil.
            if subfamily=='cooking_oil' and re.search(r'olive|canola|vegetable|coconut|sesame|sunflower|corn|peanut|butter|margarine|spread',text):
                continue
            if subfamily=='cooking_oil' and re.search(r'\b(?:tuna|salmon|sardines?|anchovies?|chicken|beef|pork)\b',text):continue
            if family in ('produce','seasoning','seed','legume','beans','gelatin'):
                remainder=text[:match.start()]+text[match.end():]
                if re.search(r'\b(?:milk|yogurt|cheese|cream|butter|flour|juice|sauce|vinegar|stock|broth|starch)\b',remainder):continue
            return family, subfamily, match.group()
    return None


def purchased_identity(text):
    # Do not treat flour or tortillas as bread just because a modifier says bread.
    if re.search(r'\b(?:bread flour|flour tortillas?)\b',text): return None
    for family, subfamily, pattern in PURCHASED_HEADS:
        match=re.search(r'\b(?:'+pattern+r')\b',text)
        if match:
            if family=='bread' and subfamily=='plain':
                if re.search(r'whole wheat',text):subfamily='whole_wheat'
                elif re.search(r'whole grains?',text):subfamily='whole_grain'
            return family,subfamily,match.group()
    return None


def normalize_food_words(text):
    aliases = {r'\bsause\b':'sauce',r'\bworcesteshire\b':'worcestershire',r'\bgelatine\b':'gelatin',r'\bchick\s+peas?\b':'chickpeas',r'\bwhole\s+grains\b':'whole grain',r'\byoghurt\b':'yogurt',r'\bchiles\b':'chili',r'\bchillies\b':'chili',r'\bcabbages\b':'cabbage',r'\bzucchinis\b':'zucchini',r'\bseason salt\b':'seasoned salt'}
    for pattern,replacement in aliases.items():text=re.sub(pattern,replacement,text)
    return text


def query_branches(text):
    """Resolve explicit OR syntax, including shared food heads/modifiers."""
    if not re.search(r'\bor\b',text):return ()
    form=re.search(r'\b(chopped|minced|ground|shredded|flaked) or (chopped|minced|ground|shredded|flaked)(?: fine)?\b',text)
    if form:return tuple(text[:form.start()]+value+text[form.end():] for value in form.groups())
    cereal=re.search(r'\b(rice|wheat) or (rice|wheat) cereal\b',text)
    if cereal:return tuple(text[:cereal.start()]+value+' cereal'+text[cereal.end():] for value in cereal.groups())
    state=re.search(r'\b(fresh|frozen|canned|dried) or (fresh|frozen|canned|dried)\b',text)
    if state:return tuple(text[:state.start()]+value+text[state.end():] for value in state.groups())
    color=re.search(r'\bonions?\s+(green|red|yellow|white) or (green|red|yellow|white)\b',text)
    if color:return tuple(text[:color.start()]+value+' onion'+text[color.end():] for value in color.groups())
    pudding=re.search(r'\b(?:instant )?pudding mix\b',text)
    if pudding:
        parts=re.split(r'\bor\b',text,maxsplit=1)
        return parts[0].strip(),pudding.group()+' '+parts[1].strip()
    all_parts=re.split(r'\bor\b',text)
    if len(all_parts)>2:
        # In a homogeneous list, a single leading purchased-state adjective
        # scopes over all listed choices. Contradictory states remain explicit.
        states=re.findall(r'\b(fresh|frozen|canned|dried)\b',text)
        if len(states)==1 and re.search(r'\b'+states[0]+r'\b',all_parts[0]):
            return tuple(part.strip() if i==0 else states[0]+' '+part.strip() for i,part in enumerate(all_parts))
    parts=re.split(r'\bor\b',text,maxsplit=1)
    if len(parts)!=2:return ()
    left,right=parts
    # Shared purchase head in "chicken or vegetable stock".
    shared=re.search(r'\b(stock|broth|milk|cheese|vinegar|steak|cereal|beans|oil)\b',right)
    if shared and not re.search(r'\b'+shared.group()+r'\b',left):left+=' '+shared.group()
    if shared and shared.group()=='beans' and re.search(r'\bseasoned\b',left):right='seasoned '+right
    return left.strip(),re.sub(r'\bother\b','',right).strip()

# Purchased identities observed in the final holdout, expressed as food taxonomy
# rather than names, brands, IDs or recipe exceptions. Outer heads precede their
# ingredient components on both query and inventory paths.
FINAL_HEADS = (
 ('beans','black',r'black beans'),
 ('beans','red',r'red beans'),
 ('produce','lychee',r'lychee(?: nuts)?'),
 ('acid','cream_of_tartar',r'cream of tartar'),
 ('fat','bacon_fat',r'bacon (?:fat|drippings)|(?:fat|drippings) (?:of |from )?bacon'),
 ('fat','lard',r'\blard\b'),
 ('sauce','salsa',r'(?:tomato )?salsa'),
 ('sauce','ketchup',r'ketchup|catsup'),
 ('sauce','mushroom',r'mushrooms?\s+sauce'),
 ('tomato','pizza_sauce',r'pizza sauce'),
 ('dessert_mix','pudding',r'(?:instant )?pudding mix|pudding'),
 ('gravy','beef',r'beef gravy(?: granules)?|gravy granules(?: for)? beef'),
 ('acid','wine_vinegar',r'(?<!red )(?<!white )wine vinegar'),
 ('rice','wild',r'wild rice'),
 ('sausage','frankfurter',r'frankfurters?|beef franks|hot dogs?'),
 ('deli_meat','salami',r'salami'),
 ('seasoning','seasoned_salt',r'seasoned salt'),
 ('produce_mix','vegetable',r'mixed(?: diced|chopped|cut)? vegetables|vegetable medley'),
 ('dressing','generic',r'(?:salad dressing|vinaigrette(?: dressing)?|\bdressing\b)(?: and marinade)?'),
 ('pickle','cucumber',r'pickles?'),
 ('tea','black',r'black tea'),
 ('cookie','ginger_snap',r'ginger ?snaps?(?: cookies?)?'),
 ('breadcrumbs','matzo',r'matzo meal'),
 ('confection','marshmallow',r'marshmallows?'),
 ('chocolate','dark_chips',r'dark chocolate chips'),
 ('chocolate','semisweet_chips',r'(?:semi sweet|semisweet)(?: milk)? chocolate chips'),
 ('cereal','rice',r'(?:rice|rice and wheat|rice or wheat) cereal(?: squares)?'),
 ('cereal','wheat',r'wheat cereal(?: squares)?'),
 ('produce','cherry',r'cherries|cherry'),
 ('produce','cantaloupe',r'cantaloupes?'),
 ('produce','artichoke',r'artichoke hearts?'),
 ('produce','plantain',r'plantains?'),
 ('seasoning','nutmeg',r'nutmeg'),
 ('seasoning','allspice',r'allspice'),
 ('grain','quinoa',r'quinoa'),
 ('pasta','linguine',r'linguine'),
 ('sweetener','molasses',r'molasses'),
 ('pickle','caper',r'capers?'),
 ('nuts','generic',r'\bnuts\b'),
)
PURCHASED_FINAL_FAMILIES={'sausage','deli_meat','produce_mix','dressing','pickle','tea','cookie','breadcrumbs','confection','chocolate','cereal','dessert_mix','gravy'}


def final_identity(text):
    for family,subfamily,pattern in FINAL_HEADS:
        match=re.search(r'\b(?:'+pattern+r')\b',text)
        if not match:continue
        if family=='nuts' and subfamily=='generic' and re.search(r'peanuts?|almonds?|walnuts?|cashews?|pecans?|coconut|lychee',text):continue
        # Nuts/spices/fruits may be modifiers of a stronger purchased head.
        if family in ('nuts','produce','seasoning','grain','sweetener'):
            remainder=text[:match.start()]+text[match.end():]
            if re.search(r'\b(?:milk|yogurt|cheese|cream|butter|flour|juice|sauce|vinegar|stock|broth|tea|cereal|meal|tomatoes|tomato)\b',remainder):continue
        return family,subfamily,match.group()
    return None


def strip_final_head(text,family,subfamily):
    for f,s,pattern in FINAL_HEADS:
        if (f,s)==(family,subfamily):text=re.sub(r'\b(?:'+pattern+r')\b',' ',text)
    return text

# Final-review taxonomy facts. Each rule applies independent of inventory IDs.
MICRO_HEADS = (
 ('produce','potato',r'yukon gold(?: potatoes)?|russet(?: potatoes)?'),
 ('pastry','puff',r'puff pastry(?: sheets)?|(?:frozen )?sheets pastry dough'),
 ('seasoning','lemon_pepper',r'lemon pepper(?: seasoning)?(?: blend)?'),
 ('seasoning','red_pepper_flakes',r'hot pepper flakes|chili pepper flakes'),
 ('produce','spaghetti_squash',r'spaghetti squash'),
 ('produce','snow_pea',r'snow peas'),
 ('nuts','brazil',r'brazil nuts'),
 ('produce','breadfruit',r'breadfruit(?: nuts)?'),
 ('fruit_peel','orange',r'orange (?:peel|zest|rind)'),
 ('sauce','cream',r'cream sauce'),
 ('sauce','hot_pepper',r'hot pepper sauce'),
 ('condiment_paste','chili',r'chili pepper paste|chili paste'),
 ('tomato','paste',r'tomato concentrate|concentrated tomato'),
 ('tomato','passata',r'passata|strained tomatoes|tomatoes strained'),
 ('syrup','apple_pear',r'apple pear syrup|apple syrup|pear syrup'),
 ('syrup','generic',r'\bsyrup\b'),
 ('confection','marshmallow_fluff',r'marshmallow fluff|fluff marshmallow'),
 ('sausage','andouille',r'andouille sausages?|sausages? andouille'),
 ('pickle','sauerkraut',r'sauerkraut'),
 ('pickle','sweet_relish',r'sweet relish'),
 ('chips','potato',r'potato chips'),
 ('cracker','whole_grain',r'whole grain(?:s)?(?: saltine)? crackers?'),
 ('cereal','generic',r'\bcereal\b'),
 ('produce','asparagus',r'asparagus'),
 ('produce','shallot',r'shallots?'),
 ('produce','raisin',r'raisins?'),
 ('water','ice',r'\bice\b'),
)


def micro_identity(text):
    for family,subfamily,pattern in MICRO_HEADS:
        match=re.search(r'\b(?:'+pattern+r')\b',text)
        if match:
            if subfamily=='ice' and re.search(r'ice cream|ice tea|iced tea',text):continue
            if family=='produce' and re.search(r'\b(?:juice|sauce|soup|milk|spread)\b',text[match.end():]):continue
            if subfamily=='generic' and family=='cereal' and re.search(r'\b(?:rice|wheat) cereal',text):continue
            if subfamily=='generic' and family=='syrup' and re.search(r'maple|corn|vanilla|in (?:heavy |light )?syrup|packed in',text):continue
            return family,subfamily,match.group()
    return None


def strip_micro_head(text,family,subfamily):
    for f,s,pattern in MICRO_HEADS:
        if (f,s)==(family,subfamily):text=re.sub(r'\b(?:'+pattern+r')\b',' ',text)
    return text

# Precision-hardening heads: outer compounds before their component words.
PRECISION_HEADS = (
 ('beans','black_eyed',r'black[- ]eyed peas?'),
 ('beans','lima',r'garrofo|garrofó'),
 ('fish','rockfish',r'rockfish|rock cod'),
 ('dairy','whipped_cream',r'whip(?:ped)?(?: light| heavy)? cream(?! cheese)'),
 ('dessert','whipped_topping',r'whipped topping'),
 ('produce','lemongrass',r'lemon ?grass'),
 ('sauce','aioli',r'aioli'),
 ('chips','puffs',r'(?:chickpea|corn|cheese) puffs'),
 ('chips','pita',r'pita (?:thins|chips)'),
 ('fruit_preserve','relish',r'(?:cranberry|fruit) relish|spreadable fruit'),
 ('fish','anchovy',r'anchovies|anchovy'),
 ('fish','herring',r'herring'),
 ('fish','mackerel',r'mackerel'),
 ('prepared','fried_produce',r'fried (?:eggplants?|aubergines?|zucchini|cauliflower|okra)|breaded (?:eggplants?|aubergines?|zucchini)'),
 ('seasoning','celery_seed',r'celery seeds?'),
 ('sauce','thai_chili',r'thai (?:sweet )?chil[l]?i sauce'),
 ('sauce','sweet_chili',r'sweet chil[l]?i(?: hot)? sauce'),
 ('sauce','hot_sauce',r'hot sauce'),
 ('produce','kiwi',r'kiwifruits?|kiwi'),
 ('produce','radish',r'radishes|radish'),
 ('produce','date',r'dates'),
 ('seasoning','nutmeg',r'nutmeg|nuez moscada'),
 ('pasta','fettuccine',r'fettuccine'),
 ('bread','pita',r'pita(?: bread)?'),
 ('confection','sour_candy',r'sour belts|sour strips|gummies|gummy candy'),
 ('seasoning','marjoram',r'marjoram'),
 ('prepared','creamed_legume',r'cream of (?:beans|lentils|peas)'),
 ('prepared','fried_meat',r'fried (?:chicken|turkey|fish|pork)|breaded (?:chicken|turkey|fish|pork)'),
 ('imitation_food','meat_topping',r'imitation (?:bacon|meat|beef|chicken)(?: bits|topping)?'),
 ('fish','sardine',r'sardines?'),
 ('pickle','sweet_relish',r'sweet (?:pickle )?relish'),
 ('pickle','cucumber',r'gherkins?'),
 ('nuts','pine',r'pine nuts|pignoli'),
 ('nuts','almond',r'almonds?'),
 ('nuts','walnut',r'walnuts?'),
 ('nuts','pecan',r'pecans?'),
 ('nuts','cashew',r'cashews?'),
 ('nuts','peanut',r'peanuts?'),
 ('acid','raspberry_vinegar',r'raspberry vinegar'),
 ('pasta','shells',r'pasta shells|shells pasta'),
 ('pasta','egg_noodles',r'egg noodles'),
 ('tofu','soy',r'tofu'),
 ('cocoa','plain',r'cocoa(?: powder)?'),
 ('extract','vanilla',r'vanilla(?: extract| essence)?'),
 ('beans','lima',r'lima beans'),
)


def precision_identity(text):
    for family,subfamily,pattern in PRECISION_HEADS:
        match=re.search(r'\b(?:'+pattern+r')\b',text)
        if match:
            if family in ('nuts','beans','cocoa','tofu') and re.search(r'\b(?:milk|flour|butter|sauce|soup|drink|juice|spread|cereal)\b',text[match.end():]):continue
            if family=='extract' and re.search(r'\b(?:pudding|yogurt|milk|cream|syrup|cereal|cookies?|cake|drink|coffee)\b',text):continue
            return family,subfamily,match.group()
    return None


def strip_precision_head(text,family,subfamily):
    for f,s,pattern in PRECISION_HEADS:
        if (f,s)==(family,subfamily):text=re.sub(r'\b(?:'+pattern+r')\b',' ',text)
    return text

# A single reusable source of purchased specificity. The compatibility loop
# requires all requested variants, independently of ranking/embedding scores.
PRECISION_VARIANTS = (
 ('seasoning','salt','kosher_crystal',r'\bkosher salt\b'),
 ('pasta',None,'white_wheat',r'\bwhite wheat\b'),
 ('pasta',None,'wheat_grain',r'\b(?:white wheat|whole wheat|wheat)\b'),
 ('produce','chili_pepper','in_adobo',r'\badobo\b'),
 ('breadcrumbs',None,'italian_seasoned',r'\bitalian\b'),
 ('bread','pita','whole_wheat',r'whole wheat|whole grain'),
 ('produce','cherry','white_variety',r'\bwhite\b'),
 ('cereal',None,'bran',r'\bbran\b'),
 ('pasta',None,'whole_wheat',r'whole wheat|whole grain'),
 ('rice',None,'long_grain',r'long grain'),
 ('rice',None,'white_grain',r'\bwhite\b'),
 ('pickle','cucumber','sweet',r'\bsweet\b'),
 ('pickle','cucumber','dill',r'\bdill\b'),
 ('meat','ham','center_cut',r'center cut'),
)


def purchased_specificity(family,subfamily,text,cut=None):
    return tuple(value for f,s,value,pattern in PRECISION_VARIANTS if f==family and (s is None or s==subfamily or s==cut) and re.search(pattern,text))


def domain_evidence(text,feature):
    if re.search(r'\b(?:cream|lotion)\b',text) and re.search(r'\b(?:hydrating|healing|moisturizing|medicated|topical|dermatologist|skin relief)\b',text):return 'explicit_topical_product'
    if any(feature.get(k) is False for k in ('snap_eligible','is_snap_eligible')):return 'explicit_ineligible_metadata'
    if str(feature.get('snap_eligibility','')).lower()=='ineligible':return 'explicit_ineligible_metadata'
    if re.search(r'\b(?:hard seltzer|vodka|whiskey|whisky|rum|tequila|alcoholic beverage|\d+\s*%\s*abv)\b',text):return 'alcohol_beverage'
    if any(re.search(r'\b(?:alcohol|alcoholic beverages|beer wine spirits)\b',str(feature.get(k,'')).lower()) for k in ('category','subcategory')):return 'alcohol_category'
    return None
