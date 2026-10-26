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
  let stores=[],failure=null;
  const selectionKey='snapp:selected-stores:v1';
  let selected;
  try{selected=new Set(JSON.parse(localStorage.getItem(selectionKey))||['morton-williams']);}catch(_){selected=new Set(['morton-williams']);}
  window.SNAPP_SELECTED_STORES=selected;
  const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
  function render(){
    const zip=input.value.trim(),supported=!!zips[zip];
    results.replaceChildren();document.getElementById('my-store-start').hidden=true;
    document.getElementById('my-store-map').hidden=true;document.getElementById('my-store-source').hidden=true;
    status.textContent=(zip?(zip.length!==5?'Enter a valid 5-digit ZIP code.':supported?`Stores near ${zip}. Approximate straight-line distances.`:'That ZIP is outside our current NYC locator area.'):'All catalog stores. Enter a NYC ZIP to sort by distance.')+(failure?' Store refresh unavailable. Showing cached stores when available.':'');
    if(!stores.length){status.textContent=failure?'Stores unavailable. Please retry.':'Loading store metadata…';const retry=el('button','Retry');retry.type='button';retry.addEventListener('click',()=>registry.load());if(failure)results.append(retry);return;}
    for(const store of rank(stores,zip)){
      const item=el('li'),title=el('h3',store.store_name),check=el('input');check.type='checkbox';check.value=store.id;check.checked=selected.has(store.id);check.setAttribute('aria-label',`Select ${store.store_name}, ${store.address||'catalog'}`);
      const label=el('label');label.append(check,el('span','Select store'));item.classList.toggle('selected',check.checked);
      item.append(title,el('p',store.retailer==='ctown'?'C-Town':store.retailer.replaceAll('_',' ')),el('p',store.address||'Physical location unavailable'),el('p',[store.borough,store.zip_code].filter(Boolean).join(' · ')),el('p',store.product_count>0?'Catalog available':'Catalog status unavailable'));
      if(supported)item.append(el('p',store.distance_miles==null?'Distance unavailable':`Approx. ${store.distance_miles.toFixed(1)} mi away`));
      check.addEventListener('change',()=>{if(check.checked)selected.add(store.id);else selected.delete(store.id);try{localStorage.setItem(selectionKey,JSON.stringify([...selected]));}catch(_){}item.classList.toggle('selected',check.checked);renderSelected();document.dispatchEvent(new Event('snapp:store-selection'));});
      item.append(label);results.append(item);
    }
    renderSelected();
  }
  function renderSelected(){const list=document.getElementById('selected-store-list');list.replaceChildren();for(const s of stores.filter(s=>selected.has(s.id)))list.append(el('li',[s.store_name,s.address].filter(Boolean).join(' — ')));}
  window.SNAPP_RENDER_SELECTED_STORES=renderSelected;
  try{input.value=localStorage.getItem('snapp:locator-zip')||'';}catch(_){}
  function lookup(){input.value=input.value.trim().replace(/\D/g,'').slice(0,5);try{localStorage.setItem('snapp:locator-zip',input.value);}catch(_){}render();}
  input.addEventListener('input',lookup);form.addEventListener('submit',e=>{e.preventDefault();lookup();});
  document.addEventListener('snapp:comparison-selection',render);
  registry.subscribe((rows,error)=>{stores=rows;failure=error;render();});registry.load();
})();
