"""Fixed conversation benchmark: expectations are independent of live rankings.

The same turns run with fixture retrieval in tests and real Typesense in review.
Human review evaluates semantic interpretation separately from retrieval quality.
"""


def turn(message, **expect):
    return {'message': message, 'expect': expect}


def language_cases():
    cases = []
    scaffolds = ["I want {}", "I'd like {}", "I would like {}", "I'm looking for {}",
                 "I'm craving {}", "I feel like {}", "Can you find me {}?",
                 "Could you find me {}?", "Give me {}", "Show me {}",
                 "Do you have {}?", "Anything with {}?", "{} sounds good"]
    for scaffold in scaffolds:
        for ingredient in ['chicken', 'beef', 'rice', 'pasta', 'eggs']:
            cases.append({'name': f'inclusion_{len(cases)}', 'turns': [
                turn(scaffold.format(ingredient), intent='NEW_SEARCH', include_ingredients=[ingredient],
                     exclude_ingredients=[], semantic_query='')]})
    for negative in ['no {}', 'without {}', "I don't want {}", "I don't really want {}",
                     'avoid {}', 'skip the {}', 'anything but {}', 'not {}']:
        for ingredient in ['cheese', 'chicken', 'onions']:
            cases.append({'name': f'negation_{len(cases)}', 'turns': [
                turn('warm dinner with rice', include_ingredients=['rice'], semantic_query='warm'),
                turn(negative.format(ingredient), intent='REFINE_SEARCH', exclude_ingredients=[ingredient],
                     include_ingredients=['rice'], semantic_query='warm', categories=['lunch_dinner'])]})
    for preference in ['warm', 'cozy', 'comforting', 'light', 'hearty', 'spicy', 'creamy',
                       'fresh', 'simple', 'easy', 'summery', 'winter', 'cold', 'hot',
                       'lighter', 'heartier', 'cozier', 'easier', 'spicier']:
        cases.append({'name': f'preference_{preference}', 'turns': [
            turn(f'Maybe something {preference}', intent='NEW_SEARCH', semantic_query=preference,
                 include_ingredients=[], exclude_ingredients=[], max_time=None)]})
    for message, cap, semantic in [
        ('under half an hour', 30, ''), ('less than 20 minutes', 20, ''),
        ('no more than 45 minutes', 45, ''), ('under 30 minutes', 30, ''),
        ('quick', None, 'quick'), ('really quick', None, 'quick'),
        ('fast', None, 'quick'), ("I don't have much time", None, 'quick'),
        ('around 30 minutes', None, 'about 30 minutes'),
    ]:
        cases.append({'name': f'time_{len(cases)}', 'turns': [
            turn(message, intent='NEW_SEARCH', max_time=cap, semantic_query=semantic)]})
    for meal, category in [('breakfast', 'breakfast'), ('brunch', 'breakfast'), ('lunch', 'lunch_dinner'),
                           ('dinner', 'lunch_dinner'), ('snack', 'snack'), ('dessert', 'dessert')]:
        cases.append({'name': f'meal_{meal}', 'turns': [
            turn(f'something for {meal} tonight', intent='NEW_SEARCH', categories=[category], semantic_query='')]})
    for message in ['actually beef', 'beef instead', 'maybe beef instead', 'not chicken, beef',
                    'actually no chicken — use beef', 'I changed my mind, beef']:
        exclusion = ['cheese', 'chicken'] if 'no chicken' in message or 'not chicken' in message else ['cheese']
        cases.append({'name': f'replacement_{len(cases)}', 'turns': [
            turn('I want a warm chicken dinner', include_ingredients=['chicken'], semantic_query='warm'),
            turn('under 30 minutes', max_time=30), turn('no cheese', exclude_ingredients=['cheese']),
            turn(message, intent='REFINE_SEARCH', include_ingredients=['beef'], semantic_query='warm',
                 max_time=30, categories=['lunch_dinner'], exclude_ingredients=exclusion)]})
    for message in ['something quicker', 'faster', 'not as long', 'make it quicker']:
        cases.append({'name': f'relative_{len(cases)}', 'turns': [
            turn('chicken under 40 minutes', max_time=40),
            turn(message, intent='REFINE_SEARCH', max_time=30, include_ingredients=['chicken'], semantic_query='')]})
    for message in ['show me something similar', 'show me another one', 'another option',
                    'give me more', 'not that one', 'give me something else', 'something like that']:
        cases.append({'name': f'alternatives_{len(cases)}', 'turns': [
            turn('warm dinner', semantic_query='warm'), turn('the first one', intent='SELECT_RESULT'),
            turn(message, intent='REFINE_SEARCH', semantic_query='warm', categories=['lunch_dinner'], alternatives=True)]})
    cases.extend([
        {'name': 'neutral_negation', 'turns': [turn("I don't mind chicken", intent='GENERAL_FOLLOWUP', exclude_ingredients=[])]},
        {'name': 'low_spice', 'turns': [turn('Not too spicy', intent='NEW_SEARCH', semantic_query='mild', exclude_ingredients=[])]},
        {'name': 'less_spice', 'turns': [turn('less spicy', intent='NEW_SEARCH', semantic_query='mild', exclude_ingredients=[])]},
        {'name': 'mixed_polarity', 'turns': [turn('I want something without cheese but with chicken',
            intent='NEW_SEARCH', include_ingredients=['chicken'], exclude_ingredients=['cheese'], semantic_query='')]},
        {'name': 'available_list', 'turns': [turn("I've got eggs and potatoes", intent='NEW_SEARCH',
            include_ingredients=['eggs', 'potatoes'], semantic_query='')]},
        {'name': 'permission_salmon', 'turns': [turn('can I use salmon?', intent='NEW_SEARCH', include_ingredients=['salmon'], semantic_query='')]},
        {'name': 'dairy_exclusion', 'turns': [turn('no dairy', intent='NEW_SEARCH', dietary=['dairy_free'], semantic_query='')]},
        {'name': 'context_vegetarian', 'turns': [turn('something spicy with rice', semantic_query='spicy'),
            turn('make that vegetarian', intent='REFINE_SEARCH', dietary=['vegetarian'], include_ingredients=['rice'], semantic_query='spicy')]},
        {'name': 'context_exclusion', 'turns': [turn('chicken dinner', include_ingredients=['chicken']),
            turn('no cheese in those', intent='REFINE_SEARCH', exclude_ingredients=['cheese'], semantic_query='')]},
        {'name': 'clear_time', 'turns': [turn('chicken under 30 minutes', max_time=30),
            turn('forget the time limit', intent='CLEAR_CONSTRAINT', max_time=None, include_ingredients=['chicken'])]},
        {'name': 'clear_restriction', 'turns': [turn('pasta without cheese', exclude_ingredients=['cheese']),
            turn('remove the cheese restriction', intent='CLEAR_CONSTRAINT', exclude_ingredients=[], include_ingredients=['pasta'])]},
        {'name': 'natural_allowance', 'turns': [turn('rice without chicken', exclude_ingredients=['chicken']),
            turn('chicken is fine actually', intent='CLEAR_CONSTRAINT', exclude_ingredients=[], include_ingredients=['rice'])]},
        {'name': 'clear_meal', 'turns': [turn('breakfast with eggs', categories=['breakfast']),
            turn('never mind the breakfast part', intent='CLEAR_CONSTRAINT', categories=[], include_ingredients=['eggs'])]},
        {'name': 'reset', 'turns': [turn('chicken without cheese under 30 minutes'),
            turn('start over', intent='GENERAL_FOLLOWUP', include_ingredients=[], exclude_ingredients=[], max_time=None, semantic_query='')]},
        {'name': 'reset_with_search', 'turns': [turn('chicken without cheese under 30 minutes'),
            turn('new search for breakfast with eggs', intent='NEW_SEARCH', include_ingredients=['eggs'], exclude_ingredients=[], max_time=None, categories=['breakfast'])]},
        {'name': 'negative_inclusion_removed', 'turns': [turn('chicken with rice'),
            turn('Actually, no chicken', intent='REFINE_SEARCH', include_ingredients=['rice'], exclude_ingredients=['chicken'])]},
        {'name': 'numeric_beats_relative', 'turns': [turn('chicken under 40 minutes'),
            turn('something faster under 20 minutes', intent='REFINE_SEARCH', max_time=20)]},
        {'name': 'ingredient_replacement', 'turns': [turn('chicken with rice'),
            turn('replace rice with pasta', intent='REFINE_SEARCH', include_ingredients=['chicken', 'pasta'])]},
        {'name': 'neutral_preserves_exclusion', 'turns': [turn('rice without chicken'),
            turn("I don't mind chicken", intent='GENERAL_FOLLOWUP', exclude_ingredients=['chicken'], include_ingredients=['rice'])]},
        {'name': 'question_after_selection', 'turns': [turn('breakfast with eggs'), turn('show me the second one', intent='SELECT_RESULT'),
            turn('does it use milk?', intent='QUESTION_ABOUT_SELECTED_RECIPE', include_ingredients=['eggs'])]},
        {'name': 'question_vs_search', 'turns': [turn('Can you find me a quick chicken dinner?', intent='NEW_SEARCH',
            include_ingredients=['chicken'], categories=['lunch_dinner'], semantic_query='quick', max_time=None)]},
        {'name': 'conflicting_positive_is_safe', 'turns': [turn('pasta without cheese'),
            turn('with cheese', exclude_ingredients=['cheese'], include_ingredients=['pasta'], response_contains='conflicts')]},
    ])
    cases.extend([
        {'name': 'requested_warm_beef', 'turns': [turn('I want something warm with beef', intent='NEW_SEARCH', include_ingredients=['beef'], semantic_query='warm')]},
        {'name': 'requested_spicy', 'turns': [turn('I feel like something spicy', intent='NEW_SEARCH', semantic_query='spicy')]},
        {'name': 'requested_cozy_dinner', 'turns': [turn('Give me something cozy for dinner', intent='NEW_SEARCH', semantic_query='cozy', categories=['lunch_dinner'])]},
        {'name': 'requested_easy', 'turns': [turn('I want something easy', intent='NEW_SEARCH', semantic_query='easy')]},
        {'name': 'available_eggs', 'turns': [turn('I have eggs', intent='NEW_SEARCH', include_ingredients=['eggs'], semantic_query='')]},
        {'name': 'available_rice', 'turns': [turn('anything using rice', intent='NEW_SEARCH', include_ingredients=['rice'], semantic_query='')]},
        {'name': 'natural_replacement_chicken', 'turns': [turn('beef dinner under 30 minutes without cheese'),
            turn('maybe chicken instead', intent='REFINE_SEARCH', include_ingredients=['chicken'], exclude_ingredients=['cheese'], categories=['lunch_dinner'], max_time=30)]},
        {'name': 'changed_mind_salmon', 'turns': [turn('chicken dinner under 30 minutes without cheese'),
            turn('I changed my mind, salmon', intent='REFINE_SEARCH', include_ingredients=['salmon'], exclude_ingredients=['cheese'], categories=['lunch_dinner'], max_time=30)]},
        {'name': 'negative_category_not_positive', 'turns': [turn('warm dinner'),
            turn('not vegetarian', dietary=[], semantic_query='warm', response_contains='cannot reliably exclude')]},
        {'name': 'negative_meal_not_positive', 'turns': [turn('breakfast with eggs'),
            turn('no dinner', categories=['breakfast'], response_contains='cannot reliably exclude')]},
        {'name': 'numeric_negative_bound', 'turns': [turn('not over 30 minutes', intent='NEW_SEARCH', max_time=30, min_time=None)]},
        {'name': 'compound_neutral_negative', 'turns': [turn("I don't mind chicken but no cheese", intent='NEW_SEARCH', include_ingredients=[], exclude_ingredients=['cheese'])]},
        {'name': 'neutral_comfort_context', 'turns': [turn('warm chicken dinner'),
            turn("I don't mind chicken", intent='GENERAL_FOLLOWUP', include_ingredients=['chicken'], semantic_query='warm')]},
    ])
    return cases
