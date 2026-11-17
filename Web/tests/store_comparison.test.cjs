const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
class E{constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.disabled=false;}append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}addEventListener(k,f){this.listeners[k]=f;}querySelectorAll(){return this.children.flatMap(n=>n.children||[]).filter(n=>n.tag==='input'&&n.checked);}}
const text=n=>[n.textContent||'',...n.children.map(text)].join(' ');
function setup(locale='en'){
 const controls={options:new E('div'),button:new E('button'),status:new E('p'),results:new E('div'),details:new E('details')};const host={querySelector:s=>s==='[data-store-options]'?controls.options:s==='[data-compare-stores]'?controls.button:s==='[data-comparison-status]'?controls.status:s==='[data-comparison-results]'?controls.results:controls.details};
 const copy=JSON.parse(fs.readFileSync(path.join(__dirname,'../i18n',locale+'.json')));const events={};const requests=[];
 const stores=[{id:'morton-williams',store_name:'Morton Williams'},{id:'ctown:A',store_name:'C-Town',address:'1 Test St',borough:'Bronx'}];
 const result={stores:[{id:'ctown:A',store_name:'C-Town',address:'1 Test St',borough:'Bronx',complete:false,best_basket:false,coverage_count:1,ingredients_requested:[{},{}],checkout_total_known:4,unknown_cost_items:[{}],ingredients_unmatched:[{ingredients:['8 oz rice']}],product_selections:[{ingredients:['8 oz cheese','10 oz cheese'],product_name:'Cheddar Cheese',checkout_cost:4,effective_cost:3,packages_needed:2,deal:{quality_tier:'A',best_deal:true,savings_vs_closest_match:1}}]}]};
 const context=vm.createContext({AbortController,setTimeout,clearTimeout,Intl,Date,console,document:{getElementById:()=>host,createElement:t=>new E(t),addEventListener:(n,f)=>events[n]=f},window:{SNAPP_ACTIVE_STORE:{id:'ctown:A'},SNAPP_I18N:{locale,t:(k,v={})=>(copy[k]||'').replace(/\{(\w+)\}/g,(_,key)=>v[key])}},getApiEndpoints:p=>[p],scheduledMeals:[{schedule_id:1,recipe:{ingredients:[{name:'cheese',quantity:8,unit:'oz',product_id:'must-not-send',price:999}]}}],fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>url==='/api/stores'?{stores}:result};}});
 vm.runInContext(fs.readFileSync('Web/store_pricing_transport.js','utf8'),context);
 vm.runInContext(fs.readFileSync('Web/recipe_requirements.js','utf8'),context);
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../store_comparison.js'),'utf8'),context);return {controls,requests,events,context};
}
test('compact selection preserves raw recipe quantities and never submits product packages',async()=>{
 const s=setup();await s.controls.details.listeners.toggle({target:{open:true}});assert.equal(s.controls.options.children.length,1);await s.controls.button.listeners.click();const payload=JSON.parse(s.requests[1].options.body);assert.deepEqual(payload.store_ids,['ctown:A']);assert.equal(payload.recipes[0].ingredients[0].quantity,8);assert.equal(payload.recipes[0].ingredients[0].product_id,undefined);assert.equal(payload.recipes[0].ingredients[0].price,undefined);assert.match(text(s.controls.results),/Known subtotal/);assert.doesNotMatch(text(s.controls.results),/Lowest complete basket total/);
});
test('English and Spanish show coverage, missing items, packages and within-store deals',async()=>{
 for(const locale of ['en','es']){const s=setup(locale);await s.controls.details.listeners.toggle({target:{open:true}});await s.controls.button.listeners.click();const value=text(s.controls.results);assert.match(value,locale==='en'?/Ingredients found: 1\/2/:/Ingredientes encontrados: 1\/2/);assert.match(value,locale==='en'?/Missing ingredient/:/Ingrediente faltante/);assert.match(value,locale==='en'?/Excellent match/:/Excelente coincidencia/);assert.match(value,locale==='en'?/2 packages needed/:/2 paquetes/);assert.match(value,/Cheddar Cheese/);}
});
test('schedule changes clear comparison and output uses text, not HTML',async()=>{
 const s=setup();await s.controls.details.listeners.toggle({target:{open:true}});await s.controls.button.listeners.click();assert.ok(s.controls.results.children.length);s.events['snapp:shopping-changed']();assert.equal(s.controls.results.children.length,0);assert.equal(s.controls.button.disabled,false);const source=fs.readFileSync(path.join(__dirname,'../store_comparison.js'),'utf8');assert.doesNotMatch(source,/innerHTML|geolocation/);
});
test('all comparison strings exist in English and Spanish with matching placeholders',()=>{
 const source=fs.readFileSync(path.join(__dirname,'../store_comparison.js'),'utf8');const en=JSON.parse(fs.readFileSync(path.join(__dirname,'../i18n/en.json')));const es=JSON.parse(fs.readFileSync(path.join(__dirname,'../i18n/es.json')));
 for(const [,key] of source.matchAll(/tx\('([^']+)'/g)){assert.ok(en[key],key);assert.ok(es[key],key);assert.deepEqual((en[key].match(/\{\w+\}/g)||[]).sort(),(es[key].match(/\{\w+\}/g)||[]).sort());}
});
test('only the active store is requested even if legacy selections contain other stores',async()=>{
 const s=setup();await s.controls.details.listeners.toggle({target:{open:true}});
 s.context.window.SNAPP_SELECTED_STORES=new Set(['ctown:A','morton-williams']);
 await s.controls.button.listeners.click();
 assert.deepEqual(JSON.parse(s.requests[1].options.body).store_ids,['ctown:A']);
 assert.equal(s.controls.results.children.length,1);
});
test('no selected store sends no pricing request',async()=>{
 const s=setup();s.context.window.SNAPP_ACTIVE_STORE.id=null;
 await s.controls.button.listeners.click();assert.equal(s.requests.length,0);
});
test('a wrong-store response is rejected',async()=>{
 const s=setup();s.context.window.SNAPP_ACTIVE_STORE.id='morton-williams';
 await s.controls.button.listeners.click();assert.equal(s.controls.results.children.length,0);
});
