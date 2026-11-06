/* Shared metadata only. One refresh per page, with bounded persistent fallback. */
(() => {
  'use strict';
  const key='snapp:stores:v1', ttl=20*60*1000;
  let stores=[], pending=null, fetched=false, settled=false, error=null;
  const listeners=new Set();
  const fields=['id','store_name','retailer','address','borough','zip_code','latitude','longitude','product_count','verified_at'];
  function normalize(rows){
    if(!Array.isArray(rows))throw new Error('Invalid store registry');
    const seen=new Set();
    return rows.filter(s=>s&&typeof s.id==='string'&&!seen.has(s.id)&&seen.add(s.id)&&s.active!==false&&s.status!=='INACTIVE').map(s=>Object.fromEntries(fields.map(k=>[k,s[k]??null])));
  }
  try { const cached=JSON.parse(localStorage.getItem(key)); if(cached&&Date.now()-cached.time<ttl&&cached.time<=Date.now())stores=normalize(cached.stores); } catch(_){}
  function emit(){for(const listener of listeners)listener(stores,error);}
  async function load(){
    if(pending)return pending;
    if(fetched)return stores;
    pending=(async()=>{
      try{
        let result,last;
        for(const endpoint of getApiEndpoints('/api/stores')){
          try{const response=await fetch(endpoint);if(!response.ok)throw new Error('Registry unavailable');result=normalize((await response.json()).stores);break;}catch(e){last=e;}
        }
        if(!result)throw last||new Error('Registry unavailable');
        stores=result;error=null;fetched=true;
        try{localStorage.setItem(key,JSON.stringify({time:Date.now(),stores}));}catch(_){}
      }catch(e){error=e;}
      settled=true;emit();return stores;
    })();
    try{return await pending;}finally{pending=null;}
  }
  window.SNAPP_STORES={load,normalize,subscribe(listener){listeners.add(listener);listener(stores,error);return()=>listeners.delete(listener);},get stores(){return stores;},get settled(){return settled;}};
})();
