/* One bounded deadline across API fallbacks, including stalled response bodies. */
(() => {
  'use strict';
  window.SNAPP_PRICE_REQUEST = async (path, body, parentSignal, timeoutMs=5000) => {
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
          const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify(body)});
          if(!response.ok)throw new Error('Pricing unavailable');
          return await response.json();
        }catch(e){error=e;if(controller.signal.aborted)throw e;}
      }
      throw error||new Error('Pricing unavailable');
    };
    try{return await Promise.race([work(),stopped]);}
    finally{clearTimeout(timer);parentSignal?.removeEventListener('abort',abort);}
  };
})();
