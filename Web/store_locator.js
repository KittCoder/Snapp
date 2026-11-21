/* ZIP entry and distance ranking are strictly local. */
(() => {
  'use strict';
  const registry=window.SNAPP_STORES, zips=window.SNAPP_NYC_ZIPS;
  function rank(stores,zip){
    const center=/^\d{5}$/.test(zip)?zips[zip]:null;
    return stores.map(s=>{
      let distance_miles=null;
      if(center&&Number.isFinite(s.latitude)&&Number.isFinite(s.longitude)){
        const rad=n=>n*Math.PI/180, a=rad(s.latitude-center[0]),b=rad(s.longitude-center[1]);
        const h=Math.sin(a/2)**2+Math.cos(rad(center[0]))*Math.cos(rad(s.latitude))*Math.sin(b/2)**2;
        distance_miles=3958.7613*2*Math.asin(Math.sqrt(Math.min(1,h)));
      }
      return {...s,distance_miles};
    }).sort((a,b)=>(center?(a.distance_miles??Infinity)-(b.distance_miles??Infinity):0)||String(a.borough||'ZZZ').localeCompare(String(b.borough||'ZZZ'))||String(a.zip_code||'').localeCompare(String(b.zip_code||''))||a.id.localeCompare(b.id));
  }
  window.SNAPP_RANK_STORES=rank;
  const form=document.getElementById('my-store-form');if(!form)return;
  const input=document.getElementById('my-zip-code'),results=document.getElementById('my-store-results'),status=document.getElementById('my-store-status');
  let stores=[],failure=null,chain='all';
  document.querySelector?.('.store-recipe-link')?.addEventListener('click',event=>{
    const navigation=document.querySelector('[data-target="recipe-chat"]');
    if(navigation){event.preventDefault();navigation.click();}
  });
  const selectionKey='snapp:selected-stores:v1';
  let selected;
  try{selected=new Set(JSON.parse(localStorage.getItem(selectionKey))||['morton-williams']);}catch(_){selected=new Set(['morton-williams']);}
  window.SNAPP_SELECTED_STORES=selected;
  const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
  const brandName=store=>store.retailer==='food_bazaar'?'Food Bazaar':store.retailer==='ctown'?'C-Town':store.store_name||'Store';
  function brand(store){
    const badge=el('span',store.retailer==='food_bazaar'?'FB':store.retailer==='ctown'?'C':'MW');
    badge.className='retailer-badge retailer-logo';badge.setAttribute('data-retailer',store.retailer);badge.setAttribute('aria-hidden','true');
    const file={food_bazaar:'food-bazaar',ctown:'ctown',morton_williams:'morton-williams'}[store.retailer];
    if(file){const image=el('img');image.src='assets/stores/'+file+'.png';image.alt='';image.width=96;image.height=60;image.decoding='async';image.addEventListener('error',()=>{image.hidden=true;badge.className='retailer-badge';});badge.append(image);}
    return badge;
  }
  function filters(){
    const host=document.getElementById('store-chain-filters');if(!host)return;
    host.replaceChildren();
    const options=[['all','All locations'],['morton_williams','Morton Williams'],['ctown','C-Town'],['food_bazaar','Food Bazaar']];
    for(const [id,label] of options){
      const count=stores.filter(s=>id==='all'||s.retailer===id).length;
      if(!count&&id!=='all')continue;
      const button=el('button',label);button.type='button';button.className='store-chain-filter';button.setAttribute('aria-pressed',String(chain===id));
      button.append(el('span',String(count)));button.addEventListener('click',()=>{chain=id;render();});host.append(button);
    }
  }
  function render(){
    const zip=input.value.trim(),supported=!!zips[zip];
    results.replaceChildren();document.getElementById('my-store-start').hidden=true;
    document.getElementById('my-store-map').hidden=true;document.getElementById('my-store-source').hidden=true;
    status.textContent=(zip?(zip.length!==5?'Enter a valid 5-digit ZIP code.':supported?`Stores near ${zip}. Approximate straight-line distances.`:'That ZIP is outside our current NYC locator area.'):'Browse local stores, or enter a NYC ZIP to find your closest options.')+(failure?' Store refresh unavailable. Showing cached stores when available.':'');
    if(!stores.length){status.textContent=failure?'Stores unavailable. Please retry.':'Loading store metadata…';const retry=el('button','Retry');retry.type='button';retry.addEventListener('click',()=>registry.load());if(failure)results.append(retry);return;}
    filters();
    const visible=rank(stores,zip).filter(s=>chain==='all'||s.retailer===chain);
    for(const store of visible){
      const item=el('li');item.className='catalog-store-card';
      const name=store.retailer==='food_bazaar'?'Food Bazaar':store.retailer==='ctown'?'C-Town':store.store_name||'Store';
      const identity=el('div');identity.className='store-card-identity';
      const badge=brand(store);
      const details=el('div');details.append(el('h3',name),el('p',store.address||'Location unavailable'),el('p',[store.borough,store.zip_code].filter(Boolean).join(' · ')));identity.append(badge,details);
      const active=window.SNAPP_ACTIVE_STORE?.id===store.id;item.classList.toggle('selected',active);
      const meta=el('div');meta.className='store-card-meta';meta.append(el('span',store.product_count>0?'✓ Recipe pricing available':'Pricing unavailable'));
      if(supported)meta.append(el('span',store.distance_miles==null?'Distance unavailable':`${store.distance_miles.toFixed(1)} mi away`));
      const button=el('button',active?'✓ Shopping here':'Select store');button.type='button';button.value=store.id;button.setAttribute('aria-pressed',String(active));button.addEventListener('click',()=>window.SNAPP_ACTIVE_STORE.select(store.id));
      button.disabled=store.product_count<=0;
      item.append(identity,meta,button);results.append(item);
    }
    renderSelected();
  }
  function renderSelected(){
    const list=document.getElementById('selected-store-list');list.replaceChildren();
    const s=stores.find(s=>s.id===window.SNAPP_ACTIVE_STORE?.id);
    if(s){
      const row=el('li');row.className='active-store-summary';
      row.append(brand(s),el('strong',brandName(s)),el('p',s.address||'Available store catalog'),el('small','✓ Selected for recipe pricing'));list.append(row);
    }else{const row=el('li','Select a location to see prices for your next meal.');row.className='store-selection-empty';list.append(row);}
  }
  document.addEventListener('snapp:active-store',render);
  window.SNAPP_RENDER_SELECTED_STORES=renderSelected;
  try{input.value=localStorage.getItem('snapp:locator-zip')||'';}catch(_){}
  function lookup(){input.value=input.value.trim().replace(/\D/g,'').slice(0,5);try{localStorage.setItem('snapp:locator-zip',input.value);}catch(_){}render();}
  input.addEventListener('input',lookup);form.addEventListener('submit',e=>{e.preventDefault();lookup();});
  document.addEventListener('snapp:comparison-selection',render);
  registry.subscribe((rows,error)=>{stores=rows;failure=error;render();});registry.load();
})();
