const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {execFileSync}=require('node:child_process');
const root=path.resolve(__dirname,'../..');
const fixtures=JSON.parse(execFileSync(process.env.SNAPP_TEST_PYTHON || 'python3',['-c',`
import json,sys
sys.path.insert(0,'Model/tests')
from test_deal_presentation import shopping_payload
cases=[('20 oz sugar',['Domino Premium Pure Cane Granulated Sugar','Domino Premium Pure Cane Granulated Sugar 2 lb. Carton'],[6.49,5.29],[24,32]),
('1 lb ground beef',['Fresh made lean ground beef round'],[5],None),
('1 oz sugar',['Domino Premium Pure Cane Granulated Sugar','Zero Sugar Cola'],[4,.01],None),
('20 oz sugar',['Domino Premium Pure Cane Granulated Sugar'],[4],[16]),
('sugar',['Domino Premium Pure Cane Granulated Sugar'],[4],None),
('6 slices cheddar cheese',['Cheddar Cheese'],[5],None)]
print(json.dumps([shopping_payload(*args) for args in cases]))
`],{cwd:root,encoding:'utf8',stdio:['ignore','pipe','pipe']}));
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.classList={toggle(){}};this.listeners={};}
 append(...nodes){this.children.push(...nodes);} appendChild(n){this.append(n);}
 replaceChildren(){this.children=[];} setAttribute(k,v){this[k]=v;} addEventListener(k,f){this.listeners[k]=f;}
}
const text=n=>[n.textContent||'',...n.children.map(text)].join(' ');
const source=fs.readFileSync(path.join(root,'Web/app.js'),'utf8');
function render(dish,locale='en',activeItems=null){
 const catalog=JSON.parse(fs.readFileSync(path.join(root,'Web/i18n',locale+'.json'),'utf8'));
 const list=new Element('ul');
 const c=vm.createContext({Intl,console,document:{createElement:tag=>new Element(tag),createTextNode:text=>Object.assign(new Element('text'),{textContent:text})},window:activeItems?{SNAPP_ACTIVE_STORE:{items:()=>activeItems}}:{},currencyFormatter:new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}),scheduledMeals:[{...dish,schedule_id:'test'}],
 shoppingList:list,shoppingStatus:{},currentUser:{id:'test'},pantryHandledShoppingIngredientIds:new Set(),selectedShoppingIngredientIds:new Set(),
 getLanguage:()=>locale,t:(key,values={})=>(catalog[key]||'').replace(/\{(\w+)\}/g,(_,k)=>values[k]),
 getShoppingCategory:()=> 'Baking',getSortedShoppingCategories:items=>[['Baking',items]],addPantryItem:async()=>true});
 for(const [a,b] of [['function getIngredientName(','function shoppingCategoryFromText('],['function getShoppingIngredients(','function updateShoppingAddButton('],['function appendShoppingDeal(','async function refreshScheduledNutrition(']]){
  const start=source.indexOf(a);const end=source.indexOf(b,start);assert.ok(end>start);vm.runInContext(source.slice(start,end),c);
 }
 c.updateShoppingAddButton=()=>{};
 vm.runInContext('renderShoppingList()',c);
 return {text:text(list),list};
}
test('recipe adapter → real matcher → optimizer → basket → API → shopping renderer, EN/ES',()=>{
 for(const locale of ['en','es']){
  const r=render(fixtures[0],locale);
  assert.match(r.text,locale==='en'?/Best deal/:/Mejor oferta/);
  assert.match(r.text,locale==='en'?/Save \$1.20/:/Ahorra 1,20/);
  assert.match(r.text,/Domino Premium/);assert.match(r.text,locale==='en'?/total for this recipe/:/total para esta receta/);
  assert.doesNotMatch(r.text,/quality_tier|0\.97|Tier [ABC]/);
 }
});
test('one viable product and invalid cheap cola never produce badges or savings',()=>{
 for(const fixture of [fixtures[1],fixtures[2]]){
  const r=render(fixture);assert.doesNotMatch(r.text,/Best deal|Save \$|Zero Sugar Cola/);
 }
});
test('two packages uses recipe checkout cost, not shelf price',()=>{
 const r=render(fixtures[3]);assert.match(r.text,/\$8.00 total/);assert.match(r.text,/2 packages needed/);
});
test('unknown quantity safely hides deal claims and checkout totals',()=>{
 assert.doesNotMatch(render(fixtures[4]).text,/Best deal|Save \$|total for this recipe/);
});
test('slice unit survives the API and renderer',()=>{
 const r=render(fixtures[5]);assert.match(r.text,/6 slices cheddar cheese/);
});
test('legacy payload still renders pantry controls and quantity',()=>{
 const r=render({name:'Legacy meal',ingredients:[{recipe_ingredient:'rye bread',recipe_measure:'6 slices rye bread',product_name:'Rye Bread',package_size:'1 loaf'}]});
 assert.match(r.text,/6 slices rye bread/);assert.match(r.text,/Add to pantry/);assert.doesNotMatch(r.text,/Best deal|Save \$/);
});
test('untrusted product/ingredient HTML is rendered as text, never markup',()=>{
 const attack='<img src=x onerror=alert(1)><script>alert(1)</script>';
 const r=render({name:attack,ingredients:[{recipe_ingredient:attack,recipe_measure:attack,product_name:attack,package_size:attack}]});
 assert.ok(r.text.includes(attack));
 function walk(n){assert.ok(!['script','img'].includes(n.tag));n.children.forEach(walk)}walk(r.list);
});
test('untrusted external links cannot execute scripts or contain credentials',()=>{
 const start=source.indexOf('function safeExternalUrl('),end=source.indexOf('function getStoreErrorMessage(',start);
 const c=vm.createContext({URL});vm.runInContext(source.slice(start,end),c);
 for(const url of ['javascript:alert(1)','data:text/html,<script>alert(1)</script>','https://user:password@evil.example','//evil.example'])assert.equal(c.safeExternalUrl(url),'');
 assert.equal(c.safeExternalUrl('https://www.nyc.gov/help'),'https://www.nyc.gov/help');
});

test('active-store Shopping rows show product, package size, package price and checkout without internal scores',()=>{
 const r=render({},'en',[{id:'rice',store_id:'ctown:PS41_311',name:'rice',requestedIngredient:'rice',quantity:'8 ounce',dishName:'Scheduled meals',productName:'Carolina Rice',package_size:'16 ounce',package_price:2,packages_needed:1,checkout_cost:2,deal:{match_score:.99,quality_tier:'A'}}]);
 assert.match(r.text,/Carolina Rice · 16 ounce/);assert.match(r.text,/1 package\(s\) × \$2.00 · \$2.00 checkout/);assert.doesNotMatch(r.text,/match_score|quality_tier|0.99/);
});
