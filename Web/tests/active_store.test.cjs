const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');
class E {constructor(){this.children=[];}append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}before(){}setAttribute(){}addEventListener(){}}
const text=n=>[n.textContent||'',...n.children.map(text)].join(' ');
function setup(){
 const events={},requests=[],values=new Map(),elements=[];
 const ids=['ctown:PS41_311','morton-williams','ctown:U41_186','food_bazaar:31553'];
 const context=vm.createContext({setTimeout,clearTimeout,Intl,AbortController,Event,localStorage:{getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)},scheduledMeals:[{recipe:{ingredients:['8 oz rice','2 oz butter']}}],renderShoppingList:()=>{},showPanel:()=>{},getApiEndpoints:p=>[p],document:{getElementById:()=>new E(),createElement:()=>{const e=new E();elements.push(e);return e;},addEventListener:(n,f)=>events[n]=f,dispatchEvent:e=>events[e.type]?.()},window:{SNAPP_STORES:{stores:ids.map(id=>({id,store_name:id,retailer:id.startsWith('food_bazaar:')?'food_bazaar':id.startsWith('ctown')?'ctown':'morton_williams',address:'Test street'})),subscribe:f=>f([])}},fetch:(url,options)=>new Promise(resolve=>requests.push({url,options,finish:(id,total,complete=true)=>resolve({ok:true,json:async()=>({basket_id:id,stores:[{id,store_name:id,inventory_version:'v1',complete,basket_total:complete?total:null,checkout_total_known:total,unknown_cost_items:complete?[]:[{ingredients:['butter'],reason:'UNKNOWN_COST'}],product_selections:[{product_id:id+'-rice',product_name:'Rice',ingredients:['8 oz rice'],checkout_cost:total,deal:{package_price:total}}]}]})})}))});
 vm.runInContext(fs.readFileSync('Web/store_pricing_transport.js','utf8'),context);
 vm.runInContext(fs.readFileSync('Web/recipe_requirements.js','utf8'),context);
 vm.runInContext(fs.readFileSync('Web/active_store.js','utf8'),context);return {api:context.window.SNAPP_ACTIVE_STORE,requests,values,elements,events};
}
test('canonical store switch invalidates prices and displays independent backend totals, preserves partial basket',async()=>{
 const s=setup();const ids=['ctown:PS41_311','morton-williams','ctown:U41_186','food_bazaar:31553'];
 for(const [i,id] of ids.entries()){
  const pending=s.api.select(id);assert.equal(s.api.result,null);assert.equal(s.api.items().length,0);
  assert.deepEqual(JSON.parse(s.requests[i].options.body),{store_ids:[id],recipes:[{id:'0',ingredients:['8 oz rice','2 oz butter']}]});
  s.requests[i].finish(id,[8,11,6,9][i],i!==1);await pending;
  assert.equal(s.api.result.id,id);assert.equal(s.api.items()[0].store_id,id);assert.equal(s.api.items()[0].inventory_version,'v1');assert.equal(s.api.items()[0].checkout_cost,[8,11,6,9][i]);assert.equal(s.values.get('snapp:active-store:v1'),id);
  assert.match(text(s.elements[0]),/Shopping at/);
  if(id.startsWith('food_bazaar:'))assert.match(text(s.elements[0]),/Food Bazaar/);
  if(i===1){assert.match(text(s.elements[0]),/Partial basket.*\$11.00/);assert.match(text(s.elements[0]),/Unavailable \/ could not price.*butter/);}
 }
});
test('late store A response cannot overwrite store B and old request is aborted',async()=>{
 const s=setup(),a=s.api.select('ctown:PS41_311'),b=s.api.select('ctown:U41_186');
 assert.equal(s.requests[0].options.signal.aborted,true);
 s.requests[1].finish('ctown:U41_186',6);await b;s.requests[0].finish('ctown:PS41_311',99);await a;
 assert.equal(s.api.result.id,'ctown:U41_186');assert.equal(s.api.result.basket_total,6);
 s.events['snapp:shopping-changed']();assert.equal(s.api.result,null);assert.equal(s.requests.length,3);s.requests[2].finish('ctown:U41_186',6);await new Promise(resolve=>setImmediate(resolve));
});
test('wrong-store server result is rejected',async()=>{const s=setup(),p=s.api.select('ctown:PS41_311');s.requests[0].finish('morton-williams',99);await p;assert.equal(s.api.result,null);assert.match(text(s.elements[0]),/Price temporarily unavailable/);});
