const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const read=f=>fs.readFileSync('Web/'+f,'utf8');
function transport(fetch){const timers=new Map();let seq=0;const context=vm.createContext({AbortController,TextDecoder,Uint8Array,window:{},getApiEndpoints:p=>[p],fetch,setTimeout:f=>{timers.set(++seq,f);return seq;},clearTimeout:id=>timers.delete(id)});vm.runInContext(read('store_pricing_transport.js'),context);return {context,timers,request:context.window.SNAPP_PRICE_REQUEST};}
test('bounded deadline rejects a stuck fetch, aborts it, and always clears timer',async()=>{let signal;const s=transport((_,options)=>{signal=options.signal;return new Promise(()=>{});});const p=s.request('/api/recipes/store-prices',{});assert.equal(s.timers.size,1);[...s.timers.values()][0]();await assert.rejects(p,/Price temporarily unavailable/);assert.equal(signal.aborted,true);assert.equal(s.timers.size,0);});
test('success and parent cancellation both clear timeout resources',async()=>{const s=transport(async()=>({ok:true,json:async()=>({ok:true})}));assert.equal((await s.request('/pricing',{})).ok,true);assert.equal(s.timers.size,0);const blocked=transport(()=>new Promise(()=>{})),parent=new AbortController(),p=blocked.request('/pricing',{},parent.signal);parent.abort();await assert.rejects(p,/cancelled/);assert.equal(blocked.timers.size,0);});
test('persisted active store warms at startup; selection warms new ID without loading registry',async()=>{const listeners={},requests=[],window={SNAPP_ACTIVE_STORE:{id:'ctown:PS41_311'},SNAPP_STORES:{stores:[{id:'ctown:PS41_311'},{id:'ctown:U41_186'}],subscribe:f=>f()},SNAPP_PRICE_REQUEST:async(path,body)=>requests.push({path,body})};vm.runInNewContext(read('store_warm.js'),{window,document:{addEventListener:(k,f)=>listeners[k]=f}});assert.equal(requests.length,1);assert.equal(requests[0].body.store_id,'ctown:PS41_311');window.SNAPP_ACTIVE_STORE.id='ctown:U41_186';listeners['snapp:active-store']();assert.equal(requests.length,2);assert.equal(requests[1].body.store_id,'ctown:U41_186');assert.ok(requests.every(r=>r.path==='/api/stores/warm'));});

test('NDJSON prices arrive before EOF, including split records and multibyte text',async()=>{
 const encoder=new TextEncoder();let next;const pending=new Promise(resolve=>next=resolve);
 const record=JSON.stringify({store_id:'s',price:{recipe_id:'0',label:'Café'}})+'\n';
 const bytes=encoder.encode(record);let reads=0;
 const s=transport(async(_,options)=>{
  assert.equal(options.headers.Accept,'application/x-ndjson');
  return {ok:true,headers:{get:()=> 'application/x-ndjson'},body:{getReader:()=>({read:async()=>++reads===1?{value:bytes.slice(0,9)}:reads===2?{value:bytes.slice(9)}:pending,releaseLock(){}})}};
 });
 const received=[],request=s.request('/pricing',{},null,45000,message=>received.push(message));
 await new Promise(resolve=>setImmediate(resolve));assert.equal(received.length,1);assert.equal(received[0].price.label,'Café');
 next({done:true});const result=await request;assert.equal(result.prices.length,1);assert.equal(s.timers.size,0);
});
