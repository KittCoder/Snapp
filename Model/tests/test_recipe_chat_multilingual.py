"""Multilingual equivalence and additive conversation behavior, real parser/search."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
import recipe_chat as chat
import recipe_chat_multilingual as multilingual
import recipe_search_typesense as search
from test_recipe_chat import Wire

REQUESTS={
'en':'I want chicken dinner under 30 minutes with no cheese',
'es':'Quiero una cena con pollo en menos de 30 minutos y sin queso.',
'zh-CN':'我想要一道30分钟以内的鸡肉晚餐，不含奶酪。',
'zh-TW':'我想要一道30分鐘以內的雞肉晚餐，不含起司。',
'ru':'Хочу ужин с курицей меньше чем за 30 минут без сыра.',
'bn':'৩০ মিনিটের মধ্যে মুরগির রাতের খাবার চাই পনির ছাড়া।',
'ht':'Mwen vle yon dine ak poul ki pran mwens pase 30 minit san fwomaj.',
'ko':'30분 이내 닭고기 저녁 치즈 없이 원해요.',
'ar':'أريد عشاء مع الدجاج أقل من 30 دقيقة بدون الجبن.',
'fr':'Je veux un dîner avec du poulet en moins de 30 minutes sans fromage.',
'ur':'30 منٹ سے کم مرغی رات کا کھانا پنیر بغیر چاہیے۔',
'pl':'Chcę obiad z kurczakiem poniżej 30 minut bez sera.',
}

class MultilingualTests(unittest.TestCase):
 def setUp(self):
  provider=patch('recipe_chat_presentation.translation_provider',return_value=None);provider.start();self.addCleanup(provider.stop)
  self.wire=Wire();self.transport=patch.object(search,'typesense_request',side_effect=self.wire);self.transport.start();self.addCleanup(self.transport.stop);self.service=chat.RecipeChatService()
 def call(self,message,state=None,locale='en',**kwargs):return multilingual.handle_message(self.service,message,state,locale=locale,**kwargs)
 def test_equivalent_constraints_in_all_locales(self):
  expected=self.call(REQUESTS['en'])
  for locale,message in REQUESTS.items():
   with self.subTest(locale=locale,canonical=multilingual.canonicalize(message,locale)):
    result=self.call(message,locale=locale)
    for key in ('include_ingredients','exclude_ingredients','max_time','min_time','categories','dietary','semantic_query'):
     self.assertEqual(result['state'][key],expected['state'][key],key)
    self.assertEqual([r['id'] for r in result['results']],[r['id'] for r in expected['results']])
    self.assertEqual(result['search_metadata']['typesense_query'],expected['search_metadata']['typesense_query'])
 def test_english_fast_path_is_not_translated(self):
  with patch.object(multilingual,'canonicalize',wraps=multilingual.canonicalize) as translate:
   wrapped=self.call('I want a beef dinner under 30 minutes')
  original=self.service.handle_message('I want a beef dinner under 30 minutes')
  for key in ('state','intent','parsed_constraints','results'):self.assertEqual(wrapped[key],original[key])
  self.assertEqual(translate.call_args.args[1],'en')
 def test_ordinals_and_reset_all_locales(self):
  for locale,terms in multilingual.lexicons().items():
   with self.subTest(locale=locale):
    initial=self.call('dinner')
    selected=self.call(terms['second'][0],initial['state'],locale)
    self.assertEqual(selected['selected_recipe']['id'],initial['state']['last_result_ids'][1])
    cleared=self.call(terms['clear time limit'][0],self.call('under 30 minutes',initial['state'])['state'],locale)
    self.assertIsNone(cleared['state']['max_time'])
    reset=self.call(terms['start over'][0],selected['state'],locale)
    self.assertEqual(reset['state']['include_ingredients'],[])
 def test_corrections_dietary_and_questions_all_locales(self):
  for locale,terms in multilingual.lexicons().items():
   with self.subTest(locale=locale):
    initial=self.call('beef dinner under 30 minutes')
    replacement=self.call(terms['actually'][0]+' '+terms['chicken'][0],initial['state'],locale)
    self.assertEqual(replacement['state']['include_ingredients'],['chicken'])
    self.assertEqual(replacement['state']['max_time'],30)
    dietary=self.call(terms['vegetarian'][0],replacement['state'],locale)
    self.assertIn('vegetarian',dietary['state']['dietary'])
    excluded=self.call(terms['without'][0]+' '+terms['cheese'][0],replacement['state'],locale)
    self.assertIn('cheese',excluded['state']['exclude_ingredients'])
    allowed=self.call(terms['cheese'][0]+' '+terms['is fine'][0],excluded['state'],locale)
    self.assertNotIn('cheese',allowed['state']['exclude_ingredients'])
    selected=self.call(terms['first'][0],replacement['state'],locale)
    for question in ('what ingredients do I need','how long does that take','how do I make that'):
     answer=self.call(terms[question][0],selected['state'],locale)
     self.assertEqual(answer['intent'],'QUESTION_ABOUT_SELECTED_RECIPE')
     self.assertEqual(answer['results'],[])

 def test_spanish_followups_and_caller_state_preserved(self):
  first=self.call(REQUESTS['es'],locale='es');before=copy.deepcopy(first['state'])
  faster=self.call('algo más rápido',first['state'],'es')
  self.assertEqual(first['state'],before);self.assertEqual(faster['state']['max_time'],22)
  second=self.call('muéstrame el segundo',first['state'],'es')
  question=self.call('¿qué ingredientes necesito?',second['state'],'es')
  self.assertEqual(question['intent'],'QUESTION_ABOUT_SELECTED_RECIPE');self.assertEqual(question['results'],[])
  self.assertEqual(question['state']['conversation_language'],'es')
 def test_pantry_list_is_preference_not_all_required(self):
  result=self.call('I have chicken, rice and tomatoes')
  self.assertEqual(result['intent'],'PANTRY_BASED_SEARCH');self.assertEqual(result['state']['include_ingredients'],[])
  self.assertEqual(result['state']['preferred_ingredients'],['chicken','rice','tomatoes'])
  self.assertNotIn('ingredient_filter_tokens',result['search_metadata']['typesense_query']['filter_by'])
 def test_missing_cost_and_nutrition_are_not_invented(self):
  initial=self.call('dinner')
  result=self.call('which is cheapest?',initial['state'])
  self.assertIn('not recorded',result['message']);self.assertEqual(result['results'],[])
 def test_equipment_is_gate_with_no_false_typesense_fields(self):
  self.wire.documents[0]['equipment']=['skillet','bowl']
  self.wire.documents[1]['equipment']=['oven']
  initial=self.call('chicken dinner')
  result=self.call("I don't have an oven",initial['state'])
  self.assertEqual([r['id'] for r in result['results']],['c1'])
  self.assertNotIn('equipment',result['search_metadata']['typesense_query']['filter_by'])
 def test_new_numeric_time_forms(self):
  self.assertEqual(self.call('20 minutes max')['state']['max_time'],20)
  result=self.call('between 30 and 45 minutes');self.assertEqual(result['state']['min_time'],30);self.assertEqual(result['state']['max_time'],45)
 def test_unknown_state_fields_and_invalid_extensions_rejected(self):
  for state in ({'evil':'yes'},{'household_size':999},{'conversation_language':'x'}):
   with self.assertRaises(ValueError):self.call('dinner',state)

if __name__=='__main__':unittest.main()
