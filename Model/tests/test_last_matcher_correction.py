"""Final correction classes, adversarial unseen-name positives and negatives."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from product_ontology import describe,compatibility
class LastMatcherCorrectionTests(unittest.TestCase):
 def gated(self,q,p,metadata=None):
  from test_surgical_structural import SurgicalStructuralTests
  SurgicalStructuralTests().assert_gated(q,p,metadata)
 def test_black_eyed_legume_subfamily(self):
  for q in ('black-eyed peas','black eyed peas','canned black eyed peas'):
   for p in ('Sweet Peas','Garden Peas','Chickpeas','Pigeon Peas'):
    self.gated(q,'Unseen '+p)
  self.assertTrue(compatibility(describe('black eyed peas'),describe('Black-Eyed Peas',product=True)).allowed)
 def test_meat_fish_species_purchase_form(self):
  for q,p in [('salt pork','Ground Pork'),('ground salt pork','Fresh Ground Pork'),('rockfish','Cod Fillet'),('rock cod','Fresh Cod'),('veal steak','Beef Steak')]:self.gated(q,'Unseen '+p)
  for name in ('Salt Pork','Rockfish Fillets','Rock Cod'):
   self.assertTrue(compatibility(describe(name),describe(name,product=True)).allowed)
 def test_required_salt_grain_bean_variants(self):
  for q,p in [('kosher salt','Salt'),('kosher salt','Sea Salt'),('wheat rotini','Chickpea Rotini'),('white wheat pasta','Gluten Free Pasta'),('large white beans','Small White Beans'),('garrofo beans','Small White Beans'),('large garrofo beans','Baby Lima Beans'),('white wheat pasta','Tri-Color Durum Wheat Pasta')]:self.gated(q,'Unseen '+p)
  for name in ('Kosher Salt','Whole Wheat Rotini','Large White Beans'):
   self.assertTrue(compatibility(describe(name),describe(name,product=True)).allowed)
 def test_whipped_cream_head(self):
  for q in ('cream','light cream','heavy cream'):
   for p in ('Whipped Cream','Whipped Light Cream','Whipped Heavy Cream'):self.gated(q,'Unseen '+p)
  self.gated('whip cream','Whipped Cream Cheese')
  self.assertTrue(compatibility(describe('whip cream'),describe('Real Whipped Cream',product=True)).allowed)
 def test_required_light_dressing_fat(self):
  for name in ('Honey Mustard Dressing','Sweet Spicy Honey Mustard Dressing','Honey Mustard'):
   self.gated('light honey mustard dressing','Unseen '+name)
  self.gated('light honey mustard or poppy seed dressing','Honey Mustard')
 def test_compound_color_queries_abstain(self):
  for colors in ('green red and yellow','red yellow and orange','green and red'):
   for p in ('Green Bell Pepper','Red Bell Pepper','Yellow Bell Pepper'):self.gated(colors+' bell peppers','Unseen '+p)
 def test_prepared_spice_heads(self):
  for name in ('Apple Cinnamon','Banana Cinnamon','Berry Cinnamon'):
   self.gated('cinnamon','Unseen '+name)
  self.assertTrue(compatibility(describe('cinnamon'),describe('Ground Cinnamon',product=True)).allowed)
 def test_marketing_state_and_crushed_pepper(self):
  for brand in ('Unseen','New Vendor','Novel'):
   self.gated('fresh green beans',brand+' Fresh Cut Green Beans',{'freshness':'fresh'})
   self.gated('chopped chili peppers',brand+' Crushed Jalapeno Pepper')
 def test_incomplete_oil_head_abstains(self):
  for q in ('extra virgin olive','2 tablespoons extra virgin olive','extra virgin olives'):
   self.gated(q,'Whole Olives')
 def test_newly_exposed_prepared_heads(self):
  for name in ('Irish Cream Liqueur','Coffee Cream Liqueur','Vanilla Cream Liqueur'):
   self.gated(name,'Heavy Cream')
  for name in ('Brown Rice Snaps','White Rice Snaps','Rice Side Dish'):
   self.gated('cooked rice','Novel '+name)
  self.gated('lite whipped topping','Dairy Whipped Topping')
 def test_obvious_normalization_and_kitchen_recoveries(self):
  for q,p in [('black peppeer','Black Pepper'),('cinamon','Cinnamon'),('gingerroot','Ginger Root'),('pieces of toast','Bread'),('nut meats','Walnuts'),('cooked rice','Rice'),('cooked brown rice','Brown Rice')]:
   with self.subTest(q=q):self.assertTrue(compatibility(describe(q),describe(p,product=True)).allowed)
  self.assertIsNone(describe('broccoli (you can use any amount)').state)
if __name__=='__main__':unittest.main()
