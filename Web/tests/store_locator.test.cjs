const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {performance}=require('node:perf_hooks');
const read=name=>fs.readFileSync(`${__dirname}/../${name}`,'utf8');
function setup(cached,network){
 const values=new Map(cached?[['snapp:stores:v1',JSON.stringify(cached)]]:[]),requests=[];
 const context=vm.createContext({window:{},console,Date,Set,localStorage:{getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v)},document:{getElementById:()=>null},getApiEndpoints:p=>[p],fetch:async url=>{requests.push(url);return {ok:true,json:async()=>({stores:await network()})};}});
 for(const name of ['nyc_zip_centroids.js','store_registry.js','store_locator.js'])vm.runInContext(read(name),context);
 return {context,api:context.window.SNAPP_STORES,rank:context.window.SNAPP_RANK_STORES,requests,values};
}
const stores=Array.from({length:12},(_,i)=>({id:`ctown:${i}`,store_name:'CTown Supermarkets',retailer:'ctown',product_count:3,latitude:40.7+i/100,longitude:-73.94,borough:'Brooklyn',zip_code:'11211'})).concat({id:'morton-williams',store_name:'Morton Williams',retailer:'morton_williams',product_count:3});
test('one shared registry fetch, all 12 C-Towns plus Morton, no requests on ZIP ranking',async()=>{
 const s=setup(null,async()=>stores);await Promise.all([s.api.load(),s.api.load()]);await s.api.load();
 assert.equal(s.api.stores.length,13);assert.equal(s.api.stores.filter(v=>v.retailer==='ctown').length,12);
 for(const zip of ['11211','10032','11102','10458','10304','90210','abc','']){assert.equal(s.rank(s.api.stores,zip).length,13);}
 assert.deepEqual(s.requests,['/api/stores']);
 assert.equal(s.api.stores[12].id,'morton-williams');
});
test('cached stores render synchronously while refresh is pending, refresh deduplicates and strips internals',async()=>{
 let finish;const network=new Promise(resolve=>finish=resolve);const s=setup({time:Date.now(),stores:[stores[0]]},()=>network);
 let rendered;s.api.subscribe(rows=>rendered=rows);assert.equal(rendered.length,1);
 const pending=s.api.load();assert.equal(rendered.length,1);
 await Promise.resolve();await Promise.resolve();finish([...stores,stores[0]]);await pending;assert.equal(rendered.length,13);assert.equal(rendered[0].inventory_version,undefined);
});
test('expired cache discarded, network failure preserves fresh cache and selection is untouched',async()=>{
 const old=setup({time:Date.now()-21*60*1000,stores},async()=>{throw Error('offline');});assert.equal(old.api.stores.length,0);await old.api.load();
 const fresh=setup({time:Date.now(),stores},async()=>{throw Error('offline');});await fresh.api.load();assert.equal(fresh.api.stores.length,13);
});
test('deterministic nearest ordering changes immediately, unlocated catalog remains last',()=>{
 const s=setup(null,async()=>stores), rows=[{id:'brooklyn',latitude:40.71,longitude:-73.95},{id:'bronx',latitude:40.86,longitude:-73.89},{id:'unknown',latitude:null,longitude:null}];
 assert.equal(s.rank(rows,'11211')[0].id,'brooklyn');assert.equal(s.rank(rows,'10458')[0].id,'bronx');assert.equal(s.rank(rows,'10458')[2].distance_miles,null);
 assert.deepEqual(s.rank(rows,'11211'),s.rank(rows,'11211'));
 for(const zip of ['11211','10032','11102','10458','10304'])assert.ok(s.rank(rows,zip)[0].distance_miles>=0,zip);
 const start=performance.now();for(let i=0;i<10000;i++)s.rank(stores,'11211');const ms=(performance.now()-start)/10000;console.log(`13-store ZIP ranking: ${ms.toFixed(4)} ms average`);assert.ok(ms<5);
});
test('selection uses backend ID; ZIP input performs no fetch, comparison or geocoding',()=>{
 const source=read('store_locator.js');assert.match(source,/button.value=store.id/);assert.match(source,/select\(store.id\)/);assert.doesNotMatch(source,/type='checkbox'/);assert.doesNotMatch(source,/fetch\(|\/api\/shopping\/compare|geolocation|geocod/i);
});
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.value='';this.classList={toggle(){}};}
 append(...nodes){this.children.push(...nodes);} replaceChildren(...nodes){this.children=nodes;}
 setAttribute(){} addEventListener(event,fn){this.listeners[event]=fn;}
}
test('Stores UI renders every catalog, immediate ZIP changes and canonical selection persist without network',async()=>{
 const s=setup(null,async()=>stores);const ids=['my-store-form','my-zip-code','my-store-results','my-store-status','my-store-start','my-store-map','my-store-source','selected-store-list'];
 const nodes=Object.fromEntries(ids.map(id=>[id,new Element('div')])),events={};
 s.context.document={getElementById:id=>nodes[id],createElement:tag=>new Element(tag),addEventListener:(name,fn)=>events[name]=fn,dispatchEvent:event=>events[event.type]?.(event)};
 s.context.Event=class{constructor(type){this.type=type;}};
 s.context.window.SNAPP_ACTIVE_STORE={id:null,select(id){this.id=id;s.values.set('snapp:active-store:v1',id);events['snapp:active-store']();}};
 vm.runInContext(read('store_locator.js'),s.context);await s.api.load();
 const list=nodes['my-store-results'];assert.equal(list.children.length,13);
 assert.equal(list.children.filter(n=>n.children[0].children[1].children[0].textContent==='C-Town').length,12);
 assert.equal(list.children.filter(n=>n.children[0].children[1].children[0].textContent==='Morton Williams').length,1);
 const input=nodes['my-zip-code'];input.value='11211';input.listeners.input();
 assert.match(nodes['my-store-status'].textContent,/Stores near 11211/);
 const first=list.children[0],check=first.children.at(-1);check.listeners.click();
 assert.equal(s.context.window.SNAPP_ACTIVE_STORE.id,check.value);assert.equal(s.values.get('snapp:active-store:v1'),check.value);
 input.value='10458';input.listeners.input();assert.match(nodes['my-store-status'].textContent,/10458/);
 assert.notEqual(list.children[0].children.at(-1).value,check.value);
 input.value='90210';input.listeners.input();assert.match(nodes['my-store-status'].textContent,/outside/);assert.equal(list.children.length,13);
 assert.deepEqual(s.requests,['/api/stores']);
});
