/* Canonical active store and request-scoped basket. Backend owns all price caching. */
(() => {
  'use strict';
  const key='snapp:active-store:v1';
  let id=null,result=null,sequence=0,controller=null,status="idle";
  try{id=localStorage.getItem(key);}catch(_){}
  const node=(tag,text)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;return n;};
  const list=document.getElementById('shopping-list');
  const header=node('section');header.className='active-shopping-store';header.setAttribute('aria-live','polite');
  if(list)list.before(header);
  function paint(message){
    header.replaceChildren();
    const store=window.SNAPP_STORES.stores.find(s=>s.id===id);
    const name=store?.retailer==='ctown'?'C-Town':store?.store_name||'Select a store';
    const badge=node('span',store?.retailer==='ctown'?'C':'MW');badge.className='retailer-badge';
    const change=node('button','Change store');change.type='button';change.addEventListener('click',()=>showPanel('my'));
    header.append(badge,node('strong',`Shopping at ${name}${store?.address?' — '+store.address:''}`),change);
    if(message)header.append(node('p',message));
    if(result){
      const amount=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(result.complete?result.basket_total:result.checkout_total_known);
      const total=node('p',result.complete?`Estimated checkout: ${amount}`:result.checkout_total_known>0?`Partial basket — ${amount} of known items`:'No reliable checkout estimate yet');total.className='checkout-summary-total';header.append(total);
      const group=(title,values)=>{if(!values?.length)return;const section=node('section');section.className='shopping-support-group';section.append(node('h4',title));const ul=node('ul');for(const value of values)ul.append(node('li',value));section.append(ul);header.append(section);};
      group('Pantry / already have',result.pantry_items);
      group('Unavailable / could not price',(result.unknown_cost_items||[]).map(item=>item.ingredients[0]));
    }
    if(typeof renderShoppingList==='function')renderShoppingList(true);
    if(typeof renderBudget==='function')renderBudget();
  }
  function recipes(){
    return scheduledMeals.map(window.SNAPP_RECIPE_REQUIREMENTS);
  }
  async function refresh(){
    const version=++sequence,storeId=id;controller?.abort();controller=new AbortController();result=null;
    const basket=recipes();
    if(!storeId||!basket.length){status="idle";paint(storeId?'Add recipes to price your basket.':'Choose your shopping store to see prices.');return;}
    status='loading';paint('Updating prices for your store…');
    try{
      const data=await window.SNAPP_PRICE_REQUEST('/api/shopping/compare',{store_ids:[storeId],recipes:basket,
        ...(typeof pantryItems!=='undefined'?{pantry_items:pantryItems.map(({name,quantity})=>({name,quantity}))}:{})},controller.signal);
      if(version!==sequence||id!==storeId)return;
      if(!data)throw new Error('Pricing unavailable');
      const priced=data.stores.find(s=>s.id===storeId);
      if(!priced||data.stores.length!==1)throw new Error('Store mismatch');
      result={...priced,basket_id:data.basket_id,versions:data.versions};status='ready';paint('Prices from your active store. Recipe quantities adjusted for servings and pantry. Fees and taxes excluded.');
    }catch(_){if(version===sequence){status='error';paint('Price temporarily unavailable');const retry=node('button','Retry');retry.type='button';retry.addEventListener('click',refresh);header.append(retry);}}
  }
  window.SNAPP_ACTIVE_STORE={get id(){return id;},get result(){return result;},get status(){return status;},refresh,
    select(next){if(!window.SNAPP_STORES.stores.some(s=>s.id===next))return;id=next;result=null;try{localStorage.setItem(key,id);}catch(_){}document.dispatchEvent(new Event('snapp:active-store'));return refresh();},
    items(){if(!result||result.id!==id)return [];return result.product_selections.map((p,index)=>({...p,store_id:id,store_name:result.store_name,inventory_version:result.inventory_version,package_price:p.deal?.package_price,cost_known:p.checkout_cost!=null,id:`${id}:${p.product_id}:${index}`,name:p.display_name||p.ingredients[0],requestedIngredient:p.display_name||p.ingredients[0],productName:p.product_name,pantryName:p.pantry_transfer?.name || (p.ingredients?.[0]||p.display_name||'').replace(/^\s*\d+(?:\.\d+)?(?:\s+\d+\/\d+|\/\d+)?\s*(?:(?:fluid ounces?|fl oz|ounces?|oz|pounds?|lbs?|grams?|g|milliliters?|ml|liters?|cups?|tablespoons?|teaspoons?|count|each|slices?|cloves?)\b\s*)?/i,''),pantryQuantity:p.pantry_transfer?.quantity || (p.total_required?.quantity!=null?`${p.total_required.quantity} ${p.total_required.unit||''}`:null),quantity:p.total_required?.quantity!=null?`${p.total_required.quantity} ${p.total_required.unit||''}`:p.packages_needed==null?'Quantity unverified':`${p.packages_needed} package(s)`,dishName:'Scheduled meals',category:'Other',deal:p.deal}));}
  };
  document.addEventListener('snapp:shopping-changed',refresh);
  window.SNAPP_STORES.subscribe(stores=>{if(stores.length&&!stores.some(s=>s.id===id)){id=null;result=null;}paint();});
})();
