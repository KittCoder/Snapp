"""Class-based precision regressions and adversarial head/domain witnesses."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'Model'))
from product_ontology import describe,compatibility

class PrecisionHardeningTests(unittest.TestCase):
    def test_reviewed_wrong_pairs_and_obvious_direct_aliases(self):
        rows=[json.loads(line) for line in (ROOT/'Model/evaluation/precision_hardening_regressions.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows),27)
        for row in rows:
            with self.subTest(case=row['case_id'],cause=row['root_cause']):
                self.assertTrue(row['general_rule'])
                self.assertEqual(compatibility(describe(row['ingredient']),describe(row['product_name'],feature=row['product_feature'],product=True)).allowed,row['expected_allowed'])

    def test_generated_product_heads_dominate_component_tokens(self):
        for base in ('strawberries','eggplant','pork liver','marshmallows','brown sugar','rice'):
            for head in ('juice','sauce','soup','spread','cereal','bread','snack','pastry','drink','seasoning','entree'):
                with self.subTest(base=base,head=head):self.assertFalse(compatibility(describe(base),describe('Unseen Market '+base+' '+head,product=True)).allowed)
        for query,product in [('cream','Cream of Lentils'),('cream','Strawberry Cream Sour Belts'),('red potatoes','Red and Yellow Potatoes'),('lemons','Preserved Lemons'),('lemons','Sardines With Preserved Lemon'),('cooked chicken','Fried Chicken'),('bacon lardons','Imitation Bacon Bits')]:
            with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe('Unseen Market '+product,product=True)).allowed)

    def test_required_specificity_is_shared_unknown_mismatch_logic(self):
        self.assertFalse(compatibility(describe('long grain white rice'),describe('Long Grain Rice',product=True)).allowed)
        self.assertTrue(compatibility(describe('long grain white rice'),describe('Long Grain White Rice',product=True)).allowed)
        for fruit in ('Lemon','Cherry','Strawberry'):
            for nut in ('Almonds','Walnuts','Cashews'):
                with self.subTest(fruit=fruit,nut=nut):self.assertFalse(compatibility(describe(fruit),describe('Unseen '+fruit+' Bliss '+nut,product=True)).allowed)
        for query,product in [('pine nuts','Mixed Nuts'),('red potatoes','Potatoes'),('raspberry vinegar','Apple Cider Vinegar'),('sweet pickle relish','Pickles'),('sweet pickles','Dill Gherkins'),('long grain rice','Rice'),('whole wheat pasta shells','Pasta Shells'),('bran cereal','Cereal'),('raw center cut ham','Raw Ham')]:
            with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe(product,product=True)).allowed)
        for query,product in [('pine nuts','Pine Nuts'),('red potatoes','Red Potatoes'),('sweet pickles','Sweet Gherkins'),('bran cereal','Bran Cereal'),('raspberry vinegar','Raspberry Vinegar')]:
            with self.subTest(query=query):self.assertTrue(compatibility(describe(query),describe(product,product=True)).allowed)

    def test_fruit_packing_medium_is_not_juice_head(self):
        for packing in ('juice','100% juice','100 % juice'):
            query=describe('pineapple in '+packing)
            self.assertEqual(query.family,'produce')
            self.assertEqual(query.packing_medium,'juice')
            self.assertFalse(compatibility(query,describe('Pineapple 100% Juice',product=True)).allowed)
            self.assertTrue(compatibility(query,describe('Pineapple In '+packing,product=True)).allowed)

    def test_food_domain_and_explicit_eligibility_are_hard_gates(self):
        for name in ('Cherry Hard Seltzer 5% ABV','Copper Metal Care Cream','Pasta Cooking Pan','Rice Serving Bowl','Sugar Dispenser'):
            for query in ('cherries','cream','pasta','rice','sugar'):
                with self.subTest(name=name,query=query):self.assertFalse(compatibility(describe(query),describe(name,product=True)).allowed)
        for key in ('snap_eligible','is_snap_eligible'):
            with self.subTest(key=key):self.assertFalse(compatibility(describe('cream'),describe('Cream',feature={key:False},product=True)).allowed)

    def test_legitimate_prepared_heads_remain_purchasable(self):
        for name in ('salsa','ketchup','salami','sauerkraut','potato chips','salad dressing','ginger snaps','Italian sausage'):
            with self.subTest(name=name):self.assertTrue(compatibility(describe(name),describe('Unseen Brand '+name,product=True)).allowed)

    def test_headings_and_compound_food_lines_abstain(self):
        for query in ('For the fish:','Pico de Gallo:','marjoram and cumin'):
            with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe('Cumin',product=True)).allowed)
        mix=describe('mixed diced vegetables (string beans, carrots, peas or celery)')
        self.assertEqual(mix.family,'produce_mix')
        self.assertFalse(compatibility(mix,describe('Celery and Carrot Sticks',product=True)).allowed)

if __name__=='__main__':unittest.main()
