/* Warming is independent of recipe search, ZIP entry and price rendering. */
(() => {
  'use strict';
  let last=null;const pending=new Set();
  function warm(){
    const id=window.SNAPP_ACTIVE_STORE?.id;
    if(!id||id===last||!window.SNAPP_STORES.stores.some(s=>s.id===id))return;
    last=id;
    if(pending.has(id))return;
    pending.add(id);
    window.SNAPP_PRICE_REQUEST('/api/stores/warm',{store_id:id}).catch(()=>{if(last===id)last=null;}).finally(()=>pending.delete(id));
  }
  document.addEventListener('snapp:active-store',warm);
  window.SNAPP_STORES.subscribe(warm);
})();
