import copy,shutil,tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import recipe_chat_presentation as presentation
class PresentationTests(unittest.TestCase):
 def setUp(self):
  temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
  directory=Path(temporary.name)
  for source in presentation.CACHE_DIRECTORY.glob('*.json'):shutil.copy2(source,directory/source.name)
  cache=patch.object(presentation,'CACHE_DIRECTORY',directory);cache.start();self.addCleanup(cache.stop)
  provider=patch.object(presentation,'translation_provider',return_value=None)
  provider.start();self.addCleanup(provider.stop)
  saving=patch.object(presentation,'_save_lines')
  saving.start();self.addCleanup(saving.stop)
 def test_spanish_display_preserves_recipe_and_quantities(self):
  recipe={'ingredients':[{'display':'6 slices cheddar cheese'},{'display':'Kraft cheddar cheese'}],'instructions':['Heat for 20 minutes.'],'servings':2}
  prior=copy.deepcopy(recipe);result=presentation.localize_detail('safe-recipe',recipe,'es')
  self.assertEqual(recipe,prior);self.assertEqual(result['ingredients'][0]['display'],'6 slices queso cheddar')
  self.assertEqual(result['ingredients'][1]['display'],'Kraft cheddar cheese')
  self.assertEqual(result['instructions'],recipe['instructions']);self.assertEqual(result['_instructions_locale'],'en')
 def test_invalid_dynamic_quantity_translation_falls_back(self):
  class Bad:
   def translate(self,*args,**kwargs):return 'Cocina durante 200 minutos.'
  with patch.object(presentation,'translation_provider',return_value=Bad()):
   result=presentation.localize_detail('bad-translation',{'instructions':['Cook for 20 minutes.']},'es')
  self.assertEqual(result['instructions'],['Cook for 20 minutes.'])
 def test_cache_key_includes_locale_and_content_revision(self):
  first={'ingredients':[{'display':'2 eggs'}]};second={'ingredients':[{'display':'3 eggs'}]}
  a=presentation.localize_detail('revision-test',first,'es');b=presentation.localize_detail('revision-test',second,'es')
  self.assertEqual(a['ingredients'][0]['display'],'2 huevos');self.assertEqual(b['ingredients'][0]['display'],'3 huevos')
  a['ingredients'].clear();self.assertEqual(len(presentation.localize_detail('revision-test',first,'es')['ingredients']),1)

class CompleteTranslationTests(unittest.TestCase):
 def setUp(self):
  import tempfile
  self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
  cache=patch.object(presentation,'CACHE_DIRECTORY',Path(self.directory.name));cache.start();self.addCleanup(cache.stop)
 def test_all_display_fields_and_each_instruction_line_are_translated(self):
  class Translator:
   def translate(self,text,source,target):return target+': '+text
  recipe={'name':'Chicken dinner','ingredients':[{'display':'2 eggs'},{'display':'1/2 cup rice'}],
          'equipment':['pan'],'instructions':'Beat 2 eggs.\nCook for 20 minutes.'}
  original=copy.deepcopy(recipe)
  with patch.object(presentation,'translation_provider',return_value=Translator()):
   for locale in ('es','zh-CN','zh-TW','ru','bn','ht','ko','ar','fr','ur','pl'):
    result=presentation.localize_detail('every-recipe',recipe,locale)
    self.assertEqual(result['_translation_status'],'translated')
    self.assertEqual(result['name'],locale+': Chicken dinner')
    self.assertEqual(result['ingredients'][1]['display'],locale+': 1/2 cup rice')
    self.assertEqual(result['equipment'],[locale+': pan'])
    self.assertEqual(result['instructions'],locale+': Beat 2 eggs.\n'+locale+': Cook for 20 minutes.')
  self.assertEqual(recipe,original)
 def test_one_bad_line_does_not_discard_other_translated_steps(self):
  class Translator:
   def translate(self,text,source,target):return 'Cocine por 200 minutos.' if '20' in text else 'Mezcle.'
  with patch.object(presentation,'translation_provider',return_value=Translator()):
   result=presentation.localize_detail('partial',{'instructions':['Stir.','Cook for 20 minutes.']},'es')
  self.assertEqual(result['instructions'],['Mezcle.','Cook for 20 minutes.'])
  self.assertEqual(result['_translation_status'],'partial')
 def test_existing_cache_is_reused_and_external_updates_are_seen(self):
  import json
  path=presentation.CACHE_DIRECTORY/'es.json'
  path.write_text(json.dumps({'cached':{'instructions':{'Stir.':'Mezcle.'}}}))
  with patch.object(presentation,'translation_provider') as provider:
   self.assertEqual(presentation.localize_detail('cached',{'instructions':['Stir.']},'es')['instructions'],['Mezcle.'])
   provider.return_value.translate.assert_not_called()
   path.write_text(json.dumps({'cached':{'instructions':{'Stir.':'Revuelva.'}}}))
   self.assertEqual(presentation.localize_detail('cached',{'instructions':['Stir.']},'es')['instructions'],['Revuelva.'])
 def test_translator_retries_changed_amounts_and_preserves_brands(self):
  from recipe_line_translator import RecipeLineTranslator
  translator=RecipeLineTranslator()
  with patch.object(translator,'_request',side_effect=[['Cocina 200 minutos con queso.'],['Cocina','minutos con','queso.']]):
   self.assertEqual(translator.translate('Cook 20 minutes with Kraft cheese.'),'Cocina 20 minutos con Kraft queso.')

if __name__=='__main__':unittest.main()
