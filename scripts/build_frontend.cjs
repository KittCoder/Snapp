'use strict';
// Only public browser configuration is emitted; backend environment is never copied.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const mode=process.env.SNAPP_BUILD_MODE||'production';
const vars={ 'snapp-api-base-url':process.env.SNAPP_API_BASE_URL, 'snapp-supabase-url':process.env.SUPABASE_URL, 'snapp-supabase-key':process.env.SUPABASE_ANON_KEY };
for(const [key,value] of Object.entries(vars))if(!value)throw Error(`Missing public configuration: ${key}`);
for(const key of ['snapp-api-base-url','snapp-supabase-url']){
 const url=new URL(vars[key]);
 if(url.username||url.password||url.search||url.hash)throw Error(`Invalid public URL: ${key}`);
 if(mode==='production'&&(url.protocol!=='https:'||['localhost','127.0.0.1'].includes(url.hostname)))throw Error(`Production HTTPS required: ${key}`);
}
const key=vars['snapp-supabase-key'];
if(key.startsWith('sb_secret_'))throw Error('Privileged Supabase key forbidden');
if(key.startsWith('eyJ')){const claims=JSON.parse(Buffer.from(key.split('.')[1],'base64url'));if(claims.role!=='anon')throw Error('Only anon JWT allowed');}
else if(!key.startsWith('sb_publishable_'))throw Error('Public Supabase credential required');
if(mode==='production'){
 const cfg=JSON.parse(fs.readFileSync(path.join(root,'vercel.json'),'utf8'));
 const csp=cfg.headers.flatMap(h=>h.headers).find(h=>h.key==='Content-Security-Policy').value;
 for(const name of ['snapp-api-base-url','snapp-supabase-url'])if(!csp.split(/[ ;]/).includes(new URL(vars[name]).origin))throw Error('Public origin absent from reviewed CSP; update vercel.json explicitly');
}
const out=path.join(root,'dist');fs.mkdirSync(out,{recursive:true});
fs.cpSync(path.join(root,'Web'),out,{recursive:true,filter:p=>!p.split(path.sep).includes('tests')});
let html=fs.readFileSync(path.join(out,'index.html'),'utf8');
for(const [name,value] of Object.entries(vars))html=html.replace(new RegExp(`(<meta name="${name}" content=")[^"]*("\\s*/>)`),(_,a,b)=>a+value.replaceAll('&','&amp;').replaceAll('"','&quot;')+b);
fs.writeFileSync(path.join(out,'index.html'),html);
console.log('Built static frontend with public configuration only');
