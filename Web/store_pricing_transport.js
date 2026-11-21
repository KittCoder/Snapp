/* One bounded deadline across API fallbacks, including stalled response bodies. */
(() => {
  'use strict';
  window.SNAPP_PRICE_REQUEST = async (path, body, parentSignal, timeoutMs=45000, onPrice) => {
    const controller=new AbortController();
    let timer,abort;
    const stopped=new Promise((_,reject)=>{
      abort=()=>{controller.abort();reject(new Error('Pricing request cancelled'));};
      if(parentSignal?.aborted)abort();
      else parentSignal?.addEventListener('abort',abort,{once:true});
      timer=setTimeout(()=>{controller.abort();reject(new Error('Price temporarily unavailable'));},timeoutMs);
    });
    const work=async()=>{
      let error;
      for(const endpoint of getApiEndpoints(path)){
        if(controller.signal.aborted)throw new Error('Pricing request cancelled');
        try{
          const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json',...(onPrice?{'Accept':'application/x-ndjson'}:{})},signal:controller.signal,body:JSON.stringify(body)});
          if(!response.ok)throw new Error('Pricing unavailable');
          if(onPrice&&response.headers?.get('content-type')?.includes('application/x-ndjson')&&response.body?.getReader){
            const reader=response.body.getReader(),decoder=new TextDecoder(),prices=[];
            let buffer='',storeId;
            const line=value=>{
              if(!value.trim())return;
              const message=JSON.parse(value);
              if(message.error)throw new Error(message.error);
              storeId=message.store_id;prices.push(message.price);onPrice(message);
            };
            try{
              while(true){
                const chunk=await reader.read();
                if(controller.signal.aborted)throw new Error('Pricing request cancelled');
                buffer+=decoder.decode(chunk.value||new Uint8Array(),{stream:!chunk.done});
                let end;while((end=buffer.indexOf('\n'))>=0){line(buffer.slice(0,end));buffer=buffer.slice(end+1);}
                if(chunk.done){line(buffer);break;}
              }
            }finally{reader.releaseLock();}
            return {store_id:storeId,prices};
          }
          return await response.json();
        }catch(e){error=e;if(controller.signal.aborted)throw e;}
      }
      throw error||new Error('Pricing unavailable');
    };
    try{return await Promise.race([work(),stopped]);}
    finally{clearTimeout(timer);parentSignal?.removeEventListener('abort',abort);}
  };
})();
