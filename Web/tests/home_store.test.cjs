const {test}=require('node:test');
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('Web/app.js','utf8');
function context(){
 const c=vm.createContext({authStateLoading:false,AbortController,setTimeout,clearTimeout,t:k=>k,window:{SNAPP_STORES:{stores:[{id:'a',store_name:'Store A'}]},SNAPP_ACTIVE_STORE:{id:'a'}},currentUser:{id:'user'},currentUserInfo:{onboarding_completed:false},hasCompletedOnboarding:info=>info.onboarding_completed});
 vm.runInContext(source.slice(source.indexOf('function selectedShoppingStore()'),source.indexOf('function onboardingCompletedStorageKey(')),c);
 return c;
}
test('setup gates every incomplete account and accounts without a valid store',()=>{
 const c=context();assert.equal(c.isOnboardingRequired(),true);
 c.currentUserInfo.onboarding_completed=true;assert.equal(c.isOnboardingRequired(),false);
 c.window.SNAPP_ACTIVE_STORE.id='missing';assert.equal(c.isOnboardingRequired(),true);
 c.currentUserInfo=null;assert.equal(c.isOnboardingRequired(),false);assert.equal(c.isAccountSetupPending(),true);
 c.currentUser=null;assert.equal(c.isOnboardingRequired(),false);
});
test('Home clears old recommendations and rejects a late response after changing stores',async()=>{
 const c=context();c.currentUserInfo.onboarding_completed=true;
 let resolve; c.fetchSaleIngredients=()=>new Promise(r=>resolve=r);
 c.saleIngredientsGrid={replaceChildren(){this.cleared=true;}};c.saleIngredientsStatus={textContent:''};
 c.document={getElementById:()=>null};c.t=k=>k;c.renderSaleIngredients=()=>assert.fail('Stale store products rendered');
 vm.runInContext(source.slice(source.indexOf('let homeSalesSequence ='),source.indexOf('document.getElementById("home-change-store")')),c);
 const pending=c.loadSaleIngredients();assert.equal(c.saleIngredientsGrid.cleared,true);
 c.window.SNAPP_ACTIVE_STORE.id='b';resolve({sale_ingredients:[{store_id:'a'}]});await pending;
});
test('Home does not fetch products before onboarding is complete',async()=>{
 const c=context();c.saleIngredientsGrid={replaceChildren(){}};c.saleIngredientsStatus={};c.t=()=> 'Choose your store in setup';c.fetchSaleIngredients=()=>assert.fail('Fetched before setup');
 vm.runInContext(source.slice(source.indexOf('let homeSalesSequence ='),source.indexOf('document.getElementById("home-change-store")')),c);
 await c.loadSaleIngredients();assert.match(c.saleIngredientsStatus.textContent,/setup/);
});
test('Home request includes selected store and rejects wrong-store responses',async()=>{
 const c=context();c.API_BASE_URL='https://example.com';c.getApiEndpoints=()=>['https://example.com/sale-ingredients'];
 let requested;c.fetch=async url=>{requested=url;return {ok:true,text:async()=>JSON.stringify({store_id:'b',sale_ingredients:[]})}};
 vm.runInContext(source.slice(source.indexOf('async function fetchSaleIngredients('),source.indexOf('function formatSaleMoney(')),c);
 await assert.rejects(c.fetchSaleIngredients('a'),/Store mismatch/);assert.match(requested,/store_id=a/);
});
test('selected-store feed renders products immediately on successful response',async()=>{
 const c=context();c.currentUserInfo.onboarding_completed=true;
 c.saleIngredientsGrid={replaceChildren(){}};c.saleIngredientsStatus={};c.document={getElementById:()=>null};c.t=k=>k;
 c.fetchSaleIngredients=async id=>({store_id:id,sale_ingredients:[{store_id:id,product_name:'Rice'}]});
 let products;c.renderSaleIngredients=items=>products=items;
 vm.runInContext(source.slice(source.indexOf('let homeSalesSequence ='),source.indexOf('document.getElementById("home-change-store")')),c);
 await c.loadSaleIngredients();assert.equal(products[0].store_id,'a');assert.equal(products[0].product_name,'Rice');
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
 c.window.SNAPP_STORES.load=async()=>{};
 vm.runInContext(source.slice(source.indexOf('async function renderAuthState('),source.indexOf('async function handleSignOut(')),c);
 const pending=c.renderAuthState({id:'user'});
 assert.deepEqual(panels,['account-loading']);assert.equal(c.isAccountSetupPending(),true);assert.equal(c.isOnboardingRequired(),false);
 resolve({onboarding_completed:true});await pending;
 assert.deepEqual(panels,['account-loading','home']);assert.equal(c.authStateLoading,false);
});
test('unresolved store metadata is a loading state rather than incomplete onboarding',()=>{
 const c=context();c.currentUserInfo.onboarding_completed=true;c.window.SNAPP_STORES.settled=false;
 assert.equal(c.isAccountSetupPending(),true);assert.equal(c.isOnboardingRequired(),false);
 c.window.SNAPP_STORES.settled=true;assert.equal(c.isAccountSetupPending(),false);
});
