import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import recipe_nutrition as nutrition

class RecipeNutritionTests(unittest.TestCase):
 def setUp(self):
  nutrition.food_candidates.cache_clear();self.addCleanup(nutrition.food_candidates.cache_clear)
 def food(self,description,protein=0,carbs=0,fat=0,portions=None):
  return {'fdc_id':123,'description':description,'data_type':'SR Legacy',
          'nutrients_per_100g':{'protein_g':protein,'carbohydrates_g':carbs,'fat_g':fat},'portions':portions or []}
 def test_recipe_amounts_multiply_per_100g_and_divide_by_recipe_servings(self):
  foods=[self.food('Egg, whole, raw',protein=12,fat=10,portions=[{'amount':1,'grams':50,'unit':'undetermined','description':'large'}]),
         self.food('Rice, white, cooked',carbs=28,portions=[{'amount':1,'grams':158,'unit':'cup','description':''}])]
  recipe={'ingredients':['2 large eggs','2 cups cooked rice']}
  with patch.object(nutrition,'catalog',return_value=foods):result=nutrition.recipe_nutrition(recipe,2)
  self.assertEqual(result['nutrition_status'],'complete')
  self.assertEqual(result['nutrition_ingredients'][0]['grams'],100)
  self.assertEqual(result['nutrition_ingredients'][1]['grams'],316)
  self.assertEqual(result['nutrition_total']['protein_g'],12)
  self.assertEqual(result['nutrition_per_person']['protein_g'],6)
  self.assertEqual(result['nutrition_per_person']['carbohydrates_g'],44.24)
 def test_full_ingredient_mass_is_used_not_number_of_packages_purchased(self):
  with patch.object(nutrition,'catalog',return_value=[self.food('Chicken, raw',protein=20)]):
   result=nutrition.recipe_nutrition({'ingredients':['200 grams chicken']},4)
  self.assertEqual(result['nutrition_total']['protein_g'],40)
  self.assertEqual(result['nutrition_per_person']['protein_g'],10)
 def test_unknown_amounts_remain_explicitly_incomplete(self):
  with patch.object(nutrition,'catalog',return_value=[self.food('Chicken, raw',protein=20)]):
   result=nutrition.recipe_nutrition({'ingredients':['200 grams chicken','salt to taste']},2)
  self.assertEqual(result['nutrition_status'],'partial')
  self.assertEqual(result['nutrition_missing_ingredients'],['salt to taste'])
  self.assertEqual(result['nutrition_total']['protein_g'],40)
 def test_egg_white_is_not_matched_to_whole_egg(self):
  foods=[self.food('Egg, whole, raw',fat=10,portions=[{'amount':1,'grams':50,'unit':'undetermined','description':'large'}]),
         self.food('Egg, white, raw',protein=10,portions=[{'amount':1,'grams':33,'unit':'undetermined','description':'large'}])]
  with patch.object(nutrition,'catalog',return_value=foods):result=nutrition.recipe_nutrition({'ingredients':['2 egg whites']},1)
  self.assertEqual(result['nutrition_ingredients'][0]['usda_description'],'Egg, white, raw')
  self.assertEqual(result['nutrition_total']['fat_g'],0)
 def test_olive_oil_is_not_matched_to_a_mixed_oil(self):
  foods=[self.food('Oil, corn, peanut, and olive',fat=100),self.food('Oil, olive, salad or cooking',fat=100)]
  with patch.object(nutrition,'catalog',return_value=foods):result=nutrition.recipe_nutrition({'ingredients':['10 grams olive oil']},1)
  self.assertEqual(result['nutrition_ingredients'][0]['usda_description'],'Oil, olive, salad or cooking')
 def test_usda_records_and_macro_units_are_present(self):
  foods=nutrition.catalog()
  self.assertGreater(len(foods),8000)
  self.assertTrue(all(all(key in food['nutrients_per_100g'] for key in nutrition.MACROS) for food in foods))
 def test_broth_does_not_match_chicken_described_as_no_broth(self):
  foods=[self.food('Chicken, canned, no broth',protein=25),self.food('Soup, chicken broth, ready-to-serve',protein=.6)]
  with patch.object(nutrition,'catalog',return_value=foods):result=nutrition.recipe_nutrition({'ingredients':['400 grams chicken broth']},2)
  self.assertEqual(result['nutrition_ingredients'][0]['usda_description'],'Soup, chicken broth, ready-to-serve')
  self.assertEqual(result['nutrition_total']['protein_g'],2.4)
 def test_count_portions_never_use_a_cup_of_eggs(self):
  food=self.food('Egg, whole, raw',protein=12,portions=[
   {'amount':1,'grams':243,'unit':'undetermined','description':'cup (4.86 large eggs)'},
   {'amount':1,'grams':50,'unit':'undetermined','description':'large'}])
  with patch.object(nutrition,'catalog',return_value=[food]):result=nutrition.recipe_nutrition({'ingredients':['2 large eggs']},2)
  self.assertEqual(result['nutrition_ingredients'][0]['grams'],100)
 def test_chicken_drumsticks_use_usda_edible_portion_weight(self):
  food=self.food('Chicken, drumstick, meat and skin, raw',protein=18,
                 portions=[{'amount':1,'grams':130,'unit':'undetermined','description':'drumstick'}])
  with patch.object(nutrition,'catalog',return_value=[food]):result=nutrition.recipe_nutrition({'ingredients':['4 skin-on chicken drumsticks']},4)
  self.assertEqual(result['nutrition_status'],'complete')
  self.assertEqual(result['nutrition_ingredients'][0]['grams'],520)
  self.assertEqual(result['nutrition_per_person']['protein_g'],23.4)
  with patch.object(nutrition,'catalog',return_value=[food]):
   result=nutrition.recipe_nutrition({'extendedIngredients':[{'original':'4 skin-on chicken drumsticks','name':'skin-on chicken drumsticks','amount':4,'unit':''}]},4)
  self.assertEqual(result['nutrition_status'],'complete')
  self.assertEqual(result['nutrition_ingredients'][0]['grams'],520)

if __name__=='__main__':unittest.main()
