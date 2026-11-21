const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class E{constructor(){this.children=[];this.dataset={};this.isConnected=true;this.listeners={};}append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}addEventListener(k,f){this.listeners[k]=f;}}
const text=n=>[n.textContent||'',...n.children.map(text)].join(' ');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function setup(){
 const events={},requests=[],cards=[],storeListeners=[];
 const context=vm.createContext({setTimeout,clearTimeout,Intl,AbortController,Event,Promise,getHouseholdSize:()=>2,pantryItems:[],getApiEndpoints:p=>[p],document:{createElement:()=>new E(),addEventListener:(n,f)=>events[n]=f},window:{SNAPP_ACTIVE_STORE:{id:'ctown:PS41_311'},SNAPP_STORES:{subscribe:fn=>storeListeners.push(fn),stores:[{id:'ctown:PS41_311',retailer:'ctown',address:'330 Graham Avenue'},{id:'morton-williams',store_name:'Morton Williams'}]}},fetch:(url,options)=>new Promise(resolve=>requests.push({url,options,finish:(partial=false,overrides={})=>{const payload=JSON.parse(options.body);resolve({ok:true,json:async()=>({store_id:payload.store_id,prices:payload.recipes.map(r=>({id:payload.store_id,recipe_id:r.id,inventory_version:'v2',complete:!partial,basket_total:partial?null:8,checkout_total_known:partial?3:8,unknown_cost_items:partial?[{}]:[],...overrides}))})});}}))});
 for(const file of ['recipe_requirements.js','store_pricing_transport.js','recipe_store_prices.js'])vm.runInContext(fs.readFileSync('Web/'+file,'utf8'),context);
 return {context,requests,events,cards,storeListeners,register(recipe){const card=new E();cards.push(card);context.window.SNAPP_RECIPE_PRICES.register(card,recipe);return card;}};
}
test('five cards render immediately and populate with one background batch including quantities and servings',async()=>{
 const s=setup();for(let i=0;i<5;i++)s.register({id:'r'+i,servings:4,ingredients_text:['1 lb ground beef']});
 assert.equal(s.cards.length,5);assert.equal(s.requests.length,0);assert.match(text(s.cards[0]),/C-Town · checking price/);
 await tick();assert.equal(s.requests.length,1);const body=JSON.parse(s.requests[0].options.body);assert.equal(body.recipes.length,1);assert.deepEqual(body.recipes[0].ingredients,['1 lb ground beef']);assert.equal(body.recipes[0].source_servings,4);assert.equal(body.recipes[0].target_servings,2);
 s.requests[0].finish();await tick();for(const card of s.cards){assert.match(text(card),/C-Town — 330 Graham Avenue/);assert.match(text(card),/\$8.00 total/);assert.match(text(card),/\$4.00 \/ serving/);}
});
test('switch clears old prices immediately; late old-store response is ignored and partial stays partial',async()=>{
 const s=setup();const card=s.register({id:'r',ingredients_text:['8 oz rice','2 oz butter']});await tick();
 s.context.window.SNAPP_ACTIVE_STORE.id='morton-williams';s.events['snapp:active-store']();assert.doesNotMatch(text(card),/\$/);assert.match(text(card),/checking price/);await tick();assert.equal(s.requests.length,2);assert.equal(s.requests[0].options.signal.aborted,true);
 s.requests[1].finish(true);await tick();assert.match(text(card),/Morton Williams/);assert.match(text(card),/\$3.00 known · partial/);assert.doesNotMatch(text(card),/\/ serving/);
 s.requests[0].finish();await tick();assert.doesNotMatch(text(card),/C-Town|\$8.00/);
});
test('no active store means no pricing request and no dollar amount',async()=>{const s=setup();s.context.window.SNAPP_ACTIVE_STORE.id=null;const card=s.register({id:'r',ingredients:['8 oz rice']});await tick();assert.equal(s.requests.length,0);assert.match(text(card),/Choose a shopping store/);assert.doesNotMatch(text(card),/\$/);});
test('detail display and measure fields survive save serialization and target servings remain stable',()=>{const s=setup();const meal={recipe_id:'real',target_servings:8,recipe:{servings:4,ingredients:[{name:'beef',display:'1 lb ground beef',measure:'1 pound ground beef'}]}};const saved=JSON.parse(JSON.stringify(meal));const result=s.context.window.SNAPP_RECIPE_REQUIREMENTS(saved);assert.equal(result.ingredients[0].display,'1 lb ground beef');assert.equal(result.source_servings,4);assert.equal(result.target_servings,8);});
test('timeout removes compact checking status and offers a retry without changing recipes',async()=>{const s=setup();let expire;const timers=new Set();s.context.setTimeout=fn=>{expire=fn;timers.add(fn);return fn;};s.context.clearTimeout=fn=>timers.delete(fn);const card=s.register({id:'r',ingredients:['8 oz rice']});await tick();assert.match(text(card),/C-Town · checking price/);expire();await tick();assert.match(text(card),/Price temporarily unavailable.*Retry/);assert.doesNotMatch(text(card),/checking price/);assert.doesNotMatch(card.children[0].className,/is-checking/);assert.equal(timers.size,0);card.children[0].children[1].listeners.click();await tick();assert.equal(s.requests.length,2);s.requests[1].finish();await tick();assert.match(text(card),/\$8.00 total/);});
test('ingredient-heavy cards split into valid batches and each card has its own request identity',async()=>{
 const s=setup();for(let i=0;i<10;i++)s.register({id:'same',ingredients:Array(30).fill('1 oz rice '+i)});
 await tick();assert.equal(s.requests.length,2);
 for(const request of s.requests){const body=JSON.parse(request.options.body);assert.ok(body.recipes.reduce((n,r)=>n+r.ingredients.length,0)<=250);assert.equal(new Set(body.recipes.map(r=>r.id)).size,body.recipes.length);request.finish();}
 await tick();for(const card of s.cards)assert.match(text(card),/\$8.00 total/);
});

test('partial recipe prices explain missing matches separately from quantity problems',async()=>{
 const s=setup(),card=s.register({ingredients:['1 cup flour','chicken']});await tick();
 s.requests[0].finish(true,{unknown_cost_items:[{ingredients:['1 cup flour'],reason:'UNKNOWN_COST',detail:'QUANTITY_CONVERSION_UNAVAILABLE'},{ingredients:['chicken'],reason:'NO_SAFE_MATCH'}]});await tick();
 assert.match(text(card),/Why some ingredients are unpriced/);
 assert.match(text(card),/1 cup flour — Cannot convert the recipe quantity/);
 assert.match(text(card),/chicken — No suitable product match/);
 assert.match(text(card),/partial estimate/);
});

test('opening an already priced recipe paints its estimate synchronously and sends no duplicate request',async()=>{
 const s=setup(),recipe={id:'r',servings:4,ingredients_text:['8 oz rice']};
 s.register(recipe);await tick();s.requests[0].finish();await tick();
 const detail=s.register({id:'r',servings:4,ingredients:[{name:'rice',display:'8 oz rice'}]});
 assert.match(text(detail),/\$8.00 total/);assert.doesNotMatch(text(detail),/checking price/);
 await tick();assert.equal(s.requests.length,1);
});
test('new cards join matching in-flight prices without aborting or restarting existing work',async()=>{
 const s=setup(),recipe={ingredients:['8 oz rice']};const first=s.register(recipe);await tick();
 const second=s.register(recipe);await tick();assert.equal(s.requests.length,1);assert.equal(s.requests[0].options.signal.aborted,false);
 s.requests[0].finish();await tick();assert.match(text(first),/\$8.00/);assert.match(text(second),/\$8.00/);
 const third=s.register({ingredients:['2 oz butter']});await tick();
 assert.match(text(first),/\$8.00/);assert.equal(s.requests.length,2);assert.equal(JSON.parse(s.requests[1].options.body).recipes.length,1);
 s.requests[1].finish();await tick();assert.match(text(third),/\$8.00/);
});
test('cache separates authoritative quantities, servings, pantry quantities and stores',async()=>{
 const s=setup(),recipe={id:'r',servings:4,ingredients:['8 oz rice']};s.register(recipe);await tick();s.requests[0].finish();await tick();
 const different=s.register({id:'r',servings:4,ingredients:[{name:'rice',display:'8 oz rice',quantity:16,unit:'oz'}]});
 assert.doesNotMatch(text(different),/\$/);await tick();assert.equal(s.requests.length,2);s.requests[1].finish();await tick();
 const scaled=s.register({...recipe,target_servings:8});assert.doesNotMatch(text(scaled),/\$/);await tick();s.requests[2].finish();await tick();
 s.context.pantryItems=[{name:'rice',quantity:'4 oz'}];s.events['snapp:shopping-changed']();await tick();
 assert.equal(s.requests.length,4);assert.equal(JSON.parse(s.requests[3].options.body).pantry_items[0].quantity,'4 oz');s.requests[3].finish();await tick();
 s.context.window.SNAPP_ACTIVE_STORE.id='morton-williams';s.events['snapp:active-store']();
 assert.doesNotMatch(text(s.cards[0]),/\$/);await tick();s.requests[4].finish();await tick();
});
test('expired estimates and changed inventory versions reprice instead of returning stale totals',async()=>{
 const s=setup(),recipe={ingredients:['8 oz rice']};let now=1000;s.context.Date={now:()=>now};
 s.register(recipe);await tick();s.requests[0].finish();await tick();
 now+=120001;const expired=s.register(recipe);assert.match(text(expired),/\$8.00/);assert.match(text(expired),/Saved estimate.*updating/);await tick();s.requests[1].finish();await tick();
 const store=s.context.window.SNAPP_STORES.stores[0];store.inventory_version='v3';s.storeListeners.forEach(fn=>fn([store]));
 assert.doesNotMatch(text(expired),/\$/);await tick();assert.equal(s.requests.length,3);s.requests[2].finish(false,{inventory_version:'v3'});await tick();
 const fresh=s.register(recipe);assert.match(text(fresh),/\$8.00/);await tick();assert.equal(s.requests.length,3);
});
test('a newly registered card cannot cause a late prior-store response to enter the cache',async()=>{
 const s=setup(),recipe={ingredients:['8 oz rice']};s.register(recipe);await tick();
 s.context.window.SNAPP_ACTIVE_STORE.id='morton-williams';s.events['snapp:active-store']();await tick();
 s.requests[0].finish();await tick();const card=s.register(recipe);assert.doesNotMatch(text(card),/\$/);
 s.requests[1].finish(true);await tick();assert.match(text(card),/\$3.00 known.*partial/);
 const cached=s.register(recipe);assert.match(text(cached),/\$3.00 known.*partial/);await tick();assert.equal(s.requests.length,2);
});

test('hard-expired estimates are recalculated rather than presented as current',async()=>{
 const s=setup(),recipe={ingredients:['8 oz rice']};let now=1000;s.context.Date={now:()=>now};
 s.register(recipe);await tick();s.requests[0].finish();await tick();
 now+=15*60*1000+1;const card=s.register(recipe);assert.doesNotMatch(text(card),/\$/);await tick();
 assert.equal(s.requests.length,2);s.requests[1].finish();await tick();assert.match(text(card),/\$8.00/);
});
test('refreshing another card preserves an expanded partial-estimate explanation',async()=>{
 const s=setup(),card=s.register({ingredients:['8 oz rice']});await tick();s.requests[0].finish(true);await tick();
 const host=card.children[0],details=host.children.find(child=>child.children.some(n=>n.textContent==='Why some ingredients are unpriced'));
 details.open=true;s.register({ingredients:['2 oz butter']});await tick();
 assert.equal(host.children.includes(details),true);assert.equal(details.open,true);s.requests[1].finish();await tick();
});

test('a completed streamed price paints its card and cache before the batch finishes',async()=>{
 const s=setup();let publish,finish;
 s.context.window.SNAPP_PRICE_REQUEST=(path,body,signal,timeout,onPrice)=>new Promise(resolve=>{publish=onPrice;finish=resolve;});
 const first=s.register({ingredients:['8 oz rice']}),second=s.register({ingredients:['2 oz butter']});await tick();
 const price={id:'ctown:PS41_311',recipe_id:'0',inventory_version:'v2',complete:true,basket_total:8,checkout_total_known:8,unknown_cost_items:[]};
 publish({store_id:price.id,price});
 assert.match(text(first),/\$8.00 total/);assert.match(text(second),/checking price/);
 const reopened=s.register({ingredients:['8 oz rice']});assert.match(text(reopened),/\$8.00 total/);
 finish({store_id:price.id,prices:[price,{...price,recipe_id:'1'}]});await tick();assert.match(text(second),/\$8.00 total/);
});

test('all cards assembled in a detached chat response remain registered until mounted',async()=>{
 const s=setup(),hosts=[];
 for(let i=0;i<5;i++){
  const card=s.register({id:'r'+i,ingredients:[String(i+1)+' oz rice']});
  const host=card.children[0];host.isConnected=false;hosts.push(host);
 }
 // recipeCard builds the entire response before history.append mounts it.
 hosts.forEach(host=>host.isConnected=true);
 await tick();assert.equal(s.requests.length,1);
 assert.equal(JSON.parse(s.requests[0].options.body).recipes.length,5);
 s.requests[0].finish();await tick();
 for(const card of s.cards)assert.match(text(card),/\$8.00 total/);
});

test('physical cooking supplies stay visible separately from the food estimate',async()=>{
 const s=setup(),card=s.register({ingredients:['1 oz rice','20 toothpicks']});await tick();
 s.requests[0].finish(false,{recipe_supplies:['20 toothpicks']});await tick();
 assert.match(text(card),/\$8.00 total/);assert.match(text(card),/Cooking supplies not included in the food estimate: 20 toothpicks/);
});
