/* Background batches: recipe content never waits for store prices. */
(() => {
  'use strict';
  const entries=new Map();let queued=false,version=0,controller=null;
  const money=value=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value);
  const node=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
  function placeholder(entry,message){entry.host.className='recipe-store-price is-checking';entry.host.replaceChildren(node('small',message));}
  const storeName=()=>{const s=window.SNAPP_STORES.stores.find(s=>s.id===window.SNAPP_ACTIVE_STORE?.id);return s?.retailer==='ctown'?'C-Town':s?.store_name||'Store';};
  function unavailable(entry){placeholder(entry,'Price temporarily unavailable');entry.host.className='recipe-store-price is-unavailable';const retry=node('button','Retry');retry.type='button';retry.addEventListener('click',schedule);entry.host.append(retry);}
  async function refresh(){
    queued=false;const seq=++version;controller?.abort();controller=new AbortController();
    const storeId=window.SNAPP_ACTIVE_STORE?.id,store=window.SNAPP_STORES.stores.find(s=>s.id===storeId);
    const current=[...entries.values()].filter(e=>e.host.isConnected!==false);
    for(const entry of current)placeholder(entry,storeId?`${storeName()} · checking price…`:'Choose a shopping store to see prices.');
    if(!storeId||!current.length)return;
    const name=store?.retailer==='ctown'?'C-Town':store?.store_name||storeId;
    const groups=[];for(let i=0;i<current.length;i+=10)groups.push(current.slice(i,i+10));
    await Promise.all(groups.map(async group=>{
      try{
        const recipes=group.map(e=>window.SNAPP_RECIPE_REQUIREMENTS(e.recipe));
        const data=await window.SNAPP_PRICE_REQUEST('/api/recipes/store-prices',{
          store_id:storeId,recipes,pantry_items:typeof pantryItems==='undefined'?[]:pantryItems.map(({name,quantity})=>({name,quantity}))
        },controller.signal);
        if(seq!==version||window.SNAPP_ACTIVE_STORE.id!==storeId)return;
        if(!data||data.store_id!==storeId)throw new Error('Store mismatch');
        for(const [index,entry] of group.entries()){
          const result=data.prices.find(p=>p.recipe_id===recipes[index].id);
          if(!result||result.id!==storeId)throw new Error('Store mismatch');
          entry.host.className='recipe-store-price';
          entry.host.replaceChildren(node('small',`Estimated at ${name}${store?.address?' — '+store.address:''}`));
          entry.host.dataset.storeId=storeId;entry.host.dataset.inventoryVersion=result.inventory_version;
          const known=result.checkout_total_known;
          entry.host.append(node('strong',result.complete?`${money(result.basket_total)} total`:known>0?`${money(known)} known · partial estimate`:'Could not price this recipe yet'));
          const servings=recipes[index].target_servings||recipes[index].source_servings;
          if(result.complete&&servings)entry.host.append(node('small',`${money(result.basket_total/servings)} / serving`));
          if(!result.complete)entry.host.append(node('small',`${result.unknown_cost_items.length} unpriced`));
        }
      }catch(_){if(seq===version)for(const entry of group)unavailable(entry);}
    }));
  }
  function schedule(){if(queued)return;queued=true;Promise.resolve().then(refresh);}
  window.SNAPP_RECIPE_PRICES={register(card,recipe){const host=node('div','','recipe-store-price');card.append(host);entries.set(host,{host,recipe});placeholder({host},`${storeName()} · checking price…`);schedule();},refresh};
  document.addEventListener('snapp:active-store',()=>{++version;controller?.abort();for(const entry of entries.values())placeholder(entry,`${storeName()} · checking price…`);schedule();});
  document.addEventListener('snapp:shopping-changed',schedule);
})();
