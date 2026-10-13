"""Additive, grounded turns around the existing English service.

Unrecognized messages return None and take the exact original path. Unsupported
facts are disclosed; equipment gates operate only on stored equipment metadata.
"""
from copy import deepcopy
import re
import time


def extension(service,message,state,extra,pantry,household):
    import recipe_chat as chat
    import recipe_chat_language as language
    import recipe_search_typesense as retrieval
    lower=language.normalize(message)
    core=chat.RecipeChatState.from_value(state)
    started=time.perf_counter()

    def answer(text,intent,selected=None,results=None,parsed=None,query=None):
        return {'message':text,'intent':intent,'state':core.to_dict(),'results':results or [],
                'selected_recipe':selected,'parsed_constraints':parsed or {},
                'search_metadata':{'latency_ms':round((time.perf_counter()-started)*1000,2),
                   'typesense_latency_ms':0,'typesense_server_latency_ms':0,'mode':None,
                   'fallback':False,'alpha':None,'typesense_query':query,'recipe_lookup_ids':[]}}

    def search(intent,parsed=None):
        # Same canonical SearchState and original Typesense search implementation.
        limit=50 if extra.get('equipment_available') or extra.get('equipment_excluded') else 5
        if extra.get('preferred_ingredients'):
            query=(core.semantic_query+' '+' '.join(extra['preferred_ingredients'])).strip()
            payload=retrieval.search_recipes(query,limit=limit,state=retrieval.SearchState.from_value(core.to_dict()),
                config=service.config,mode="hybrid",alpha=.7,allow_fallback=True,parse_constraints=False)
        else:payload=service.search(core,limit=limit)
        results=[chat.public_recipe(r) for r in payload['results']]
        allowed=extra.get('equipment_available',[]);blocked=extra.get('equipment_excluded',[])
        if allowed or blocked:
            def compatible(recipe):
                equipment=recipe.get('equipment')
                if not isinstance(equipment,list) or not equipment:return False
                normalized=[str(item).lower() for item in equipment]
                if any(any(term in item for term in blocked) for item in normalized):return False
                if allowed:
                    support={'skillet','pan','frying pan','stove','stovetop','knife','bowl','spoon','pot','cutting board'} if 'skillet' in allowed else set(allowed)|{'knife','bowl','spoon','cutting board'}
                    return all(any(term in item for term in support) for item in normalized)
                return True
            results=[r for r in results if compatible(r)]
        core.selected_recipe_id=None
        results,reply=service.compose_response(results[:5],core)
        if allowed or blocked:reply+='\nEquipment checks use stored lists only; recipes with missing equipment data are left out.'
        result=answer(reply,intent,results=results,parsed=parsed,
            query={'q':payload['effective_query'],'filter_by':payload['filter_by'],'mode':payload['mode'],'alpha':payload['alpha']})
        for key in ('mode','fallback','alpha','typesense_server_latency_ms','typesense_latency_ms'):result['search_metadata'][key]=payload[key]
        return result

    if message=='__apply_active_preferences__':return search('REFINE_SEARCH')

    if re.fullmatch(r'(?:clear|remove) (?:equipment|pantry preferences|preferred ingredients)',lower):
        for key in ('equipment_available','equipment_excluded','preferred_ingredients'):extra.pop(key,None)
        return search('CLEAR_CONSTRAINT')
    listed=re.fullmatch(r'which (?:ones|of these) (?:have|use|contain) (.+)',lower)
    if listed:
        tokens=set(retrieval.ingredient_filter_tokens([listed[1]]))
        recipes=[service.fetch_recipe(rid) for rid in core.last_result_ids]
        found=[recipe for recipe in recipes if recipe and tokens.issubset(set(retrieval.ingredient_filter_tokens(recipe.get('ingredient_names',[]))))]
        text='These recipes list that ingredient:\n'+'\n'.join(chat.recipe_line(recipe) for recipe in found) if found else 'That ingredient is not named in the stored result lists. This is not an allergy guarantee.'
        return answer(text,'QUESTION_ABOUT_RESULTS')

    switch=re.fullmatch(r'(?:what about |)(vegetarian|vegan)(?: instead)?',lower)
    if switch and (lower.startswith('what about') or lower.endswith('instead')):
        core.include_ingredients=[term for term in core.include_ingredients if term not in chat.PROTEINS-{'tofu'}]
        core.dietary=[term for term in core.dietary if term not in {'vegetarian','vegan'}]+[switch[1]]
        return search('REPLACE_CONSTRAINT',{'dietary':[switch[1]],'replace_ingredients':True})
    replace=re.fullmatch(r'same thing but with (.+)',lower)
    if replace:return service.handle_message('actually '+replace[1],state)
    missing=re.fullmatch(r"i (?:don't|do not) have (.+)",lower)
    if missing and missing[1] not in {'an oven','a skillet','oven','skillet'}:
        names=language.parse_message('with '+missing[1])[1]['include_ingredients']
        if names:
            extra['unavailable_ingredients']=names
            return answer('Would you like recipes without that ingredient, or would you prefer to add it to your shopping list?','GENERAL_FOLLOWUP')

    # Questions do not issue searches or invent missing costs/nutrients.
    reference=chat.ordinal_index(lower,len(core.last_result_ids))
    question=bool(re.match(r'^(?:what|how|does|is|can|which|compare)\b',lower))
    if lower in {'that one','show me that one','what about that one'}:
        if not core.selected_recipe_id:return answer('Which recipe do you mean? Choose a result by number.','GENERAL_FOLLOWUP')
        selected=service.fetch_recipe(core.selected_recipe_id)
        return answer(chat.recipe_line(selected) if selected else 'That recipe is no longer available.','SELECT_RESULT',selected=selected)
    if question and re.search(r'\b(?:cheapest|cheaper|cost|price|nutrition|protein)\b',lower):
        return answer('Cost is not recorded for this recipe.' if re.search(r'cheap|cost|price',lower) else 'Nutrition is not recorded for this recipe.','QUESTION_ABOUT_RESULTS')
    if re.match(r'^can i substitute\b',lower):
        return answer('The stored recipe does not specify that substitution. I can show its ingredients, but cannot guarantee the replacement will work.','SUBSTITUTION_QUESTION')
    if question and ('dairy' in lower or 'vegetarian' in lower or 'oven' in lower):
        rid=core.last_result_ids[reference] if reference is not None and 0<=reference<len(core.last_result_ids) else core.selected_recipe_id
        recipe=service.fetch_recipe(rid) if rid else None
        if not recipe:return answer('Select a recipe first, for example: show me the second one.','QUESTION_ABOUT_SELECTED_RECIPE')
        if 'oven' in lower:
            equipment=recipe.get('equipment')
            text='Equipment is not recorded for this recipe.' if not equipment else 'Stored equipment: '+', '.join(equipment)+'.'
        elif 'vegetarian' in lower:
            text='This recipe has a stored vegetarian tag.' if 'vegetarian' in recipe.get('categories',[]) else 'A vegetarian tag is not recorded. Please review the ingredient list.'
        else:
            names=recipe.get('ingredient_names') or []
            dairy=[name for name in names if any(re.search(r'\b'+re.escape(term)+r'\b',name.lower()) for term in retrieval.dairy_ingredient_names())]
            text='Listed dairy ingredients: '+', '.join(dairy)+'.' if dairy else 'No named dairy ingredient appears in the stored list. This is not an allergy guarantee.'
        return answer(text,'QUESTION_ABOUT_SELECTED_RECIPE',selected=recipe)
    if re.match(r'^compare\s+\d+\s+(?:and|&)\s+\d+',lower):
        numbers=[int(n)-1 for n in re.findall(r'\d+',lower)]
        if any(n<0 or n>=len(core.last_result_ids) for n in numbers):return answer('Choose two available result numbers.','COMPARE_RESULTS')
        ids=[core.last_result_ids[n] for n in numbers]
        recipes=[service.fetch_recipe(rid) for rid in ids]
        extra['comparison_recipe_ids']=ids
        return answer('Stored recipe comparison:\n'+'\n'.join(chat.recipe_line(recipe) for recipe in recipes if recipe),'COMPARE_RESULTS')

    pantry_request=bool(re.search(r'\b(?:what (?:can|could) i make with what i have|use what i (?:already )?have|use (?:my |the )?pantry)\b',lower))
    available=re.match(r'^i have (.+)',lower)
    if pantry_request or (available and re.search(r',|\band\b',available[1]) and not re.search(r'\b(?:minutes?|hour|oven|skillet)\b',available[1])):
        names=[item.get('name') for item in pantry if isinstance(item,dict) and isinstance(item.get('name'),str)] if pantry_request else language.parse_message('with '+available[1])[1]['include_ingredients']
        names=retrieval.clean_terms(names[:20])
        if not names:return answer('Tell me what ingredients you have, or add them to your pantry first.','PANTRY_BASED_SEARCH')
        extra['preferred_ingredients']=names
        return search('PANTRY_BASED_SEARCH',{'preferred_ingredients':names})

    equipment=re.search(r"(?:i (?:only )?have (?:a |an )?(skillet|oven)|i (?:don't|do not) have (?:a |an )?(oven|skillet))",lower)
    if equipment:
        excluded=equipment[2];term=excluded or equipment[1]
        field='equipment_excluded' if excluded else 'equipment_available'
        extra[field]=list(dict.fromkeys(extra.get(field,[])+[term]))
        other='equipment_available' if excluded else 'equipment_excluded'
        extra[other]=[x for x in extra.get(other,[]) if x!=term]
        return search('REFINE_SEARCH' if core.has_search() else 'NEW_SEARCH',{field:[term]})

    # Only newly supported explicit time phrasings are normalized here.
    explicit=re.search(r'\b(\d+) minutes? max\b',lower)
    between=re.search(r'\bbetween (\d+) and (\d+) minutes?\b',lower)
    hour=re.fullmatch(r'i have (?:an|one) hour',lower)
    if explicit or between or hour:
        if between:
            low,high=int(between[1]),int(between[2])
            if not 1<=low<=high<=10000:return answer('Please choose a valid time range.','GENERAL_FOLLOWUP')
            core.min_time,core.max_time=low,high
        else:core.max_time=60 if hour else int(explicit[1])
        if not 1<=core.max_time<=10000:return answer('Please choose a valid time limit.','GENERAL_FOLLOWUP')
        return search('REFINE_SEARCH' if state else 'NEW_SEARCH',{'min_time':core.min_time,'max_time':core.max_time})
    allowance=re.fullmatch(r'(?:actually |nevermind,? |never mind,? )?(.+?) (?:is |are )?(?:fine|okay|ok)',lower)
    if allowance and lower.startswith(('actually ','nevermind','never mind')):
        return service.handle_message(allowance[1]+' is fine',state)
    # Persist preferences without forcing fabricated Typesense fields.
    terms={'budget_preference':r'\b(?:cheap|cheaper|budget|affordable)\b','spice_preference':r'\b(?:mild|less spicy|spicy)\b'}
    for field,pattern in terms.items():
        if re.search(pattern,lower):extra[field]='mild' if 'mild' in lower or 'less spicy' in lower else 'cheap' if field=='budget_preference' else 'spicy'
    health=[term for term in ('healthy','healthier','high protein','higher protein','kid friendly','warm','filling','simple','light') if term in lower]
    if health:extra['health_preferences']=list(dict.fromkeys(extra.get('health_preferences',[])+health))
    family=re.search(r'\bfor (?:my family|my kids|(?:\d+) people)\b',lower)
    if family:
        number=re.search(r'\d+',family[0]);extra['household_size']=min(20,max(1,int(number[0]))) if number else min(20,max(1,int(household or 1)))
    # Original search and state behavior remains authoritative for all other turns.
    return None
