const {test}=require('node:test');
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('Web/app.js','utf8');
const en=JSON.parse(fs.readFileSync('Web/i18n/en.json','utf8'));
function setupBudget(){
 const el=()=>({value:'',textContent:'',hidden:false,disabled:false,dataset:{},classList:{toggle(k,v){this[k]=v;}}});
 const nodes=Object.fromEntries(['budget-monthly-input','budget-balance-label','budget-pricing-status','budget-cost-label','budget-refresh-prices','budget-store-context'].map(k=>[k,el()]));
 const c=vm.createContext({document:{getElementById:k=>nodes[k],activeElement:null},window:{SNAPP_ACTIVE_STORE:{id:'store-a',status:'ready',result:{id:'store-a',complete:true,basket_total:20,checkout_total_known:20}},SNAPP_STORES:{stores:[{id:'store-a',retailer:'ctown',address:'330 Graham Avenue'}]}},scheduledMeals:[{}],budgetInput:{value:'100'},budgetEmptyMessage:el(),currentBudget:el(),remainingBudget:el(),budgetMealCount:el(),scheduledMealCost:el(),currencyFormatter:new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}),t:k=>en[k]});
 vm.runInContext(source.slice(source.indexOf('function getScheduledMealTotal('),source.indexOf('function getHouseholdSize(')),c);
 vm.runInContext(source.slice(source.indexOf('function renderBudget('),source.indexOf('function getPortionMacroValue(')),c);
 return {c,nodes};
}
test('selected store partial prices produce a usable, explicitly partial budget',()=>{
 const {c,nodes}=setupBudget();c.window.SNAPP_ACTIVE_STORE.result={id:'store-a',complete:false,basket_total:null,checkout_total_known:10.07,unknown_cost_items:[{}]};c.renderBudget();
 assert.equal(c.remainingBudget.textContent,'$89.93');assert.equal(c.scheduledMealCost.textContent,'$10.07');assert.match(nodes['budget-pricing-status'].textContent,/Partial estimate/);assert.equal(nodes['budget-balance-label'].textContent,'Budget after known items');
 assert.match(nodes['budget-store-context'].textContent,/C-Town.*330 Graham/);
});
test('zero-cost pantry baskets, empty schedules, and missing monthly budgets are distinct',()=>{
 const {c,nodes}=setupBudget();c.window.SNAPP_ACTIVE_STORE.result.basket_total=0;c.renderBudget();assert.equal(c.remainingBudget.textContent,'$100.00');
 c.scheduledMeals=[];c.window.SNAPP_ACTIVE_STORE.result=null;c.renderBudget();assert.equal(c.scheduledMealCost.textContent,'$0.00');assert.match(nodes['budget-pricing-status'].textContent,/Add recipes/);
 c.budgetInput.value='';c.renderBudget();assert.equal(c.remainingBudget.textContent,'—');assert.equal(c.currentBudget.textContent,'—');assert.equal(c.budgetEmptyMessage.hidden,false);
});
test('loading, pricing failure and stale-store results never borrow another stores total',()=>{
 const {c,nodes}=setupBudget();c.window.SNAPP_ACTIVE_STORE.result={id:'store-b',complete:true,basket_total:1};c.window.SNAPP_ACTIVE_STORE.status='loading';c.renderBudget();assert.equal(c.remainingBudget.textContent,'—');assert.match(nodes['budget-pricing-status'].textContent,/Updating/);assert.equal(nodes['budget-refresh-prices'].disabled,true);
 c.window.SNAPP_ACTIVE_STORE.status='error';c.renderBudget();assert.match(nodes['budget-pricing-status'].textContent,/could not be loaded/);assert.equal(nodes['budget-refresh-prices'].disabled,false);
 c.window.SNAPP_ACTIVE_STORE=null;c.renderBudget();assert.match(nodes['budget-pricing-status'].textContent,/Choose a shopping store/);
});
test('over-budget display and an in-progress budget edit survive repricing',()=>{
 const {c,nodes}=setupBudget();c.budgetInput.value='10';nodes['budget-monthly-input'].value='200';c.document.activeElement=nodes['budget-monthly-input'];c.renderBudget();assert.equal(nodes['budget-monthly-input'].value,'200');assert.equal(c.remainingBudget.textContent,'-$10.00');assert.equal(c.remainingBudget.classList['over-budget'],true);
});
test('single, bulk, and removal pantry mutations invalidate active-store pricing; bulk retains transfer quantities',async()=>{
 const inserted=[],events=[];let next=1;
 const c=vm.createContext({Event,document:{dispatchEvent:e=>events.push(e.type)},currentUser:{id:'u1'},pantryItems:[],renderPantryItems:()=>{},setPantryStatus:()=>{},getPantryErrorMessage:()=>'',t:()=>'',supabaseClient:{from:()=>({insert:rows=>{inserted.push(rows);const data=Array.isArray(rows)?rows.map(r=>({...r,id:next++})):{...rows,id:next++};return {select:()=>Array.isArray(rows)?Promise.resolve({data,error:null}):{single:async()=>({data,error:null})}};},delete:()=>({eq(){return this;},then(resolve){resolve({error:null});}})})}});
 vm.runInContext(source.slice(source.indexOf('function notifyPantryChanged('),source.indexOf('function showAuthMode(')),c);
 await c.addPantryItem('ground turkey breast','453.592 gram');
 await c.addPantryItems([{name:'onion',quantity:'display only',pantryName:'onion chopped',pantryQuantity:'118.294 milliliter'}]);
 assert.equal(inserted[1][0].name,'onion chopped');assert.equal(inserted[1][0].quantity,'118.294 milliliter');
 await c.deletePantryItem(1);assert.equal(events.length,3);assert.ok(events.every(e=>e==='snapp:shopping-changed'));
});
