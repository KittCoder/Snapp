const {test}=require('node:test');
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('Web/app.js','utf8');
function context(){
 const c=vm.createContext({authStateLoading:false,AbortController,setTimeout,clearTimeout,t:k=>k,window:{SNAPP_STORES:{stores:[{id:'a',store_name:'Store A'}]},SNAPP_ACTIVE_STORE:{id:'a'}},currentUser:{id:'user'},currentUserInfo:{onboarding_completed:false},hasCompletedOnboarding:info=>info.onboarding_completed});
 vm.runInContext(source.slice(source.indexOf('function isAccountSetupPending()'),source.indexOf('function onboardingCompletedStorageKey(')),c);
 return c;
}
test('setup gates incomplete accounts without requiring a grocery store',()=>{
 const c=context();assert.equal(c.isOnboardingRequired(),true);
 c.currentUserInfo.onboarding_completed=true;assert.equal(c.isOnboardingRequired(),false);
 c.window.SNAPP_ACTIVE_STORE.id=null;assert.equal(c.isOnboardingRequired(),false);
 c.currentUserInfo=null;assert.equal(c.isOnboardingRequired(),false);assert.equal(c.isAccountSetupPending(),true);
 c.currentUser=null;assert.equal(c.isOnboardingRequired(),false);
});
test('Home clears old recommendations and rejects a late response after sign-out',async()=>{
 const c=context();c.currentUserInfo.onboarding_completed=true;
 let resolve; c.fetchSaleIngredients=()=>new Promise(r=>resolve=r);
 c.saleIngredientsGrid={replaceChildren(){this.cleared=true;}};c.saleIngredientsStatus={textContent:''};
 c.document={getElementById:()=>null};c.t=k=>k;c.renderSaleIngredients=()=>assert.fail('Stale store products rendered');
 vm.runInContext(source.slice(source.indexOf('let homeSalesSequence ='),source.indexOf('async function generateRecipesForSaleIngredient')),c);
 const pending=c.loadSaleIngredients();assert.equal(c.saleIngredientsGrid.cleared,true);
 c.currentUser=null;resolve({sale_ingredients:[{store_id:'a'}]});await pending;
});
test('Home does not fetch products before onboarding is complete',async()=>{
 const c=context();c.saleIngredientsGrid={replaceChildren(){}};c.saleIngredientsStatus={};c.t=()=> 'Choose your store in setup';c.fetchSaleIngredients=()=>assert.fail('Fetched before setup');
 vm.runInContext(source.slice(source.indexOf('let homeSalesSequence ='),source.indexOf('async function generateRecipesForSaleIngredient')),c);
 await c.loadSaleIngredients();assert.match(c.saleIngredientsStatus.textContent,/setup/);
});
test('Home request includes selected store and rejects wrong-store responses',async()=>{
 const c=context();c.API_BASE_URL='https://example.com';c.getApiEndpoints=()=>['https://example.com/sale-ingredients'];
 let requested;c.fetch=async url=>{requested=url;return {ok:true,text:async()=>JSON.stringify({store_id:'b',sale_ingredients:[]})}};
 vm.runInContext(source.slice(source.indexOf('async function fetchSaleIngredients('),source.indexOf('function formatSaleMoney(')),c);
 await assert.rejects(c.fetchSaleIngredients('a'),/Store mismatch/);assert.match(requested,/store_id=a/);
});
test('Home renders Morton Williams products regardless of the shopping store',async()=>{
 const c=context();c.currentUserInfo.onboarding_completed=true;
 c.saleIngredientsGrid={replaceChildren(){}};c.saleIngredientsStatus={};c.document={getElementById:()=>null};c.t=k=>k;
 c.fetchSaleIngredients=async id=>({store_id:id,sale_ingredients:[{store_id:id,product_name:'Rice'}]});
 let products;c.renderSaleIngredients=items=>products=items;
 vm.runInContext(source.slice(source.indexOf('let homeSalesSequence ='),source.indexOf('async function generateRecipesForSaleIngredient')),c);
 await c.loadSaleIngredients();assert.equal(products[0].store_id,'morton-williams');assert.equal(products[0].product_name,'Rice');
});
test('stalled response bodies have a bounded deadline',async()=>{
 const c=context();c.API_BASE_URL='https://example.com';c.getApiEndpoints=()=>['https://example.com/sale-ingredients'];
 c.setTimeout=callback=>setTimeout(callback,5);c.fetch=async()=>({ok:true,text:()=>new Promise(()=>{})});
 vm.runInContext(source.slice(source.indexOf('async function fetchSaleIngredients('),source.indexOf('function formatSaleMoney(')),c);
 await assert.rejects(c.fetchSaleIngredients('a'),/home.salesTimeout/);
});
test('refresh waits for the profile without ever opening onboarding for a completed account',async()=>{
 const c=context();let resolve;
 c.authRenderSequence=0;c.activeAuthUserId='user';c.authLandingPending=true;c.activeAppMode='snapp';
 c.ONBOARDING_PANEL_ID='onboarding';c.SIGNED_IN_DEFAULT_PANEL_ID='home';c.SIGNED_OUT_DEFAULT_PANEL_ID='home';
 const panels=[];c.showPanel=id=>panels.push(id);
 c.document={body:{classList:{toggle(){}}},querySelector:()=>({id:panels.at(-1)})};
 for(const name of ['clearUserScopedTransientState','renderNavigationForAuthState','renderAccountForAuthState','syncSettingsFromUserInfo','syncSnapCalculatorHouseholdSize','renderHomeForAuthState','loadSavedStores','loadPantryItems','loadFavoriteRecipes','loadScheduledMeals','setAuthStatus','syncOnboardingFromUserInfo'])c[name]=()=>{};
 c.getDisplayUsername=()=> 'fixture';c.ensureUserInfo=()=>new Promise(r=>resolve=r);c.repairOnboardingCompletionIfNeeded=async(user,info)=>info;
 c.window.SNAPP_STORES.load=()=>assert.fail('Account setup must not wait for store selection');
 vm.runInContext(source.slice(source.indexOf('async function renderAuthState('),source.indexOf('async function handleSignOut(')),c);
 const pending=c.renderAuthState({id:'user'});
 assert.deepEqual(panels,['account-loading']);assert.equal(c.isAccountSetupPending(),true);assert.equal(c.isOnboardingRequired(),false);
 resolve({onboarding_completed:true});await pending;
 assert.deepEqual(panels,['account-loading','home']);assert.equal(c.authStateLoading,false);
});
test('unresolved store metadata does not block Home or onboarding',()=>{
 const c=context();c.currentUserInfo.onboarding_completed=true;c.window.SNAPP_STORES.settled=false;
 assert.equal(c.isAccountSetupPending(),false);assert.equal(c.isOnboardingRequired(),false);
 c.window.SNAPP_STORES.settled=true;assert.equal(c.isAccountSetupPending(),false);
});
class SaleNode {constructor(){this.children=[];}replaceChildren(){this.children=[];}append(...nodes){this.children.push(...nodes);}addEventListener(){} }
function salesContext(storage=new Map()) {
 const c=context();c.currentUserInfo.onboarding_completed=true;
 c.localStorage={getItem:key=>storage.get(key),setItem:(key,value)=>storage.set(key,value)};
 c.saleIngredientsGrid=new SaleNode();c.saleIngredientsStatus={};c.document={getElementById:()=>null,createElement:()=>new SaleNode()};
 c.rendered=[];c.renderSaleIngredients=items=>c.rendered.push(items);
 vm.runInContext(source.slice(source.indexOf('let homeSalesSequence ='),source.indexOf('async function generateRecipesForSaleIngredient')),c);
 return c;
}
const salesPayload={store_id:'morton-williams',sale_ingredients:[{store_id:'morton-williams',product_name:'Sale rice'}]};
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('public sales prefetch finishes during account startup and paints immediately after setup',async()=>{
 const c=salesContext();c.currentUserInfo=null;let calls=0;c.fetchSaleIngredients=async()=>{calls++;return salesPayload;};
 c.primeHomeSales();await settle();assert.equal(calls,1);assert.equal(c.rendered.length,0);
 c.currentUserInfo={onboarding_completed:true};const pending=c.loadSaleIngredients();
 assert.equal(c.rendered.length,1);await pending;assert.equal(calls,1);
});
test('persisted fresh sales display synchronously on reload with no network wait',async()=>{
 const storage=new Map(),first=salesContext(storage);first.fetchSaleIngredients=async()=>salesPayload;
 await first.loadSaleIngredients();const reloaded=salesContext(storage);
 reloaded.fetchSaleIngredients=()=>assert.fail('Fresh persisted sales should not wait on network');
 const pending=reloaded.loadSaleIngredients();assert.equal(reloaded.rendered[0][0].product_name,'Sale rice');await pending;
});
test('prefetch and repeated Home loads share one request and reject superseded rendering',async()=>{
 const c=salesContext();let resolve,calls=0;c.fetchSaleIngredients=()=>{calls++;return new Promise(r=>resolve=r);};
 c.primeHomeSales();const a=c.loadSaleIngredients(),b=c.loadSaleIngredients();assert.equal(calls,1);
 resolve(salesPayload);await Promise.all([a,b]);assert.equal(c.rendered.length,1);
});
test('sales retry automatically after a transient error without a button click',async()=>{
 const c=salesContext(),timers=[];c.setTimeout=(callback,ms)=>{timers.push({callback,ms});return timers.length;};c.clearTimeout=()=>{};
 let calls=0;c.fetchSaleIngredients=async()=>{if(++calls===1)throw new Error('Temporary failure');return salesPayload;};
 await c.loadSaleIngredients();assert.equal(timers[0].ms,1000);assert.equal(c.rendered.length,0);
 timers[0].callback();await settle();assert.equal(calls,2);assert.equal(c.rendered.length,1);
});
test('signing out prevents an automatic retry from fetching or painting',async()=>{
 const c=salesContext(),timers=[];c.setTimeout=callback=>{timers.push(callback);return timers.length;};c.clearTimeout=()=>{};
 let calls=0;c.fetchSaleIngredients=async()=>{calls++;throw new Error('Temporary failure');};
 await c.loadSaleIngredients();c.currentUser=null;timers[0]();await settle();assert.equal(calls,1);assert.equal(c.rendered.length,0);
});
test('auth callbacks release the Supabase lock before account reads; token refresh preserves loaded Home',async()=>{
 const c=context(),timers=[],renders=[];let listener,locked=false;
 c.currentUserInfo={onboarding_completed:true};c.authStateLoading=false;
 c.renderAuthState=async user=>{assert.equal(locked,false);renders.push(user?.id||null);};
 c.setTimeout=callback=>timers.push(callback);c.setAuthStatus=()=>{};
 c.supabaseClient={auth:{getSession:async()=>({data:{session:{user:{id:'user'}}}}),onAuthStateChange:callback=>listener=callback}};
 vm.runInContext(source.slice(source.indexOf('async function initializeAuth()'),source.indexOf('navButtons.forEach((button) =>\n  button.addEventListener')),c);
 await c.initializeAuth();assert.deepEqual(renders,['user']);
 locked=true;assert.equal(listener('TOKEN_REFRESHED',{user:{id:'user'}}),undefined);assert.equal(timers.length,0);
 assert.equal(listener('SIGNED_OUT',null),undefined);assert.equal(renders.length,1);locked=false;
 timers[0]();await settle();assert.deepEqual(renders,['user',null]);
});
