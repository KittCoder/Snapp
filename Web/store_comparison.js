/* Whole-store comparison. Original Morton Williams shopping list stays unchanged. */
(() => {
  'use strict';
  const host=document.getElementById('store-comparison');
  if(!host)return;
  const selector=host.querySelector('[data-store-options]');
  const button=host.querySelector('[data-compare-stores]');
  const status=host.querySelector('[data-comparison-status]');
  const output=host.querySelector('[data-comparison-results]');
  let loaded=false,requestVersion=0,lastPayload=null,controller=null;
  const tx=(key,values={})=>window.SNAPP_I18N.t(key,values);
  const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;};
  const currency=value=>new Intl.NumberFormat(window.SNAPP_I18N.locale,{style:'currency',currency:'USD'}).format(value);
  async function api(path,body,signal){
    if(body)return window.SNAPP_PRICE_REQUEST(path,body,signal);
    let error;
    for(const endpoint of getApiEndpoints(path)){
      try{
        const response=await fetch(endpoint,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
        if(!response.ok)throw new Error('comparison unavailable');
        return await response.json();
      }catch(e){error=e;}
    }
    throw error||new Error('comparison unavailable');
  }
  function renderOptions(stores){
    selector.replaceChildren();
    const active=stores.find(store=>store.id===window.SNAPP_ACTIVE_STORE?.id);
    if(active)selector.append(node('span',[active.store_name,active.address,active.borough].filter(Boolean).join(' — ')));

  }
  if(window.SNAPP_STORES)window.SNAPP_STORES.subscribe(stores=>{if(loaded)renderOptions(stores);});
  async function load(){
    if(loaded)return;
    status.textContent=tx('stores.loading');
    try{
      const data=window.SNAPP_STORES ? {stores:await window.SNAPP_STORES.load()} : await api('/api/stores');selector.replaceChildren();
      renderOptions(data.stores);
      loaded=true;status.textContent='';
    }catch(_){status.textContent=tx('stores.unavailable');}
  }
  function recipes(){
    return scheduledMeals.map(window.SNAPP_RECIPE_REQUIREMENTS);
  }
  function render(data){
    output.replaceChildren();
    for(const store of data.stores){
      const card=node('article',null,'comparison-result');card.append(node('h3',[store.retailer==='food_bazaar'?'Food Bazaar':store.store_name,store.address].filter(Boolean).join(' — ')));
      if(store.borough)card.append(node('p',store.borough));
      if(store.verified_at)card.append(node('p',tx('stores.snapshot',{date:new Date(store.verified_at).toLocaleString(window.SNAPP_I18N.locale)})));
      if(store.best_basket)card.append(node('strong',tx('stores.bestBasket'),'comparison-best'));
      card.append(node('p',tx('stores.coverage',{found:store.coverage_count,total:store.ingredients_requested.length})));
      card.append(node('p',store.complete?tx('stores.total',{amount:currency(store.basket_total)}):tx('stores.subtotal',{amount:currency(store.checkout_total_known)})));
      if(!store.complete)card.append(node('p',tx('stores.unknown',{count:store.unknown_cost_items.length})));
      const details=node('details');details.append(node('summary',tx('stores.viewBasket')));const items=node('ul');
      for(const product of store.product_selections){
        const li=node('li');li.append(node('strong',product.display_name||product.ingredients[0]),node('p',product.product_name));
        const quality={a:'shopping.excellentMatch',b:'shopping.strongMatch',c:'shopping.goodMatch'}[String(product.deal?.quality_tier||'').toLowerCase()];
        if(quality)li.append(node('span',tx(quality)));
        if(product.effective_cost!=null)li.append(node('p',tx('stores.effectiveCost',{amount:currency(product.effective_cost)})));
        if(product.packages_needed!=null)li.append(node('p',tx('shopping.packagesNeeded',{count:product.packages_needed})));
        li.append(node('p',product.checkout_cost==null?tx('stores.costUnknown'):currency(product.checkout_cost)));
        if(product.deal?.best_deal)li.append(node('span',tx('shopping.bestDeal')));
        if(product.deal?.savings_vs_closest_match!=null)li.append(node('p',tx('shopping.saveAmount',{amount:currency(product.deal.savings_vs_closest_match)})));
        items.append(li);
      }
      for(const missing of store.ingredients_unmatched)items.append(node('li',tx('stores.missing',{ingredient:missing.ingredients[0]})));
      details.append(items);card.append(details);output.append(card);
    }
  }
  host.querySelector('details').addEventListener('toggle',async event=>{if(event.target.open)await load();});
  button.addEventListener('click',async()=>{
    const version=++requestVersion;const storeId=window.SNAPP_ACTIVE_STORE?.id;const ids=storeId?[storeId]:[];const basket=recipes();
    if(!ids.length||!basket.length){status.textContent=tx('stores.chooseBasket');return;}
    controller?.abort();controller=new AbortController();
    button.disabled=true;status.textContent=tx('stores.comparing');output.replaceChildren();
    try{
      const result=await api('/api/shopping/compare',{store_ids:ids,recipes:basket,...(typeof pantryItems!=='undefined'?{pantry_items:pantryItems.map(({name,quantity})=>({name,quantity}))}:{})},controller.signal);
      if(version!==requestVersion||window.SNAPP_ACTIVE_STORE?.id!==storeId)return;
      if(result.stores?.length!==1||result.stores[0].id!==storeId)throw new Error('Store mismatch');
      lastPayload=result;render(result);status.textContent=tx('stores.disclaimer');
    }catch(_){if(version===requestVersion)status.textContent=tx('stores.unavailable');}
    finally{if(version===requestVersion)button.disabled=false;}
  });
  document.addEventListener('snapp:active-store',()=>{
    controller?.abort();++requestVersion;lastPayload=null;output.replaceChildren();status.textContent='';button.disabled=false;
    if(window.SNAPP_STORES)renderOptions(window.SNAPP_STORES.stores);
  });
  document.addEventListener('snapp:shopping-changed',()=>{controller?.abort();++requestVersion;lastPayload=null;output.replaceChildren();status.textContent='';button.disabled=false;});
  document.addEventListener('snapp:localechange',()=>{if(lastPayload)render(lastPayload);});
})();
