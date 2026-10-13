/* Central locale manager. Canonical data and user-entered text never change. */
(() => {
  'use strict';
  const manifest=window.SNAPP_LOCALE_MANIFEST;
  const names=Object.fromEntries(Object.entries(manifest).map(([locale,entry])=>[locale,entry.name]));
  const english = window.SNAPP_EN_CATALOG || {};
  const resources = new Map([['en', english]]);
  const loads = new Map();
  const bindings = new WeakMap();
  const attributeBindings = new WeakMap();
  const reverseCopy = new Map();
  const templateBindings = [];
  const bindingCache = new Map();
  const warned = new Set();
  const keyByEnglish = new Map(Object.entries(english).map(([key,text]) => [text,key]));
  const dev = ['localhost','127.0.0.1'].includes(location.hostname);
  const normalize = value => names[value] ? value : value?.startsWith('zh') ? (value.includes('TW') || value.includes('Hant') ? 'zh-TW' : 'zh-CN') : names[value?.split('-')[0]] ? value.split('-')[0] : 'en';
  let locale = normalize(localStorage.getItem('snapp-language') || navigator.languages?.[0] || 'en');
  let revision = 0;
  let scheduled = false;
  const ignored = 'script,style,code,textarea,#global-language-select option,#language-select option,[data-i18n-ignore],.brand-name,.brand-logo,.store-identity-name,.pantry-item-details strong,.shopping-item-details strong,.recipe-chat-card h3,.recipe-chat-card li,.recipe-chat-text,.dish-modal-list';
  const fill = (template, values) => template.replace(/\{([A-Za-z0-9_]+)\}/g, (whole,key) => values[key] == null ? whole : String(values[key]));
  function t(key, values = {}) {
    const text = resources.get(locale)?.[key] || resources.get(locale.split('-')[0])?.[key] || english[key];
    if (!text && dev && !warned.has(key)) { warned.add(key); console.warn('Missing SNAPP translation:',key); }
    return fill(text || '', values);
  }
  function indexResource(copy) {
    bindingCache.clear();
    for (const [key,template] of Object.entries(copy)) {
      if (!template.includes('{')) { reverseCopy.set(template.trim().replace(/\s+/g,' '),key); continue; }
      const args=[];
      const pattern=template.split(/(\{[A-Za-z0-9_]+\})/).map(part=>{
        if(/^\{/.test(part)){args.push(part.slice(1,-1));return '(.*?)';}
        return part.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
      }).join('');
      templateBindings.push({key,args,pattern:new RegExp('^'+pattern+'$')});
    }
  }
  indexResource(english);
  function findBinding(value) {
    const trimmed=value.trim().replace(/\s+/g,' ');
    if(bindingCache.has(trimmed))return bindingCache.get(trimmed);
    let binding=reverseCopy.has(trimmed)?{key:reverseCopy.get(trimmed),values:{}}:null;
    if(!binding)for(const entry of templateBindings){
      const match=trimmed.match(entry.pattern);
      if(match){binding={key:entry.key,values:Object.fromEntries(entry.args.map((arg,i)=>[arg,match[i+1]]))};break;}
    }
    if(bindingCache.size>2048)bindingCache.clear();bindingCache.set(trimmed,binding);return binding;
  }
  function translate(text) {
    const binding=findBinding(String(text));return binding?t(binding.key,binding.values):text;
  }
  const observer = new MutationObserver(records => {
    // New text nodes get new bindings; changing a status never restores stale copy.
    for (const record of records) if (record.type==='characterData') bindings.delete(record.target);
    if (!scheduled) { scheduled=true; queueMicrotask(()=>{scheduled=false;refresh();}); }
  });
  function refresh() {
    observer.disconnect();
    document.documentElement.lang=locale;document.documentElement.dir=manifest[locale]?.dir || 'ltr';
    document.querySelectorAll('#global-language-select,#language-select').forEach(select=>{
      if(select.options.length!==Object.keys(names).length){select.replaceChildren(...Object.entries(names).map(([value,name])=>{const option=document.createElement('option');option.value=value;option.textContent=name;return option;}));}
      select.value=locale;
    });
    document.querySelectorAll('[data-i18n]').forEach(element=>{
      const text=t(element.dataset.i18n);if (text && element.textContent!==text)element.textContent=text;
    });
    document.querySelectorAll('[data-i18n-placeholder-key],[data-i18n-aria-label-key],[data-i18n-title-key],[data-i18n-alt-key]').forEach(element=>{
      for (const attr of ['placeholder','aria-label','title','alt']) {
        const key=element.getAttribute('data-i18n-'+attr+'-key');if(key)element.setAttribute(attr,t(key));
      }
    });
    document.querySelectorAll('[placeholder],[aria-label],[title],[alt]').forEach(element=>{
      if(element.closest('[data-i18n-ignore]'))return;
      let map=attributeBindings.get(element);if(!map){map={};attributeBindings.set(element,map);}
      for(const attr of ['placeholder','aria-label','title','alt']){
        const value=element.getAttribute(attr);if(value==null)continue;
        const binding=map[attr]||findBinding(value);if(binding){map[attr]=binding;element.setAttribute(attr,t(binding.key,binding.values));}
      }
    });
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    while(walker.nextNode()) {
      const node=walker.currentNode;const parent=node.parentElement;
      if(!parent || parent.closest(ignored+', [data-i18n]'))continue;
      let binding=bindings.get(node);
      if(!binding){binding=findBinding(node.nodeValue);if(binding)bindings.set(node,binding);}
      if(binding){const text=t(binding.key,binding.values);if(text && text!==node.nodeValue.trim())node.nodeValue=text;}
    }
    observer.observe(document.body,{childList:true,subtree:true,characterData:true});
  }
  async function load(lang) {
    if(resources.has(lang))return resources.get(lang);
    if(!loads.has(lang))loads.set(lang,fetch('i18n/'+lang+'.json').then(response=>{if(!response.ok)throw Error('Locale unavailable');return response.json();}).then(copy=>{resources.set(lang,copy);indexResource(copy);return copy;}).catch(()=>english));
    return loads.get(lang);
  }
  async function setLocale(value) {
    const next=normalize(value);const token=++revision;
    await load(next);if(token!==revision)return;
    locale=next;localStorage.setItem('snapp-language',locale);refresh();
    document.dispatchEvent(new CustomEvent('snapp:localechange',{detail:{locale}}));
  }
  window.SNAPP_I18N={get locale(){return locale;},names,t,translate,refresh,setLocale,load,
    ready:load(locale).then(()=>refresh())};
  document.getElementById('global-language-select')?.addEventListener('change',event=>setLocale(event.target.value));
  refresh();
  // Small static catalogs are cached before the user needs another language.
  Promise.all(Object.keys(names).map(load));
})();
