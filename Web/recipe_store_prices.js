/* Background batches: recipe content never waits for store prices. */
(() => {
  'use strict';
  const entries=new Map();let queued=false,version=0,controller=null;
  const money=value=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value);
  const node=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
  function placeholder(entry,message){entry.host.replaceChildren(node('small',message));}
  async function refresh(){
    queued=false;const seq=++version;controller?.abort();controller=new AbortController();
    const storeId=window.SNAPP_ACTIVE_STORE?.id,store=window.SNAPP_STORES.stores.find(s=>s.id===storeId);
    const current=[...entries.values()].filter(e=>e.host.isConnected!==false);
    for(const entry of current)placeholder(entry,storeId?'Updating store prices…':'Choose a shopping store to see prices.');
    if(!storeId||!current.length)return;
    const name=store?.retailer==='ctown'?'C-Town':store?.store_name||storeId;
    const groups=[];for(let i=0;i<current.length;i+=10)groups.push(current.slice(i,i+10));
    await Promise.all(groups.map(async group=>{
      try{
        const recipes=group.map(e=>window.SNAPP_RECIPE_REQUIREMENTS(e.recipe));
        let data,error;
        for(const endpoint of getApiEndpoints('/api/recipes/store-prices')){
          try{const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({store_id:storeId,recipes,pantry_items:typeof pantryItems==='undefined'?[]:pantryItems.map(({name,quantity})=>({name,quantity}))})});if(!response.ok)throw new Error('Pricing unavailable');data=await response.json();break;}catch(e){error=e;if(seq!==version)return;}
        }
        if(seq!==version||window.SNAPP_ACTIVE_STORE.id!==storeId)return;
        if(!data||data.store_id!==storeId)throw error||new Error('Store mismatch');
        for(const [index,entry] of group.entries()){
          const result=data.prices.find(p=>p.recipe_id===recipes[index].id);
          if(!result||result.id!==storeId)throw new Error('Store mismatch');
          entry.host.replaceChildren(node('small',`Estimated at ${name}${store?.address?' — '+store.address:''}`));
          entry.host.dataset.storeId=storeId;entry.host.dataset.inventoryVersion=result.inventory_version;
          const known=result.checkout_total_known;
          entry.host.append(node('strong',result.complete?`${money(result.basket_total)} total`:known>0?`${money(known)} known · partial estimate`:'Could not price this recipe yet'));
          const servings=recipes[index].target_servings||recipes[index].source_servings;
          if(result.complete&&servings)entry.host.append(node('small',`${money(result.basket_total/servings)} / serving`));
          if(!result.complete)entry.host.append(node('small',`${result.unknown_cost_items.length} item(s) unavailable or unpriced`));
        }
      }catch(_){if(seq===version)for(const entry of group)placeholder(entry,`Price unavailable at ${name}.`);}
    }));
  }
  function schedule(){if(queued)return;queued=true;Promise.resolve().then(refresh);}
  window.SNAPP_RECIPE_PRICES={register(card,recipe){const host=node('div','','recipe-store-price');card.append(host);entries.set(host,{host,recipe});placeholder({host},'Checking store price…');schedule();},refresh};
  document.addEventListener('snapp:active-store',()=>{++version;controller?.abort();for(const entry of entries.values())placeholder(entry,'Updating store prices…');schedule();});
  document.addEventListener('snapp:shopping-changed',schedule);
})();
