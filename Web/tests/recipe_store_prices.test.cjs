const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class E{constructor(){this.children=[];this.dataset={};this.isConnected=true;}append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}}
const text=n=>[n.textContent||'',...n.children.map(text)].join(' ');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function setup(){
 const events={},requests=[],cards=[];
 const context=vm.createContext({Intl,AbortController,Event,Promise,getHouseholdSize:()=>2,pantryItems:[],getApiEndpoints:p=>[p],document:{createElement:()=>new E(),addEventListener:(n,f)=>events[n]=f},window:{SNAPP_ACTIVE_STORE:{id:'ctown:PS41_311'},SNAPP_STORES:{stores:[{id:'ctown:PS41_311',retailer:'ctown',address:'330 Graham Avenue'},{id:'morton-williams',store_name:'Morton Williams'}]}},fetch:(url,options)=>new Promise(resolve=>requests.push({url,options,finish:(partial=false)=>{const payload=JSON.parse(options.body);resolve({ok:true,json:async()=>({store_id:payload.store_id,prices:payload.recipes.map(r=>({id:payload.store_id,recipe_id:r.id,inventory_version:'v2',complete:!partial,basket_total:partial?null:8,checkout_total_known:partial?3:8,unknown_cost_items:partial?[{}]:[]}))})});}}))});
 for(const file of ['recipe_requirements.js','recipe_store_prices.js'])vm.runInContext(fs.readFileSync('Web/'+file,'utf8'),context);
 return {context,requests,events,cards,register(recipe){const card=new E();cards.push(card);context.window.SNAPP_RECIPE_PRICES.register(card,recipe);return card;}};
}
test('five cards render immediately and populate with one background batch including quantities and servings',async()=>{
 const s=setup();for(let i=0;i<5;i++)s.register({id:'r'+i,servings:4,ingredients_text:['1 lb ground beef']});
 assert.equal(s.cards.length,5);assert.equal(s.requests.length,0);assert.match(text(s.cards[0]),/Checking store price/);
 await tick();assert.equal(s.requests.length,1);const body=JSON.parse(s.requests[0].options.body);assert.equal(body.recipes.length,5);assert.deepEqual(body.recipes[0].ingredients,['1 lb ground beef']);assert.equal(body.recipes[0].source_servings,4);assert.equal(body.recipes[0].target_servings,2);
 s.requests[0].finish();await tick();for(const card of s.cards){assert.match(text(card),/C-Town — 330 Graham Avenue/);assert.match(text(card),/\$8.00 total/);assert.match(text(card),/\$4.00 \/ serving/);}
});
test('switch clears old prices immediately; late old-store response is ignored and partial stays partial',async()=>{
 const s=setup();const card=s.register({id:'r',ingredients_text:['8 oz rice','2 oz butter']});await tick();
 s.context.window.SNAPP_ACTIVE_STORE.id='morton-williams';s.events['snapp:active-store']();assert.doesNotMatch(text(card),/\$/);assert.match(text(card),/Updating/);await tick();assert.equal(s.requests.length,2);assert.equal(s.requests[0].options.signal.aborted,true);
 s.requests[1].finish(true);await tick();assert.match(text(card),/Morton Williams/);assert.match(text(card),/\$3.00 known · partial/);assert.doesNotMatch(text(card),/\/ serving/);
 s.requests[0].finish();await tick();assert.doesNotMatch(text(card),/C-Town|\$8.00/);
});
test('no active store means no pricing request and no dollar amount',async()=>{const s=setup();s.context.window.SNAPP_ACTIVE_STORE.id=null;const card=s.register({id:'r',ingredients:['8 oz rice']});await tick();assert.equal(s.requests.length,0);assert.match(text(card),/Choose a shopping store/);assert.doesNotMatch(text(card),/\$/);});
test('detail display and measure fields survive save serialization and target servings remain stable',()=>{const s=setup();const meal={recipe_id:'real',target_servings:8,recipe:{servings:4,ingredients:[{name:'beef',display:'1 lb ground beef',measure:'1 pound ground beef'}]}};const saved=JSON.parse(JSON.stringify(meal));const result=s.context.window.SNAPP_RECIPE_REQUIREMENTS(saved);assert.equal(result.ingredients[0].display,'1 lb ground beef');assert.equal(result.source_servings,4);assert.equal(result.target_servings,8);});
