/* Store-scoped estimates shared by result cards and recipe details. */
(() => {
  'use strict';
  const entries=new Map(),cache=new Map(),inflight=new Map(),inventoryVersions=new Map();
  const CACHE_TTL=2*60*1000,MAX_AGE=15*60*1000,MAX_CACHE=128;
  let queued=false,version=0,controller=new AbortController();
  const formatter=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'});
  const money=value=>formatter.format(value);
  const node=(tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;};
  const currentStore=()=>window.SNAPP_STORES.stores.find(s=>s.id===window.SNAPP_ACTIVE_STORE?.id);
  const storeName=store=>store?.retailer==='food_bazaar'?'Food Bazaar':store?.retailer==='ctown'?'C-Town':store?.store_name||'Store';
  const pantry=()=>typeof pantryItems==='undefined'?[]:pantryItems.map(({name,quantity})=>({name,quantity}));
  const stable=value=>Array.isArray(value)?value.map(stable):value&&typeof value==='object'?Object.fromEntries(Object.keys(value).sort().filter(k=>value[k]!==undefined).map(k=>[k,stable(value[k])])):value;
  const normalized=text=>String(text||'').trim().replace(/\s+/g,' ').toLowerCase();
  function ingredientKey(item){
    if(typeof item==='string')return normalized(item);
    const raw=item?.raw||item?.original||item?.display||item?.measure||item?.text;
    // Trusted structured quantities and identity modifiers remain in the key.
    // Plain display wrappers can share the exact text representation of a card.
    const explicit=['quantity','amount','quantity_text','unit'].some(k=>item?.[k]!=null&&item[k]!=='');
    const words=new Set(normalized(raw).match(/[a-z0-9]+/g)||[]);
    const covered=['name','nameClean','originalName','note'].every(k=>(normalized(item?.[k]).match(/[a-z0-9]+/g)||[]).every(word=>words.has(word)));
    return raw&&!explicit&&covered?normalized(raw):stable(item);
  }
  function context(entry){
    entry.requirements=window.SNAPP_RECIPE_REQUIREMENTS(entry.recipe);
    const r=entry.requirements;
    return JSON.stringify(stable({store:window.SNAPP_ACTIVE_STORE?.id,source:r.source_servings,target:r.target_servings,
      ingredients:(r.extendedIngredients||r.ingredients||[]).map(ingredientKey),pantry:pantry()}));
  }
  function placeholder(entry,message){entry.presented=null;entry.refreshNote=null;entry.retryButton=null;entry.host.className='recipe-store-price is-checking';entry.host.replaceChildren(node('small',message));}
  function cached(key,store){
    const value=cache.get(key),expected=inventoryVersions.get(store?.id)||store?.inventory_version;
    if(!value)return null;
    if(Date.now()-value.time>=MAX_AGE||(expected&&value.result.inventory_version!==expected)){cache.delete(key);return null;}
    cache.delete(key);cache.set(key,value);return {result:value.result,stale:Date.now()-value.time>=CACHE_TTL};
  }
  function remember(key,result){
    const previous=inventoryVersions.get(result.id);
    if(previous&&previous!==result.inventory_version)for(const [k,v] of cache)if(v.result.id===result.id)cache.delete(k);
    inventoryVersions.set(result.id,result.inventory_version);
    cache.delete(key);cache.set(key,{time:Date.now(),result});
    while(cache.size>MAX_CACHE)cache.delete(cache.keys().next().value);
  }
  function render(entry,result){
    if(entry.presented===result&&entry.presentedKey===entry.key)return;
    entry.presented=result;entry.presentedKey=entry.key;entry.refreshNote=null;entry.retryButton=null;
    const store=currentStore(),name=storeName(store);
    entry.host.className='recipe-store-price';
    entry.host.replaceChildren(node('small',`Estimated at ${name}${store?.address?' — '+store.address:''}`));
    entry.host.dataset.storeId=result.id;entry.host.dataset.inventoryVersion=result.inventory_version;
    const known=result.checkout_total_known;
    entry.host.append(node('strong',result.complete?`${money(result.basket_total)} total`:known>0?`${money(known)} known · partial estimate`:'Could not price this recipe yet'));
    const servings=entry.requirements.target_servings||entry.requirements.source_servings;
    if(result.complete&&servings)entry.host.append(node('small',`${money(result.basket_total/servings)} / serving`));
    if(!result.complete){
      entry.host.append(node('small',`${result.unknown_cost_items.length} unpriced`));
      const details=node('details');details.append(node('summary','Why some ingredients are unpriced'));
      const reasons={NO_SAFE_MATCH:'No suitable product match',MISSING_RECIPE_QUANTITY:'Recipe quantity or unit is missing',QUANTITY_CONVERSION_UNAVAILABLE:'Cannot convert the recipe quantity to the package unit',PACKAGE_SIZE_UNAVAILABLE:'Store package size is missing or uncertain',UNKNOWN_COST:'Package price or quantity could not be verified'};
      const list=node('ul');
      for(const item of result.unknown_cost_items)list.append(node('li',`${item.ingredients?.[0]||'Ingredient'} — ${reasons[item.detail||item.reason]||reasons.UNKNOWN_COST}`));
      details.append(list);entry.host.append(details);
    }
    if(result.product_selections?.some(p=>p.warnings?.includes('recipe volume converted using standard ingredient weight')))entry.host.append(node('small','Volume-to-weight quantities use standard cooking estimates.'));
  }
  function unavailable(entry){
    const previous=cached(entry.key,currentStore());
    if(previous){render(entry,previous.result);refreshNote(entry,'Saved estimate · refresh unavailable');}
    else{placeholder(entry,'Price temporarily unavailable');entry.host.className='recipe-store-price is-unavailable';}
    if(!entry.retryButton){const retry=node('button','Retry');retry.type='button';retry.addEventListener('click',schedule);entry.host.append(retry);entry.retryButton=retry;}
  }
  function refreshNote(entry,message){
    if(!entry.refreshNote){entry.refreshNote=node('small',message);entry.host.append(entry.refreshNote);}
    else entry.refreshNote.textContent=message;
  }
  function update(entry){
    const key=context(entry),store=currentStore(),value=cached(key,store),changed=entry.key!==key;
    entry.key=key;
    if(value){
      render(entry,value.result);
      if(!value.stale)return false;
      refreshNote(entry,'Saved estimate · updating…');entry.state='refreshing';
      return Boolean(window.SNAPP_ACTIVE_STORE?.id&&!inflight.has(key));
    }
    if(changed||!entry.state)placeholder(entry,window.SNAPP_ACTIVE_STORE?.id?`${storeName(store)} · checking price…`:'Choose a shopping store to see prices.');
    entry.state='checking';
    return Boolean(window.SNAPP_ACTIVE_STORE?.id&&!inflight.has(key));
  }
  async function refresh(){
    queued=false;
    const seq=version,storeId=window.SNAPP_ACTIVE_STORE?.id,signal=controller.signal,missing=new Map();
    for(const [host,entry] of entries){
      if(host.isConnected===false){entries.delete(host);continue;}
      if(update(entry))missing.set(entry.key,{key:entry.key,requirements:entry.requirements});
    }
    if(!storeId||!missing.size)return;
    const groups=[];let group=[],count=0;
    for(const task of missing.values()){
      const size=(task.requirements.extendedIngredients||task.requirements.ingredients||[]).length;
      if(group.length&&(group.length===10||count+size>250)){groups.push(group);group=[];count=0;}
      group.push(task);count+=size;
    }
    if(group.length)groups.push(group);
    const token={};for(const task of missing.values())inflight.set(task.key,token);
    await Promise.all(groups.map(async tasks=>{
      try{
        const recipes=tasks.map((task,index)=>({...task.requirements,id:String(index)}));
        const data=await window.SNAPP_PRICE_REQUEST('/api/recipes/store-prices',{store_id:storeId,recipes,pantry_items:pantry()},signal);
        if(seq!==version||signal.aborted||window.SNAPP_ACTIVE_STORE?.id!==storeId)return;
        if(data?.store_id!==storeId||!Array.isArray(data.prices))throw new Error('Store mismatch');
        const results=tasks.map((task,index)=>{
          const result=data.prices.find(p=>p.recipe_id===String(index));
          if(!result||result.id!==storeId||!result.inventory_version)throw new Error('Store mismatch');
          return result;
        });
        tasks.forEach((task,index)=>{
          remember(task.key,results[index]);
          for(const entry of entries.values())if(entry.key===task.key){render(entry,results[index]);entry.state='ready';}
        });
      }catch(_){
        if(seq===version&&!signal.aborted)for(const task of tasks)for(const entry of entries.values())if(entry.key===task.key){unavailable(entry);entry.state='error';}
      }finally{for(const task of tasks)if(inflight.get(task.key)===token)inflight.delete(task.key);}
    }));
  }
  function schedule(){if(queued)return;queued=true;Promise.resolve().then(refresh);}
  function invalidate(){
    ++version;controller.abort();controller=new AbortController();inflight.clear();
    for(const entry of entries.values()){entry.key=null;update(entry);}schedule();
  }
  window.SNAPP_RECIPE_PRICES={
    register(card,recipe){
      for(const [host] of entries)if(host.isConnected===false)entries.delete(host);
      const host=node('div','','recipe-store-price'),entry={host,recipe,key:null};card.append(host);entries.set(host,entry);
      if(update(entry))schedule();
      return host;
    },
    refresh:invalidate
  };
  document.addEventListener('snapp:active-store',invalidate);
  document.addEventListener('snapp:shopping-changed',invalidate);
  window.SNAPP_STORES.subscribe?.(stores=>{
    for(const store of stores)if(store.inventory_version){
      const previous=inventoryVersions.get(store.id);
      inventoryVersions.set(store.id,store.inventory_version);
      if(previous&&previous!==store.inventory_version)invalidate();
    }
  });
})();
