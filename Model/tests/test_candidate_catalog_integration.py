"""Real corrected-catalog checks, separate from deterministic recipe fixtures."""
import json,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'Model'))
from product_retrieval import ProductCandidateRetriever
from product_compatibility import ProductMatchService,profile_from_query
from product_ontology import compatibility
from basket_quantity import BasketBuilder,parse_package_info,parse_price_info
S=Path(os.getenv('SNAPP_CANDIDATE_ARTIFACT_DIR',str(ROOT/'data/morton_williams_corrected_20261013')))
if not (S/'morton_williams_product_features.json').exists():S=ROOT/'Model'
INDEX=S/('vector_index' if (S/'vector_index').exists() else 'morton_williams_vector_index')

@unittest.skipUnless((S/'morton_williams_product_features.json').exists(),'Candidate artifact integration requires the corrected staging catalog')
class CandidateCatalogIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service=ProductMatchService(retriever=ProductCandidateRetriever(features_path=S/'morton_williams_product_features.json',index_dir=INDEX));cls.builder=BasketBuilder(cls.service)
    def test_required_basic_identity_queries(self):
        queries=['white sugar','rice','fresh mint','garlic','rye bread','extra virgin olive oil','red wine vinegar','skirt steak']
        for q,result in zip(queries,self.service.match_recipe_ingredients(queries,limit=15,use_semantic=True)):
            with self.subTest(query=q):
                if not result.selected_match:
                    self.assertIn(q,['fresh mint','skirt steak']);continue
                query=profile_from_query(q,self.service.overrides)[0].ontology
                product=self.service.product_profile(self.service.feature_by_id[result.selected_match.product_id]).ontology
                self.assertTrue(compatibility(query,product).allowed)
                if q=='fresh mint':self.assertEqual((product.family,product.subfamily,product.state),('produce','mint','fresh'))
    def test_lamb_in_pitas_current_catalog_safely_abstains(self):
        recipe={'id':'candidate-lamb-in-pitas','ingredients':['1 pound minced lamb','1 tablespoon fresh mint, chopped','1 small onion, finely chopped','1 garlic clove, crushed','1 tablespoon sweet chili sauce','1 tub hummus','4 whole meal pita breads','25 gram rockets']}
        basket=self.builder.build_recipe_basket(recipe)
        for item in basket.shopping_basket:
            for raw in item.ingredients:
                query=profile_from_query(raw,self.service.overrides)[0].ontology
                product=self.service.product_profile(self.service.feature_by_id[item.product_id]).ontology
                self.assertTrue(compatibility(query,product).allowed,(raw,item.product_name))
                if 'small onion' in raw:self.assertEqual(product.family,'produce');self.assertNotEqual(product.state,'dried')
                if 'fresh mint' in raw:self.assertEqual((product.family,product.subfamily,product.state),('produce','mint','fresh'))
        self.assertFalse(any('minced lamb' in raw for item in basket.shopping_basket for raw in item.ingredients),'Current snapshot has no verified ground lamb; never substitute another cut/species')
    def test_ambiguous_package_economics_abstain(self):
        features=self.service.feature_by_id.values()
        for f in features:
            if f.get('size_evidence_source')=='pdf_layout_unverified' or f.get('package_parse_confidence')=='low':
                self.assertFalse(parse_package_info(f).eligible_for_optimization,f['original_product_name'])
            price=parse_price_info(f.get('raw_price'),f)
            if price.checkout_price is not None:self.assertGreater(price.checkout_price,0)
