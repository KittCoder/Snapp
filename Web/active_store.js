/* Canonical active store and request-scoped basket. Backend owns all price caching. */
(() => {
  'use strict';
  const key='snapp:active-store:v1';
  let id=null,result=null,sequence=0,controller=null;
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
      header.append(node('p',result.complete?`Checkout total: ${amount}`:`Partial basket — ${amount} of known items`));
      for(const item of result.unknown_cost_items)header.append(node('p',`${item.ingredients.join(' + ')} — ${item.reason==='UNKNOWN_COST'?'Price unknown':'Unavailable'}`));
    }
    if(typeof renderShoppingList==='function')renderShoppingList(true);
    if(typeof renderBudget==='function')renderBudget();
  }
  function recipes(){
    return scheduledMeals.map((meal,index)=>{
      const original=meal.recipe||meal;
      const clean=item=>typeof item==='string'?item:Object.fromEntries(Object.entries(item||{}).filter(([k])=>['name','nameClean','original','originalName','amount','quantity','unit','raw','text','note','recipe_ingredient','recipe_measure','display','measure','type'].includes(k)));
      return {id:String(meal.schedule_id||index),name:meal.name,...(original.extendedIngredients?{extendedIngredients:original.extendedIngredients.map(clean)}:{ingredients:(original.ingredients||meal.ingredients||[]).map(clean)})};
    });
  }
  async function refresh(){
    const version=++sequence,storeId=id;controller?.abort();controller=new AbortController();result=null;
    const basket=recipes();
    if(!storeId||!basket.length){paint(storeId?'Add recipes to price your basket.':'Choose your shopping store to see prices.');return;}
    paint('Updating prices for your store…');
    try{
      let data,error;
      for(const endpoint of getApiEndpoints('/api/shopping/compare')){
        try{const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({store_ids:[storeId],recipes:basket})});if(!response.ok)throw new Error('Pricing unavailable');data=await response.json();break;}catch(e){error=e;if(version!==sequence)return;}
      }
      if(version!==sequence||id!==storeId)return;
      if(!data)throw error;
      const priced=data.stores.find(s=>s.id===storeId);
      if(!priced||data.stores.length!==1)throw new Error('Store mismatch');
      result={...priced,basket_id:data.basket_id,versions:data.versions};paint('Prices from your active store. Full recipe quantities; pantry deductions, fees and taxes excluded.');
    }catch(_){if(version===sequence)paint('Prices unavailable. Try again by selecting your store.');}
  }
  window.SNAPP_ACTIVE_STORE={get id(){return id;},get result(){return result;},refresh,
    select(next){if(!window.SNAPP_STORES.stores.some(s=>s.id===next))return;id=next;result=null;try{localStorage.setItem(key,id);}catch(_){}document.dispatchEvent(new Event('snapp:active-store'));return refresh();},
    items(){if(!result||result.id!==id)return [];return result.product_selections.map((p,index)=>({...p,store_id:id,store_name:result.store_name,inventory_version:result.inventory_version,package_price:p.deal?.package_price,cost_known:p.checkout_cost!=null,id:`${id}:${p.product_id}:${index}`,name:p.ingredients.join(' + '),requestedIngredient:p.ingredients.join(' + '),productName:p.product_name,quantity:p.packages_needed==null?'Quantity unverified':`${p.packages_needed} package(s)`,dishName:'Scheduled meals',category:'Other',deal:p.deal}));}
  };
  document.addEventListener('snapp:shopping-changed',refresh);
  window.SNAPP_STORES.subscribe(stores=>{if(stores.length&&!stores.some(s=>s.id===id)){id=null;result=null;}paint();});
})();
